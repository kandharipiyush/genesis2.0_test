"""USP 3: Adaptive Invalid-Request Suppression - Prevents repeated invalid tool processing."""

import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class SuppressionRecord(BaseModel):
    tool_name: str
    fingerprint: str
    contract_version: int
    error_class: str
    failure_count: int = 1
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    suppressed_until: Optional[float] = None


class RequestSuppressionEngine:
    """Tracks failed requests and suppresses repeated identical invalid calls."""

    def __init__(
        self,
        failure_threshold: int = 2,
        suppression_window_seconds: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.suppression_window_seconds = suppression_window_seconds
        # key: f"{tool_name}:{fingerprint}" -> SuppressionRecord
        self._records: Dict[str, SuppressionRecord] = {}

    def is_suppressed(
        self,
        tool_name: str,
        fingerprint: str,
        contract_version: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if a request fingerprint is currently suppressed.
        Returns: (is_suppressed, reason)
        """
        now = time.time()
        key = f"{tool_name}:{fingerprint}"
        rec = self._records.get(key)
        if not rec:
            return False, None

        # Check if contract version changed -> clear suppression!
        if rec.contract_version != contract_version:
            self._records.pop(key, None)
            return False, None

        # Check if active suppression window is still in effect
        if rec.suppressed_until and now < rec.suppressed_until:
            remaining = int(rec.suppressed_until - now)
            return (
                True,
                f"Request suppressed: identical invalid request failed {rec.failure_count} times. "
                f"Suppression active for {remaining} more seconds.",
            )

        # Expired suppression
        if rec.suppressed_until and now >= rec.suppressed_until:
            self._records.pop(key, None)
            return False, None

        return False, None

    def record_failure(
        self,
        tool_name: str,
        fingerprint: str,
        contract_version: int,
        error_class: str,
        status_code: Optional[int] = None,
    ) -> bool:
        """
        Records a failure. If threshold reached, enters suppression.
        Safety rule: Do NOT suppress 429, 5xx, or timeouts!
        Returns: True if suppression was triggered.
        """
        # Safety filter
        if status_code in (429, 500, 502, 503, 504) or "timeout" in error_class.lower():
            return False

        now = time.time()
        key = f"{tool_name}:{fingerprint}"

        if key in self._records:
            rec = self._records[key]
            rec.failure_count += 1
            rec.last_seen = now
            if rec.failure_count >= self.failure_threshold:
                rec.suppressed_until = now + self.suppression_window_seconds
                return True
        else:
            self._records[key] = SuppressionRecord(
                tool_name=tool_name,
                fingerprint=fingerprint,
                contract_version=contract_version,
                error_class=error_class,
                failure_count=1,
                first_seen=now,
                last_seen=now,
            )

        return False

    def clear_for_tool(self, tool_name: str) -> None:
        """Clears suppression records when a tool updates its contract."""
        keys_to_del = [k for k in self._records if k.startswith(f"{tool_name}:")]
        for k in keys_to_del:
            self._records.pop(k, None)

    def reset(self) -> None:
        self._records.clear()
