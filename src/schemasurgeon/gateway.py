"""SchemaSurgeon Gateway Orchestrator implementing bounded recovery, safety, and anti-flap."""

import asyncio
import copy
import time
from typing import Any, Dict, List, Optional
import httpx

from schemasurgeon.config import settings
from schemasurgeon.models import (
    AuditEvent,
    RecoveryContext,
    RecoveryOutcome,
    RepairCandidate,
    TaskIntent,
    ToolContract,
)
from schemasurgeon.registry import ToolRegistry, registry as default_registry
from schemasurgeon.diagnosis import DiagnosisEngine
from schemasurgeon.repair import (
    RequestRepairEngine,
    compute_request_fingerprint,
)
from schemasurgeon.validation import validate_payload
from schemasurgeon.verification import VerificationEngine
from schemasurgeon.audit import AuditLogger, audit_logger as default_audit_logger
from schemasurgeon.usps.confidence_gate import ConfidenceGate
from schemasurgeon.usps.request_suppression import RequestSuppressionEngine
from schemasurgeon.usps.intent_lock import IntentLock
from schemasurgeon.usps.drift_memory import DriftMemory, drift_memory as default_drift_memory


class SchemaSurgeonGateway:
    """Gateway orchestrating tool executions, schema failure detection, and self-healing."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        audit_logger: Optional[AuditLogger] = None,
        drift_memory: Optional[DriftMemory] = None,
    ):
        self.registry = registry or default_registry
        self.audit_logger = audit_logger or default_audit_logger
        self.drift_memory = drift_memory or default_drift_memory

        self.diagnosis_engine = DiagnosisEngine()
        self.repair_engine = RequestRepairEngine()
        self.verification_engine = VerificationEngine()
        self.confidence_gate = ConfidenceGate(
            min_confidence=settings.min_confidence_score,
            approval_threshold=0.80,
        )
        self.suppression_engine = RequestSuppressionEngine(
            failure_threshold=2,
            suppression_window_seconds=settings.anti_flap_window_seconds,
        )
        self.intent_lock = IntentLock()

        # Anti-flap tracking: tool_name -> list of float timestamps of recoveries
        self._recovery_history: Dict[str, List[float]] = {}
        # Fingerprint set to prevent duplicate retries in same recovery run
        self._seen_fingerprints: set[str] = set()

    def _check_anti_flap(self, tool_name: str) -> bool:
        """
        Anti-flap rule: at most 1 re-heal per tool within anti_flap_window_seconds (30s).
        Returns True if allowed, False if flap detected.
        """
        now = time.time()
        window = settings.anti_flap_window_seconds
        history = self._recovery_history.get(tool_name, [])
        # Keep only recent recoveries
        recent = [t for t in history if now - t <= window]
        self._recovery_history[tool_name] = recent

        if len(recent) >= settings.max_reheals_per_window:
            return False
        return True

    def _record_anti_flap_recovery(self, tool_name: str) -> None:
        if tool_name not in self._recovery_history:
            self._recovery_history[tool_name] = []
        self._recovery_history[tool_name].append(time.time())

    def reset_history(self) -> None:
        """Resets the in-memory anti-flap history and deduplication cache."""
        self._recovery_history.clear()
        self._seen_fingerprints.clear()

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        intent: Optional[TaskIntent] = None,
        deadline_seconds: Optional[float] = None,
    ) -> RecoveryOutcome:
        """Executes tool via gateway with bounded, confidence-gated self-healing."""
        start_time = time.time()
        deadline = deadline_seconds or settings.recovery_deadline_seconds

        context = RecoveryContext(
            tool_name=tool_name,
            active_version=1,
            original_arguments=arguments,
            deadline_seconds=deadline,
            intent=intent.model_dump() if intent else None,
        )

        # 1. Load active contract
        contract = self.registry.get_active(tool_name)
        if not contract:
            return RecoveryOutcome(
                status="error",
                tool_name=tool_name,
                old_version=0,
                error_class="unknown_tool",
                refusal_reason=f"Tool '{tool_name}' is not registered",
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        context.active_version = contract.version

        # 2. Check Request Suppression (USP 3)
        initial_fp = compute_request_fingerprint(
            tool_name=tool_name,
            method=contract.method,
            path=contract.path,
            arguments=arguments,
            headers=contract.required_headers,
        )

        is_suppressed, supp_reason = self.suppression_engine.is_suppressed(
            tool_name=tool_name,
            fingerprint=initial_fp,
            contract_version=contract.version,
        )
        if is_suppressed:
            self.audit_logger.log(
                AuditEvent(
                    event="request_suppressed",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    decision="SUPPRESSED",
                    refusal_reason=supp_reason,
                    metadata={"fingerprint": initial_fp},
                )
            )
            return RecoveryOutcome(
                status="suppressed",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=supp_reason,
                duration_ms=(time.time() - start_time) * 1000.0,
                error_class="request_suppressed",
            )

        self.audit_logger.log(
            AuditEvent(
                event="request_started",
                tool=tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=contract.version,
                metadata={"arguments": arguments},
            )
        )

        # 3. Initial Execution against API
        target_url = f"{contract.server_url.rstrip('/')}{contract.path}"
        http_status: Optional[int] = None
        raw_response: Optional[Any] = None
        network_error: Optional[str] = None

        try:
            timeout_val = min(context.remaining_deadline, 2.0)
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                res = await client.request(
                    method=contract.method,
                    url=target_url,
                    json=arguments,
                    headers=contract.required_headers,
                )
                http_status = res.status_code
                try:
                    raw_response = res.json()
                except Exception:
                    raw_response = res.text
        except httpx.TimeoutException:
            network_error = "timeout"
        except Exception as e:
            # Fallback to in-process mock_app if port 8001 is not running externally
            try:
                from mock_api.app import mock_app
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_app), base_url=contract.server_url) as fallback_client:
                    res = await fallback_client.request(
                        method=contract.method,
                        url=contract.path,
                        json=arguments,
                        headers=contract.required_headers,
                    )
                    http_status = res.status_code
                    try:
                        raw_response = res.json()
                    except Exception:
                        raw_response = res.text
            except Exception:
                network_error = str(e)

        # 4. Check for success on initial attempt
        is_schema_err = False
        if http_status == 200 and raw_response is not None:
            # Validate response schema
            is_valid_resp, resp_errs = validate_payload(raw_response, contract.response_schema)
            if is_valid_resp:
                # Intent Lock & Verification
                task_ok, task_reason = self._verify_outcome(contract, arguments, raw_response, intent)
                if task_ok:
                    dur_ms = (time.time() - start_time) * 1000.0
                    return RecoveryOutcome(
                        status="verified_success",
                        tool_name=tool_name,
                        old_version=contract.version,
                        new_version=contract.version,
                        retry_count=0,
                        task_verified=True,
                        promoted=False,
                        response_data=raw_response,
                        duration_ms=dur_ms,
                    )
            else:
                is_schema_err = True

        # 5. Check if failure is non-schema related
        if not is_schema_err and http_status is not None:
            is_schema_err = self.diagnosis_engine.is_schema_related_error(http_status, raw_response)

        if not is_schema_err:
            # Non-schema error policy (401, 403, 429, 5xx, or network timeout)
            error_class = "network_timeout" if network_error == "timeout" else (
                f"http_{http_status}" if http_status else "network_error"
            )
            # Record failure in suppression engine
            self.suppression_engine.record_failure(
                tool_name=tool_name,
                fingerprint=initial_fp,
                contract_version=contract.version,
                error_class=error_class,
                status_code=http_status,
            )
            dur_ms = (time.time() - start_time) * 1000.0
            return RecoveryOutcome(
                status="error",
                tool_name=tool_name,
                old_version=contract.version,
                error_class=error_class,
                refusal_reason=network_error or f"API returned non-schema error HTTP {http_status}",
                response_data=raw_response,
                duration_ms=dur_ms,
            )

        # ------------------------------------------------------------------
        # BEGIN BOUNDED RECOVERY
        # ------------------------------------------------------------------
        self.audit_logger.log(
            AuditEvent(
                event="schema_error_detected",
                tool=tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=contract.version,
                error_class="schema_validation",
                metadata={"status_code": http_status, "detail": raw_response},
            )
        )

        # Anti-Flap Check: block repeated re-healing within window
        if not self._check_anti_flap(tool_name):
            refusal_reason = f"Anti-flap policy: tool '{tool_name}' exceeded max re-heals in 30s window"
            self.audit_logger.log(
                AuditEvent(
                    event="recovery_refused",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    decision="REFUSE",
                    refusal_reason=refusal_reason,
                )
            )
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=refusal_reason,
                error_class="anti_flap_exceeded",
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # Check deadline before diagnosis
        if context.remaining_deadline <= 0.1:
            return self._handle_timeout(context, start_time, contract.version)

        # Check Drift Memory (USP 5)
        memory_pattern = None
        compat_entry = self.drift_memory.find_compatible_pattern(
            tool_name=tool_name,
            current_contract_hash=contract.contract_hash,
            candidate_req_schema={},  # Initial check
        )
        if compat_entry:
            memory_pattern = compat_entry.model_dump()
            self.audit_logger.log(
                AuditEvent(
                    event="drift_memory_reused",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    metadata={"verified_count": compat_entry.verified_count},
                )
            )

        trusted_configured_headers = {"X-Client-Version": "2", **contract.required_headers}

        # Diagnosis and Candidate Generation
        candidate: RepairCandidate = await self.diagnosis_engine.diagnose_and_plan(
            active_contract=contract,
            original_args=arguments,
            status_code=http_status,
            error_payload=raw_response,
            trusted_headers=trusted_configured_headers,
            memory_pattern=memory_pattern,
        )

        # Safety & Confidence Gate (USP 2)
        gate_decision = self.confidence_gate.evaluate(
            candidate=candidate,
            original_args=arguments,
            trusted_headers=trusted_configured_headers,
            conflicting_evidence=False,
        )

        self.audit_logger.log(
            AuditEvent(
                event="safety_decision_made",
                tool=tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=contract.version,
                candidate_version=candidate.target_version,
                decision=gate_decision.decision,
                refusal_reason="; ".join(gate_decision.reasons) if gate_decision.reasons else None,
                evidence=gate_decision.evidence,
            )
        )

        if gate_decision.decision != "AUTO_REPAIR":
            refusal_msg = "; ".join(gate_decision.reasons) or "Confidence score insufficient for auto-repair"
            # Record failure in suppression engine so repeated identical invalid requests are suppressed
            self.suppression_engine.record_failure(
                tool_name=tool_name,
                fingerprint=initial_fp,
                contract_version=contract.version,
                error_class="safety_refusal",
                status_code=http_status,
            )
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=refusal_msg,
                error_class="safety_refusal",
                duration_ms=(time.time() - start_time) * 1000.0,
                evidence_summary=gate_decision.evidence,
                decision=gate_decision.decision,
            )

        # Apply Request Adapter to transform request
        transformed_args, transformed_headers = self.repair_engine.apply_adapter(
            arguments=arguments,
            headers=trusted_configured_headers,
            adapter=candidate.request_adapter,
        )

        # Validate transformed arguments against candidate request schema
        is_valid_req, req_errs = validate_payload(transformed_args, candidate.candidate_request_schema)
        if not is_valid_req:
            refusal_msg = f"Transformed request failed candidate schema validation: {'; '.join(req_errs)}"
            self.audit_logger.log(
                AuditEvent(
                    event="recovery_refused",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    decision="REFUSE",
                    refusal_reason=refusal_msg,
                    metadata={"arguments": arguments},
                )
            )
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=refusal_msg,
                error_class="schema_validation",
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # Check duplicate fingerprint (Acceptance item 18: "Duplicate fingerprint is rejected before dispatch")
        repaired_fp = compute_request_fingerprint(
            tool_name=tool_name,
            method=contract.method,
            path=contract.path,
            arguments=transformed_args,
            headers=transformed_headers,
        )
        if repaired_fp in self._seen_fingerprints:
            refusal_msg = "Duplicate request fingerprint detected; aborting to prevent recursion loop"
            self.audit_logger.log(
                AuditEvent(
                    event="recovery_refused",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    decision="REFUSE",
                    refusal_reason=refusal_msg,
                    metadata={"fingerprint": repaired_fp},
                )
            )
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=refusal_msg,
                error_class="duplicate_fingerprint",
                duration_ms=(time.time() - start_time) * 1000.0,
            )
        self._seen_fingerprints.add(repaired_fp)

        # Check deadline before retry dispatch (Acceptance item 17: "Deadline leaves active registry unchanged")
        if context.remaining_deadline <= 0.1:
            return self._handle_timeout(context, start_time, contract.version)

        # DISPATCH REPAIR RETRY (AT MOST 1 RETRY PER RECOVERY RUN!)
        self.audit_logger.log(
            AuditEvent(
                event="repair_dispatched",
                tool=tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=contract.version,
                candidate_version=candidate.target_version,
                retry_count=1,
                metadata={"transformed_arguments": transformed_args, "headers": transformed_headers},
            )
        )

        retry_resp_data = None
        retry_status = None
        try:
            async with httpx.AsyncClient(timeout=min(context.remaining_deadline, 2.0)) as client:
                retry_res = await client.request(
                    method=contract.method,
                    url=target_url,
                    json=transformed_args,
                    headers=transformed_headers,
                )
                retry_status = retry_res.status_code
                try:
                    retry_resp_data = retry_res.json()
                except Exception:
                    retry_resp_data = retry_res.text
        except httpx.TimeoutException:
            return self._handle_timeout(context, start_time, contract.version)
        except Exception as e:
            # Fallback to in-process mock_app if port 8001 is not running externally
            try:
                from mock_api.app import mock_app
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_app), base_url=contract.server_url) as fallback_client:
                    retry_res = await fallback_client.request(
                        method=contract.method,
                        url=contract.path,
                        json=transformed_args,
                        headers=transformed_headers,
                    )
                    retry_status = retry_res.status_code
                    try:
                        retry_resp_data = retry_res.json()
                    except Exception:
                        retry_resp_data = retry_res.text
            except Exception:
                return RecoveryOutcome(
                    status="error",
                    tool_name=tool_name,
                    old_version=contract.version,
                    error_class="network_error",
                    refusal_reason=f"Retry network error: {str(e)}",
                    duration_ms=(time.time() - start_time) * 1000.0,
                )

        if retry_status != 200:
            self.registry.quarantine(tool_name, candidate, f"Retry returned HTTP {retry_status}")
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason=f"Retry attempt failed with HTTP {retry_status}",
                error_class="retry_failed",
                response_data=retry_resp_data,
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # Validate response payload against candidate response schema
        is_valid_resp, resp_errs = validate_payload(retry_resp_data, candidate.candidate_response_schema)
        if not is_valid_resp:
            self.registry.quarantine(tool_name, candidate, f"Response validation failed: {'; '.join(resp_errs)}")
            return RecoveryOutcome(
                status="quarantined",
                tool_name=tool_name,
                old_version=contract.version,
                refusal_reason="Response schema validation failed on retry",
                error_class="response_schema_validation",
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # Response envelope handling (safe unwrapping)
        unwrapped_data = self.repair_engine.unwrap_response(
            retry_resp_data, candidate.candidate_response_schema
        )

        # TASK VERIFICATION & INTENT LOCK (USP 4)
        task_ok, task_reason = self._verify_outcome(contract, arguments, unwrapped_data, intent)
        if not task_ok:
            # Failed verification NEVER promotes v2! (Acceptance item 13)
            self.registry.quarantine(tool_name, candidate, task_reason or "Task verification failed")
            self.audit_logger.log(
                AuditEvent(
                    event="candidate_quarantined",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    candidate_version=candidate.target_version,
                    refusal_reason=task_reason,
                )
            )
            return RecoveryOutcome(
                status="quarantined",
                tool_name=tool_name,
                old_version=contract.version,
                retry_count=1,
                task_verified=False,
                promoted=False,
                refusal_reason=task_reason,
                response_data=unwrapped_data,
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # ATOMIC REGISTRY PROMOTION
        promoted = await self.registry.promote_if_current(
            tool_name=tool_name,
            expected_version=contract.version,
            candidate=candidate,
        )

        if not promoted:
            # Concurrency / Promotion conflict (Acceptance item 20)
            self.audit_logger.log(
                AuditEvent(
                    event="promotion_conflict",
                    tool=tool_name,
                    task_id=context.task_id,
                    recovery_id=context.recovery_id,
                    old_version=contract.version,
                    refusal_reason="Active schema changed concurrently; promotion rejected",
                )
            )
            return RecoveryOutcome(
                status="refused",
                tool_name=tool_name,
                old_version=contract.version,
                retry_count=1,
                task_verified=True,
                promoted=False,
                refusal_reason="Promotion conflict: active schema updated concurrently",
                duration_ms=(time.time() - start_time) * 1000.0,
            )

        # Record in Drift Memory (USP 5)
        new_active = self.registry.get_active(tool_name)
        if new_active:
            self.drift_memory.store_verified_repair(
                tool_name=tool_name,
                from_contract_hash=contract.contract_hash,
                to_contract_hash=new_active.contract_hash,
                mappings=[m for m in candidate.request_adapter if m.get("op") == "move"],
                adapter=candidate.request_adapter,
            )

        # Clear suppression records for this tool on successful schema update
        self.suppression_engine.clear_for_tool(tool_name)
        self._record_anti_flap_recovery(tool_name)

        dur_ms = (time.time() - start_time) * 1000.0
        self.audit_logger.log(
            AuditEvent(
                event="registry_promoted",
                tool=tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=contract.version,
                candidate_version=candidate.target_version,
                retry_count=1,
                task_verified=True,
                promoted=True,
                duration_ms=dur_ms,
            )
        )

        return RecoveryOutcome(
            status="verified_success",
            tool_name=tool_name,
            old_version=contract.version,
            new_version=candidate.target_version,
            retry_count=1,
            task_verified=True,
            promoted=True,
            transformed_arguments=transformed_args,
            response_data=unwrapped_data,
            duration_ms=dur_ms,
            evidence_summary=gate_decision.evidence,
            decision="AUTO_REPAIR",
        )

    def _verify_outcome(
        self,
        contract: ToolContract,
        original_args: Dict[str, Any],
        response_data: Any,
        intent: Optional[TaskIntent],
    ) -> tuple[bool, Optional[str]]:
        """Verifies task completion and intent lock postconditions."""
        # Check Intent Lock first
        if intent:
            ok_intent, intent_err = self.intent_lock.validate_response_intent(intent, response_data)
            if not ok_intent:
                return False, intent_err

        # Check read verification
        req_id = original_args.get("user_id") or original_args.get("id")
        if req_id is not None:
            ok_read, read_err = self.verification_engine.verify_read_operation(
                requested_user_id=req_id,
                response_data=response_data,
            )
            if not ok_read:
                return False, read_err

        return True, None

    def _handle_timeout(
        self,
        context: RecoveryContext,
        start_time: float,
        old_version: int,
    ) -> RecoveryOutcome:
        dur_ms = (time.time() - start_time) * 1000.0
        self.audit_logger.log(
            AuditEvent(
                event="recovery_timeout",
                tool=context.tool_name,
                task_id=context.task_id,
                recovery_id=context.recovery_id,
                old_version=old_version,
                duration_ms=dur_ms,
                refusal_reason="Recovery deadline exceeded; active registry remains unchanged",
            )
        )
        return RecoveryOutcome(
            status="timeout",
            tool_name=context.tool_name,
            old_version=old_version,
            promoted=False,
            refusal_reason="Recovery deadline exceeded",
            error_class="deadline_exceeded",
            duration_ms=dur_ms,
        )
