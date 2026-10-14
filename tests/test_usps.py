"""USP Acceptance Tests covering all 5 USPs."""

import pytest
from schemasurgeon.models import TaskIntent, RepairCandidate
from schemasurgeon.usps.proactive_monitor import ProactiveMonitor
from schemasurgeon.usps.confidence_gate import ConfidenceGate
from schemasurgeon.usps.request_suppression import RequestSuppressionEngine
from schemasurgeon.usps.intent_lock import IntentLock
from schemasurgeon.usps.drift_memory import DriftMemory
from mock_api.mutations import active_mutations


@pytest.mark.asyncio
async def test_acceptance_22_proactive_monitor_detects_changed_openapi(fresh_registry, monkeypatch):
    """Acceptance 22: Proactive monitor detects a changed OpenAPI contract before runtime error."""
    import httpx

    # Simulate changed OpenAPI document from server
    changed_openapi = {
        "paths": {
            "/get_user": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "integer", "description": "User identifier"}},
                                    "required": ["id"],
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"properties": {"id": {"type": "integer"}, "plan": {"type": "string"}}}
                                }
                            }
                        }
                    },
                }
            }
        }
    }

    async def mock_get(*args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return changed_openapi
        return MockResp()

    async def mock_request(*args, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return {"id": 123, "plan": "basic"}
        return MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    monitor = ProactiveMonitor(registry=fresh_registry)
    detected, candidate, evidence = await monitor.check_for_drift("get_user")

    assert detected is True
    assert candidate is not None
    assert candidate.decision == "AUTO_REPAIR"
    assert any("hash mismatch" in ev.lower() for ev in evidence)


def test_acceptance_23_confidence_gate_refuses_unsafe_candidates():
    """Acceptance 23: Confidence gate refuses unsafe candidates."""
    gate = ConfidenceGate(min_confidence=0.50)
    candidate = RepairCandidate(
        target_version=2,
        confidence_score=0.35,  # Low score!
        decision="REFUSE",
        refusal_reason="Confidence score 0.35 is below minimum threshold 0.50",
    )

    decision = gate.evaluate(candidate, original_args={"user_id": "123"})
    assert decision.decision == "REFUSE"
    assert decision.safety_checks_passed is False


def test_acceptance_24_repeated_invalid_requests_suppressed():
    """Acceptance 24: Repeated invalid requests are suppressed appropriately."""
    supp_engine = RequestSuppressionEngine(failure_threshold=2, suppression_window_seconds=30.0)
    tool_name = "unknown_tool"
    fp = "test-fingerprint-123"

    # First attempt: not suppressed
    is_supp, _ = supp_engine.is_suppressed(tool_name, fp, 1)
    assert is_supp is False

    # Failure 1
    supp_engine.record_failure(tool_name, fp, 1, "schema_error", 422)
    is_supp, _ = supp_engine.is_suppressed(tool_name, fp, 1)
    assert is_supp is False

    # Failure 2 -> triggers suppression!
    supp_engine.record_failure(tool_name, fp, 1, "schema_error", 422)
    is_supp, reason = supp_engine.is_suppressed(tool_name, fp, 1)
    assert is_supp is True
    assert "identical invalid request" in reason.lower()

    # Safety check: New contract version clears suppression!
    is_supp_v2, _ = supp_engine.is_suppressed(tool_name, fp, 2)
    assert is_supp_v2 is False


def test_acceptance_25_intent_lock_detects_wrong_target():
    """Acceptance 25: Intent Lock detects a wrong-target result."""
    intent_lock = IntentLock()
    intent = TaskIntent(
        task_id="t1",
        intent="Query plan for user 123",
        constraints={"user_id": "123"},
        postconditions=["plan_exists"],
    )

    valid, reason = intent_lock.validate_response_intent(
        intent=intent,
        response_data={"id": 456, "plan": "pro"},  # Wrong ID!
    )
    assert valid is False
    assert "wrong target rejected" in reason.lower() or "456" in reason


def test_acceptance_26_drift_memory_reuses_compatible_pattern():
    """Acceptance 26: Drift Memory reuses a compatible verified pattern."""
    memory = DriftMemory()
    candidate_schema = {
        "properties": {
            "target": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
            }
        }
    }

    # Store verified pattern
    memory.store_verified_repair(
        tool_name="get_user",
        from_contract_hash="hash_v1",
        to_contract_hash="hash_v2",
        mappings=[{"source": "user_id", "target": "target.id"}],
        adapter=[{"op": "move", "from": "user_id", "to": "target.id"}],
    )

    # Lookup compatible pattern
    entry = memory.find_compatible_pattern(
        tool_name="get_user",
        current_contract_hash="hash_v1",
        candidate_req_schema=candidate_schema,
    )

    assert entry is not None
    assert entry.to_contract_hash == "hash_v2"
    assert entry.verified_count >= 1


def test_acceptance_27_drift_memory_rejects_incompatible_pattern():
    """Acceptance 27: Drift Memory rejects an incompatible or stale pattern."""
    memory = DriftMemory()
    # Incompatible candidate schema: expects 'account_id', not 'target.id'
    incompatible_schema = {
        "properties": {
            "account_id": {"type": "integer"},
        }
    }

    memory.store_verified_repair(
        tool_name="get_user",
        from_contract_hash="hash_v1",
        to_contract_hash="hash_v2",
        mappings=[{"source": "user_id", "target": "target.id"}],
        adapter=[{"op": "move", "from": "user_id", "to": "target.id"}],
    )

    entry = memory.find_compatible_pattern(
        tool_name="get_user",
        current_contract_hash="hash_v1",
        candidate_req_schema=incompatible_schema,
    )

    assert entry is None  # Incompatible pattern safely rejected!
