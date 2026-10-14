"""USP 2: Confidence-Gated, Transparent Recovery."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from schemasurgeon.models import FieldMapping, RepairCandidate
from schemasurgeon.mapping_solver import is_safe_integer_conversion, is_security_sensitive


class GateDecision(BaseModel):
    decision: str  # AUTO_REPAIR, REQUIRES_APPROVAL, REFUSE
    confidence_score: float
    safety_checks_passed: bool
    evidence: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class ConfidenceGate:
    """Enforces confidence thresholds and non-negotiable hard safety checks."""

    def __init__(self, min_confidence: float = 0.50, approval_threshold: float = 0.80):
        self.min_confidence = min_confidence
        self.approval_threshold = approval_threshold

    def evaluate(
        self,
        candidate: RepairCandidate,
        original_args: Dict[str, Any],
        trusted_headers: Optional[Dict[str, str]] = None,
        conflicting_evidence: bool = False,
    ) -> GateDecision:
        """
        Evaluates a candidate repair against hard safety rules and score thresholds.
        A high numerical score MUST NEVER override a hard safety failure.
        """
        reasons: List[str] = []
        evidence = list(candidate.evidence)
        trusted_h = trusted_headers or {}

        # 1. Hard Rule: Conflicting Evidence Check
        if conflicting_evidence:
            reasons.append("Conflicting evidence detected between contract specification and observed payload")

        # 2. Hard Rule: Leading Zero & Unsafe Type Conversion Check
        for op in candidate.request_adapter:
            if op.get("op") == "move" and op.get("val_type") == "int":
                src = op.get("from")
                val = original_args.get(src)
                if val is not None and not is_safe_integer_conversion(val):
                    reasons.append(
                        f"Unsafe conversion: identifier '{val}' loses leading zeros or information when converted to integer"
                    )
            elif op.get("op") == "coerce_type" and op.get("new_type") == "int":
                path = op.get("path")
                val = original_args.get(path)
                if val is not None and not is_safe_integer_conversion(val):
                    reasons.append(
                        f"Unsafe conversion: identifier '{val}' loses leading zeros or information when converted to integer"
                    )

        # 3. Hard Rule: Required Header Provenance Check
        for op in candidate.request_adapter:
            if op.get("op") == "add_header":
                header_name = op.get("header")
                if header_name not in trusted_h:
                    reasons.append(
                        f"Required header '{header_name}' has no trusted authoritative source in gateway configuration"
                    )

        # 4. Hard Rule: Security Sensitive Fields Check
        for op in candidate.request_adapter:
            if is_security_sensitive(op.get("from", "")) or is_security_sensitive(op.get("to", "")):
                reasons.append("Candidate involves security-sensitive fields which cannot be repaired automatically")

        # 5. Check if candidate was already marked REFUSE by mapping solver
        if candidate.refusal_reason:
            reasons.append(candidate.refusal_reason)

        if reasons:
            return GateDecision(
                decision="REFUSE",
                confidence_score=0.0,
                safety_checks_passed=False,
                evidence=evidence,
                reasons=reasons,
            )

        # Numerical confidence evaluation
        score = candidate.confidence_score
        if score >= self.min_confidence:
            decision = "AUTO_REPAIR"
        else:
            decision = "REFUSE"
            reasons.append(f"Confidence score {score:.2f} is below minimum threshold {self.min_confidence}")

        return GateDecision(
            decision=decision,
            confidence_score=score,
            safety_checks_passed=True,
            evidence=evidence,
            reasons=reasons,
        )
