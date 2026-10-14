import test from "node:test";
import assert from "node:assert/strict";
import { getProbeDisplayData } from "../dashboard/src/components/probeResultFormat.ts";

test("Scenario 1: Baseline v1 probe succeeds directly without auto-repair claims", () => {
  const backendResponse = {
    status: "verified_success",
    tool_name: "get_user",
    old_version: 1,
    new_version: 1,
    retry_count: 0,
    task_verified: true,
    promoted: false,
    refusal_reason: null,
    transformed_arguments: null,
    response_data: { id: 456, plan: "pro" },
    duration_ms: 9.1,
    error_class: null,
    evidence_summary: [],
    decision: "DIRECT_SUCCESS",
  };

  const display = getProbeDisplayData(backendResponse, "456");

  // Must be classified as direct_success
  assert.equal(display.outcomeType, "direct_success");
  assert.equal(display.scoreLevelText, "DIRECT_SUCCESS");
  assert.equal(display.scoreBoxClass, "green");

  // Decision pill must NOT claim AUTO_REPAIR
  assert.match(display.decisionPillText, /DIRECT_EXECUTION/);
  assert.doesNotMatch(display.decisionPillText, /AUTO_REPAIR/);

  // Evidence trail must NOT have hardcoded 422 or target.id mapping or score 0.73
  assert.doesNotMatch(display.evidenceTrail, /422/);
  assert.doesNotMatch(display.evidenceTrail, /target\.id/);
  assert.doesNotMatch(display.evidenceTrail, /0\.73/);
  assert.match(display.evidenceTrail, /No schema drift detected/);

  // Transformation and verification details must not claim AST adaptation
  assert.doesNotMatch(display.highlightedText, /applied typed AST adaptation/);
  assert.equal(display.transformedArgumentsText, null);
  assert.equal(display.verifiedResponseText, JSON.stringify({ id: 456, plan: "pro" }));

  // Invariant guarantees must reflect direct validation, not auto-repair
  assert.match(display.usp1Title, /Direct Contract Match/);
  assert.equal(display.usp1StatusText, "✓ direct match");
  assert.match(display.usp2Title, /DIRECT_EXECUTION/);
  assert.doesNotMatch(display.usp2Title, /AUTO_REPAIR/);
  assert.equal(display.usp2StatusText, "✓ verified");
});

test("Scenario 2: SW-02 leading-zero probe displays REFUSED and no AUTO_REPAIR claims in lower panel", () => {
  const backendResponse = {
    status: "refused",
    tool_name: "get_user",
    old_version: 1,
    new_version: null,
    retry_count: 0,
    task_verified: false,
    promoted: false,
    refusal_reason: "Unsafe type conversion: '00123' loses leading zeros or information when converted to integer",
    transformed_arguments: null,
    response_data: null,
    duration_ms: 19.1,
    error_class: "safety_refusal",
    evidence_summary: [
      "HTTP 422 schema error observed",
      "Fetched authoritative OpenAPI v2 contract from trusted server",
      "Hard safety refusal triggered: Unsafe type conversion: '00123' loses leading zeros or information when converted to integer",
    ],
    decision: "REFUSE",
  };

  const display = getProbeDisplayData(backendResponse, "00123");

  // Main score box must be REFUSED with red styling
  assert.equal(display.outcomeType, "refused");
  assert.equal(display.scoreLevelText, "REFUSED");
  assert.equal(display.scoreBoxClass, "red");

  // Decision pill must be REFUSED, NOT AUTO_REPAIR
  assert.match(display.decisionPillText, /REFUSED/);
  assert.doesNotMatch(display.decisionPillText, /AUTO_REPAIR/);

  // Refusal reason must be present
  assert.match(display.refusalReason, /leading zeros/);

  // Highlighted text must describe refusal, NOT claim successful transformation
  assert.doesNotMatch(display.highlightedText, /applied typed AST adaptation, and verified response/);
  assert.match(display.highlightedText, /guardrails refused adaptation/);

  // No transformed arguments or verified response
  assert.equal(display.transformedArgumentsText, null);
  assert.equal(display.verifiedResponseText, null);
  assert.match(display.safetyTagText, /safety_refusal/);

  // Lower panel must display Decision: REFUSE, NOT Decision: AUTO_REPAIR
  assert.doesNotMatch(display.usp2Title, /AUTO_REPAIR/);
  assert.match(display.usp2Title, /Decision: REFUSE/);
  assert.equal(display.usp1StatusText, "✕ blocked");
  assert.equal(display.usp2StatusText, "✕ refusal enforced");
});

test("Scenario 3: SW-03 nesting repair displays verified repair with actual mapping data", () => {
  const backendResponse = {
    status: "verified_success",
    tool_name: "get_user",
    old_version: 1,
    new_version: 2,
    retry_count: 1,
    task_verified: true,
    promoted: true,
    refusal_reason: null,
    transformed_arguments: { target: { id: "456" } },
    response_data: { id: 456, plan: "pro" },
    duration_ms: 26.7,
    error_class: null,
    evidence_summary: [
      "HTTP 422 schema error observed",
      "Fetched authoritative OpenAPI v2 contract from trusted server",
      "Mapped 'user_id' -> 'target.id' (score: 0.73, transform: move)",
    ],
    decision: "AUTO_REPAIR",
    confidence_score: 0.73,
  };

  const display = getProbeDisplayData(backendResponse, "456");

  // Main score box
  assert.equal(display.outcomeType, "verified_repair");
  assert.equal(display.scoreLevelText, "VERIFIED_REPAIR");
  assert.equal(display.scoreBoxClass, "orange");

  // Decision pill
  assert.match(display.decisionPillText, /AUTO_REPAIR — Contract Promoted to v2/);

  // Evidence trail has actual evidence
  assert.match(display.evidenceTrail, /target\.id/);
  assert.match(display.evidenceTrail, /0\.73/);

  // Transformed arguments and response
  assert.equal(display.transformedArgumentsText, JSON.stringify({ target: { id: "456" } }));
  assert.equal(display.verifiedResponseText, JSON.stringify({ id: 456, plan: "pro" }));

  // Lower panel displays mapping and verified auto-repair
  assert.match(display.usp1Title, /target\.id/);
  assert.match(display.usp1Title, /0\.73/);
  assert.equal(display.usp1StatusText, "✓ verified");
  assert.match(display.usp2Title, /AUTO_REPAIR/);
  assert.equal(display.usp2StatusText, "✓ verified");
});
