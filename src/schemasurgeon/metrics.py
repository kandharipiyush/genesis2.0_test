"""Metrics aggregation and calculation engine based on JSONL audit events."""

import math
from typing import Any, Dict, List, Optional
from schemasurgeon.audit import audit_logger


def compute_metrics(events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Calculates operational and recovery metrics from audit event history."""
    if events is None:
        events = audit_logger.read_events()

    total_calls = 0
    schema_incidents = 0
    verified_recoveries = 0
    refusals = 0
    quarantined = 0
    suppressed = 0
    timeouts = 0
    proactive_adaptations = 0
    recovery_durations: List[float] = []

    for ev in events:
        event_name = ev.get("event")
        if event_name == "request_started":
            total_calls += 1
        elif event_name == "schema_error_detected":
            schema_incidents += 1
        elif event_name in ("registry_promoted", "repair_verified"):
            verified_recoveries += 1
            dur = ev.get("duration_ms")
            if dur is not None and dur > 0:
                recovery_durations.append(dur)
        elif event_name in ("recovery_refused", "safety_refusal"):
            refusals += 1
        elif event_name == "candidate_quarantined":
            quarantined += 1
        elif event_name == "request_suppressed":
            suppressed += 1
        elif event_name == "recovery_timeout":
            timeouts += 1
        elif event_name == "proactive_change_detected":
            proactive_adaptations += 1

    # Zero-Touch Adaptation Rate
    adaptation_rate = (
        (verified_recoveries / schema_incidents * 100.0)
        if schema_incidents > 0
        else (100.0 if verified_recoveries > 0 else 0.0)
    )

    # MTTR calculations
    mean_mttr = sum(recovery_durations) / len(recovery_durations) if recovery_durations else 0.0
    sorted_durations = sorted(recovery_durations)
    median_mttr = 0.0
    p95_mttr = 0.0
    max_mttr = 0.0

    if sorted_durations:
        n = len(sorted_durations)
        median_mttr = sorted_durations[n // 2]
        p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
        p95_mttr = sorted_durations[p95_idx]
        max_mttr = sorted_durations[-1]

    return {
        "total_calls": total_calls,
        "schema_drift_incidents": schema_incidents,
        "verified_recoveries": verified_recoveries,
        "zero_touch_adaptation_rate": round(adaptation_rate, 1),
        "mean_mttr_ms": round(mean_mttr, 1),
        "median_mttr_ms": round(median_mttr, 1),
        "p95_mttr_ms": round(p95_mttr, 1),
        "max_mttr_ms": round(max_mttr, 1),
        "unsafe_repairs_refused": refusals,
        "failed_verifications": quarantined,
        "requests_suppressed": suppressed,
        "timeouts": timeouts,
        "proactive_adaptations": proactive_adaptations,
        "sample_count": len(recovery_durations),
    }
