"""Structured JSONL Audit Logging with credential redaction and failure surfacing."""

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional
from schemasurgeon.config import settings
from schemasurgeon.models import AuditEvent

_SENSITIVE_KEYS = {
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts credentials and sensitive fields from dictionaries and lists."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if any(s in k.lower() for s in _SENSITIVE_KEYS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class AuditLogger:
    """Thread-safe JSONL audit logger."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or str(settings.audit_log_path)
        self._lock = threading.Lock()
        self._simulate_failure = False

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def set_simulate_failure(self, simulate: bool) -> None:
        """Testing utility to test surfacing of audit persistence failure."""
        self._simulate_failure = simulate

    def log(self, event: AuditEvent) -> None:
        """
        Appends a structured event to the JSONL log.
        Surfaces persistence failure if IO error occurs.
        """
        if self._simulate_failure:
            raise IOError("Simulated audit disk write failure: storage volume read-only")

        event_dict = event.model_dump()
        redacted_dict = redact_sensitive_data(event_dict)
        line = json.dumps(redacted_dict) + "\n"

        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                # Must surface failure rather than silently claiming complete audit trail!
                raise IOError(f"Audit persistence failure: unable to write event '{event.event}': {str(e)}") from e

    def read_events(self) -> List[Dict[str, Any]]:
        """Reads all logged events from file."""
        events = []
        if not os.path.exists(self.log_path):
            return events

        with self._lock:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except Exception:
                            continue
        return events

    def clear(self) -> None:
        """Clears audit log file."""
        with self._lock:
            if os.path.exists(self.log_path):
                open(self.log_path, "w").close()


audit_logger = AuditLogger()
