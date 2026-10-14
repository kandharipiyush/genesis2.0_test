import type { ExecutionOutcome } from "../types";

export interface ProbeDisplayData {
  outcomeType: "direct_success" | "verified_repair" | "refused" | "suppressed" | "timeout" | "error";
  scoreBoxClass: string;
  scoreLevelText: string;
  latencyLabel: string;
  summaryTitle: string;
  decisionPillText: string;
  decisionPillClass: string;
  refusalReason: string | null;
  evidenceTrail: string;
  isEvidenceGreen?: boolean;
  highlightedText: string;
  originalInput: string;
  transformedArgumentsText: string | null;
  verifiedResponseText: string | null;
  safetyTagText: string | null;
  usp1Title: string;
  usp1StatusText: string;
  usp1StatusClass: string;
  usp1MetricText: string;
  usp2Title: string;
  usp2StatusText: string;
  usp2StatusClass: string;
  usp2TokensText: string;
}

export function getProbeDisplayData(probeResult: any, probeUserId: string): ProbeDisplayData {
  const isVerifiedRepair =
    probeResult.status === "verified_success" &&
    (probeResult.promoted === true || (probeResult.retry_count && probeResult.retry_count > 0) || probeResult.decision === "AUTO_REPAIR");

  const isDirectSuccess = probeResult.status === "verified_success" && !isVerifiedRepair;
  const isRefused = probeResult.status === "refused" || probeResult.decision === "REFUSE";
  const isSuppressed = probeResult.status === "suppressed" || probeResult.decision === "SUPPRESSED";
  const isTimeout = probeResult.status === "timeout";

  const durationStr =
    probeResult.duration_ms !== undefined && probeResult.duration_ms !== null
      ? Number(probeResult.duration_ms).toFixed(1)
      : "0.0";

  if (isDirectSuccess) {
    const version = probeResult.old_version || 1;
    return {
      outcomeType: "direct_success",
      scoreBoxClass: "green",
      scoreLevelText: "DIRECT_SUCCESS",
      latencyLabel: `Latency: ${durationStr} ms`,
      summaryTitle: `Baseline v${version} Request Succeeded Directly (0 LLM Tokens Spent)`,
      decisionPillText: `DIRECT_EXECUTION — Active Contract v${version} Validated (No Drift)`,
      decisionPillClass: "uncertain-pill green",
      refusalReason: null,
      evidenceTrail:
        probeResult.evidence_summary && probeResult.evidence_summary.length > 0
          ? probeResult.evidence_summary.join(" • ")
          : `No schema drift detected. Upstream API responded directly with HTTP 200 matching active contract v${version}.`,
      isEvidenceGreen: true,
      highlightedText: `Caller passed user_id: "${probeUserId}". Target service accepted payload directly matching contract v${version}; response validated against active schema.`,
      originalInput: `user_id: "${probeUserId}"`,
      transformedArgumentsText: null,
      verifiedResponseText: probeResult.response_data ? JSON.stringify(probeResult.response_data) : null,
      safetyTagText: null,
      usp1Title: "Active Schema Validation (Direct Contract Match — No Drift)",
      usp1StatusText: "✓ direct match",
      usp1StatusClass: "confirmed-tag",
      usp1MetricText: `Latency: ${durationStr}ms`,
      usp2Title: "Intent Lock & Verification (Decision: DIRECT_EXECUTION)",
      usp2StatusText: "✓ verified",
      usp2StatusClass: "confirmed-tag",
      usp2TokensText: "Tokens: 0",
    };
  }

  if (isVerifiedRepair) {
    const newVer = probeResult.new_version || 2;
    const mappingEv = probeResult.evidence_summary?.find(
      (e: string) => e.startsWith("Mapped ") || e.includes("score:")
    );
    const mappingTitle = mappingEv
      ? `Deterministic AST Field Mapping: ${mappingEv.replace(/^Mapped\s+/, "")}`
      : "Deterministic AST Field Mapping (AST Adaptation Applied)";

    return {
      outcomeType: "verified_repair",
      scoreBoxClass: "orange",
      scoreLevelText: "VERIFIED_REPAIR",
      latencyLabel: `MTTR: ${durationStr} ms`,
      summaryTitle: "Safe Zero-Touch Repair Completed & Verified (0 LLM Tokens Spent)",
      decisionPillText: `AUTO_REPAIR — Contract Promoted to v${newVer}`,
      decisionPillClass: "uncertain-pill",
      refusalReason: null,
      evidenceTrail:
        probeResult.evidence_summary && probeResult.evidence_summary.length > 0
          ? probeResult.evidence_summary.join(" • ")
          : "Schema drift detected and auto-repaired.",
      isEvidenceGreen: false,
      highlightedText: `Original caller passed user_id: "${probeUserId}". Gateway intercepted schema drift, synthesized typed AST adaptation, and verified response against active intent.`,
      originalInput: `user_id: "${probeUserId}"`,
      transformedArgumentsText: probeResult.transformed_arguments
        ? JSON.stringify(probeResult.transformed_arguments)
        : null,
      verifiedResponseText: probeResult.response_data ? JSON.stringify(probeResult.response_data) : null,
      safetyTagText: null,
      usp1Title: mappingTitle,
      usp1StatusText: "✓ verified",
      usp1StatusClass: "confirmed-tag",
      usp1MetricText: `MTTR: ${durationStr}ms`,
      usp2Title: "Confidence Gate & Intent Lock (Decision: AUTO_REPAIR)",
      usp2StatusText: "✓ verified",
      usp2StatusClass: "confirmed-tag",
      usp2TokensText: "Tokens: 0",
    };
  }

  if (isRefused) {
    const isLeadingZero = probeResult.refusal_reason?.toLowerCase().includes("leading zero");
    const refusalLabel = isLeadingZero
      ? "Hard Safety Rule: Leading-Zero Loss Guard (Unsafe Conversion Blocked)"
      : "Safety Gate Invariant Guard (Unsafe Adaptation Blocked)";

    return {
      outcomeType: "refused",
      scoreBoxClass: "red",
      scoreLevelText: "REFUSED",
      latencyLabel: `Latency: ${durationStr} ms`,
      summaryTitle: "Safe Refusal Enforced by Gateway Safety Guardrails",
      decisionPillText: isLeadingZero
        ? "REFUSED — Hard Safety Invariant Protected (Leading-Zero Rule)"
        : "REFUSED — Hard Safety Invariant Protected",
      decisionPillClass: "uncertain-pill red",
      refusalReason: probeResult.refusal_reason || "Safety check failed",
      evidenceTrail:
        probeResult.evidence_summary && probeResult.evidence_summary.length > 0
          ? probeResult.evidence_summary.join(" • ")
          : "Schema drift detected. Repair refused by safety gate.",
      isEvidenceGreen: false,
      highlightedText: `Caller passed user_id: "${probeUserId}". Gateway intercepted upstream schema drift and safety guardrails refused adaptation to prevent data corruption or ambiguous mapping.`,
      originalInput: `user_id: "${probeUserId}"`,
      transformedArgumentsText: null,
      verifiedResponseText: null,
      safetyTagText: `Safety Gate: ${probeResult.error_class || "safety_refusal"}`,
      usp1Title: refusalLabel,
      usp1StatusText: "✕ blocked",
      usp1StatusClass: "refused-tag",
      usp1MetricText: `Latency: ${durationStr}ms`,
      usp2Title: "Confidence Gate & Safety Guard (Decision: REFUSE)",
      usp2StatusText: "✕ refusal enforced",
      usp2StatusClass: "refused-tag",
      usp2TokensText: "Tokens: 0",
    };
  }

  if (isSuppressed) {
    return {
      outcomeType: "suppressed",
      scoreBoxClass: "red",
      scoreLevelText: "SUPPRESSED",
      latencyLabel: "Blocked",
      summaryTitle: "Request Suppressed by Anti-Flap Rate Limiter",
      decisionPillText: "SUPPRESSED — Repeated Failure Window Active",
      decisionPillClass: "uncertain-pill red",
      refusalReason: probeResult.refusal_reason || "Request suppressed",
      evidenceTrail:
        probeResult.evidence_summary && probeResult.evidence_summary.length > 0
          ? probeResult.evidence_summary.join(" • ")
          : (probeResult.refusal_reason || "Request suppressed to prevent loop"),
      isEvidenceGreen: false,
      highlightedText: `Request for user_id: "${probeUserId}" was suppressed by the anti-flap engine to prevent cascading API degradation.`,
      originalInput: `user_id: "${probeUserId}"`,
      transformedArgumentsText: null,
      verifiedResponseText: null,
      safetyTagText: "Suppressed: anti_flap_active",
      usp1Title: "Adaptive Invalid-Request Suppression (USP-3 Guard)",
      usp1StatusText: "✕ suppressed",
      usp1StatusClass: "refused-tag",
      usp1MetricText: `Latency: ${durationStr}ms`,
      usp2Title: "Confidence Gate & Anti-Flap (Decision: SUPPRESSED)",
      usp2StatusText: "✕ suppressed",
      usp2StatusClass: "refused-tag",
      usp2TokensText: "Tokens: 0",
    };
  }

  // Timeout or generic error
  return {
    outcomeType: isTimeout ? "timeout" : "error",
    scoreBoxClass: "red",
    scoreLevelText: (probeResult.status || "ERROR").toUpperCase(),
    latencyLabel: `Latency: ${durationStr} ms`,
    summaryTitle: isTimeout
      ? "Recovery Deadline Exceeded"
      : `Gateway Error: ${probeResult.error_class || "Execution Error"}`,
    decisionPillText: isTimeout
      ? "TIMEOUT — Recovery Deadline Exceeded"
      : "ERROR — Execution Failed",
    decisionPillClass: "uncertain-pill red",
    refusalReason: probeResult.refusal_reason || "Execution failed",
    evidenceTrail:
      probeResult.evidence_summary && probeResult.evidence_summary.length > 0
        ? probeResult.evidence_summary.join(" • ")
        : (probeResult.refusal_reason || "No evidence recorded"),
    isEvidenceGreen: false,
    highlightedText: `Execution failed for user_id: "${probeUserId}". ${probeResult.refusal_reason || ""}`,
    originalInput: `user_id: "${probeUserId}"`,
    transformedArgumentsText: null,
    verifiedResponseText: null,
    safetyTagText: probeResult.error_class || "error",
    usp1Title: `Gateway Policy (${(probeResult.status || "error").toUpperCase()})`,
    usp1StatusText: "✕ failed",
    usp1StatusClass: "refused-tag",
    usp1MetricText: `Latency: ${durationStr}ms`,
    usp2Title: `Decision Engine (Decision: ${(probeResult.decision || "ERROR").toUpperCase()})`,
    usp2StatusText: "✕ failed",
    usp2StatusClass: "refused-tag",
    usp2TokensText: "Tokens: 0",
  };
}
