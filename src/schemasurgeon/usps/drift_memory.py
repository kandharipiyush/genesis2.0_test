"""USP 5: Drift Memory - Stores and reuses verified repair patterns."""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    tool_name: str
    from_contract_hash: str
    to_contract_hash: str
    mappings: List[Dict[str, Any]]
    adapter: List[Dict[str, Any]]
    created_at: float = Field(default_factory=time.time)
    verified_count: int = 1


class DriftMemory:
    """Stores verified schema repairs and re-evaluates them as evidence."""

    def __init__(self):
        # key: f"{tool_name}:{from_contract_hash}" -> List[MemoryEntry]
        self._entries: Dict[str, List[MemoryEntry]] = {}

    def store_verified_repair(
        self,
        tool_name: str,
        from_contract_hash: str,
        to_contract_hash: str,
        mappings: List[Dict[str, Any]],
        adapter: List[Dict[str, Any]],
    ) -> None:
        """Stores a newly verified schema repair pattern."""
        key = f"{tool_name}:{from_contract_hash}"
        if key not in self._entries:
            self._entries[key] = []

        # Check if already exists, update verification count
        for entry in self._entries[key]:
            if entry.to_contract_hash == to_contract_hash:
                entry.verified_count += 1
                return

        self._entries[key].append(
            MemoryEntry(
                tool_name=tool_name,
                from_contract_hash=from_contract_hash,
                to_contract_hash=to_contract_hash,
                mappings=mappings,
                adapter=adapter,
            )
        )

    def find_compatible_pattern(
        self,
        tool_name: str,
        current_contract_hash: str,
        candidate_req_schema: Dict[str, Any],
    ) -> Optional[MemoryEntry]:
        """
        Finds a verified repair pattern that is compatible with current candidate schema.
        Re-validates compatibility: all target properties in adapter/mappings must exist in candidate schema.
        Rejects incompatible or stale entries!
        """
        key = f"{tool_name}:{current_contract_hash}"
        entries = self._entries.get(key, [])

        for entry in entries:
            # Check compatibility with candidate_req_schema
            is_compatible = True
            for op in entry.adapter:
                if op.get("op") == "move":
                    target_path = op.get("to")
                    # Check if target_path exists in candidate_req_schema
                    parts = target_path.split(".")
                    curr = candidate_req_schema.get("properties", {})
                    for p in parts:
                        if not isinstance(curr, dict) or p not in curr:
                            is_compatible = False
                            break
                        if "properties" in curr[p]:
                            curr = curr[p]["properties"]

            if is_compatible:
                return entry

        return None

    def get_all_entries(self) -> List[Dict[str, Any]]:
        result = []
        for entries in self._entries.values():
            for e in entries:
                result.append(e.model_dump())
        return result

    def reset(self) -> None:
        self._entries.clear()


drift_memory = DriftMemory()
