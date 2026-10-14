"""Versioned per-tool Schema Registry with atomic promotion and concurrency protection."""

import asyncio
import hashlib
import json
import threading
from typing import Any, Dict, List, Optional
from schemasurgeon.models import ToolContract, RepairCandidate


def canonical_contract_hash(data: Dict[str, Any]) -> str:
    """Computes a stable SHA-256 hash of canonicalized JSON."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ToolRegistry:
    """In-memory thread-safe and async-safe schema registry."""

    def __init__(self):
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        # tool_name -> active_version (int)
        self._active_versions: Dict[str, int] = {}
        # (tool_name, version) -> ToolContract
        self._contracts: Dict[tuple[str, int], ToolContract] = {}
        # tool_name -> candidate RepairCandidate
        self._staged_candidates: Dict[str, RepairCandidate] = {}
        # tool_name -> list of quarantined entries
        self._quarantine: Dict[str, List[Dict[str, Any]]] = {}

    def register(self, contract: ToolContract) -> None:
        """Registers a contract version and sets it active if first version."""
        with self._lock:
            if not contract.contract_hash:
                full_dict = {
                    "method": contract.method,
                    "path": contract.path,
                    "request_schema": contract.request_schema,
                    "response_schema": contract.response_schema,
                    "required_headers": contract.required_headers,
                }
                contract.contract_hash = canonical_contract_hash(full_dict)

            key = (contract.tool_name, contract.version)
            self._contracts[key] = contract

            if contract.tool_name not in self._active_versions:
                self._active_versions[contract.tool_name] = contract.version
            elif contract.version > self._active_versions[contract.tool_name]:
                # Explicit registration of higher version
                self._active_versions[contract.tool_name] = contract.version

    def get_active(self, tool_name: str) -> Optional[ToolContract]:
        """Returns the currently active contract for a tool."""
        with self._lock:
            version = self._active_versions.get(tool_name)
            if version is None:
                return None
            return self._contracts.get((tool_name, version))

    def get_version(self, tool_name: str, version: int) -> Optional[ToolContract]:
        """Returns a specific version of a tool contract."""
        with self._lock:
            return self._contracts.get((tool_name, version))

    def get_history(self, tool_name: str) -> List[ToolContract]:
        """Returns all versions of a tool in ascending order."""
        with self._lock:
            contracts = [
                c for (name, _), c in self._contracts.items()
                if name == tool_name
            ]
            return sorted(contracts, key=lambda c: c.version)

    def stage_candidate(self, tool_name: str, candidate: RepairCandidate) -> None:
        """Stages a candidate schema for evaluation without making it active."""
        with self._lock:
            self._staged_candidates[tool_name] = candidate

    def get_staged(self, tool_name: str) -> Optional[RepairCandidate]:
        with self._lock:
            return self._staged_candidates.get(tool_name)

    async def promote_if_current(
        self,
        tool_name: str,
        expected_version: int,
        candidate: RepairCandidate,
    ) -> bool:
        """
        Atomically promotes a candidate if active version matches expected_version.
        Protects against concurrent race conditions or promotion conflicts.
        """
        async with self._async_lock:
            with self._lock:
                current_active = self.get_active(tool_name)
                if not current_active:
                    return False

                # Concurrency check: If another request already promoted to newer version, reject!
                if current_active.version != expected_version:
                    return False

                new_version = expected_version + 1
                new_contract_dict = {
                    "method": current_active.method,
                    "path": current_active.path,
                    "request_schema": candidate.candidate_request_schema,
                    "response_schema": candidate.candidate_response_schema,
                    "required_headers": candidate.candidate_headers,
                }
                new_hash = canonical_contract_hash(new_contract_dict)

                new_contract = ToolContract(
                    tool_name=tool_name,
                    version=new_version,
                    method=current_active.method,
                    path=current_active.path,
                    request_schema=candidate.candidate_request_schema,
                    response_schema=candidate.candidate_response_schema,
                    contract_hash=new_hash,
                    server_url=current_active.server_url,
                    required_headers=candidate.candidate_headers,
                    metadata={"promoted_from": expected_version, "confidence": candidate.confidence_score},
                )

                self._contracts[(tool_name, new_version)] = new_contract
                self._active_versions[tool_name] = new_version
                self._staged_candidates.pop(tool_name, None)
                return True

    def quarantine(self, tool_name: str, candidate: RepairCandidate, reason: str) -> None:
        """Quarantines an unverified or unsafe candidate."""
        with self._lock:
            if tool_name not in self._quarantine:
                self._quarantine[tool_name] = []
            self._quarantine[tool_name].append({
                "candidate": candidate.model_dump(),
                "reason": reason,
            })
            self._staged_candidates.pop(tool_name, None)

    def get_quarantined(self, tool_name: str) -> List[Dict[str, Any]]:
        with self._lock:
            return self._quarantine.get(tool_name, []).copy()

    def reset(self) -> None:
        """Clears all registry state."""
        with self._lock:
            self._active_versions.clear()
            self._contracts.clear()
            self._staged_candidates.clear()
            self._quarantine.clear()


registry = ToolRegistry()
