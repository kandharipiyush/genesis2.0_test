import React, { useState } from "react";
import { Search, ChevronDown, ChevronUp, AlertTriangle, ShieldCheck, Zap, Check } from "lucide-react";
import { applyMockMutations, resetMockApi, executeProbeTool } from "../api";

interface UspScenarioViewProps {
  currentTab: string;
  onRefreshAll: () => void;
}

export const UspScenarioView: React.FC<UspScenarioViewProps> = ({ currentTab, onRefreshAll }) => {
  const [activeScenario, setActiveScenario] = useState<number>(3);
  const [searchQuery, setSearchQuery] = useState("get_user");
  const [loading, setLoading] = useState(false);
  const [execResult, setExecResult] = useState<any>(null);
  const [activeFilter, setActiveFilter] = useState("all");

  const scenarios = [
    {
      id: 1,
      title: "Scenario 1: Field Rename (user_id → id)",
      mutation: { rename: true, type_int: false, nest_target: false, require_header: false, wrap_envelope: false },
      desc: "Upstream API renamed 'user_id' to 'id'. Downstream agent continues sending {'user_id': '456'}. Gateway computes Jaccard token similarity 1.00 and builds move adapter.",
      contractHash: "b100048367a77539004a0f6405e955bb314a56971db8116408af93db4d821707",
      targetPath: "/get_user",
      severity: "HIGH",
    },
    {
      id: 2,
      title: 'Scenario 2: Identifier Type Coercion (string "123" → int 123)',
      mutation: { rename: false, type_int: true, nest_target: false, require_header: false, wrap_envelope: false },
      desc: "Upstream API changed parameter type from string to integer. Gateway verifies safe integer conversion without leading zero loss before applying type coercion.",
      contractHash: "6c2efbc21b3664d4b38d61cb589dfd04344933d1b9135a507851eb336c5332f0",
      targetPath: "/get_user",
      severity: "HIGH",
    },
    {
      id: 3,
      title: "Scenario 3: Identifier Nesting (user_id → target.id)",
      mutation: { rename: false, type_int: false, nest_target: true, require_header: false, wrap_envelope: false },
      desc: "Upstream API restructured schema to require a nested object {'target': {'id': ...}}. Gateway detects hierarchy changes, transforms payload to dotted AST path, and validates before dispatch.",
      contractHash: "dbb5f7d375997298b0ba695ae879f8d3e3905d6fbd8ddeddd520b65b27d9f0d7",
      targetPath: "/get_user",
      severity: "CRITICAL",
    },
    {
      id: 4,
      title: "Scenario 4: Required Header Injection (X-Client-Version: 2)",
      mutation: { rename: false, type_int: false, nest_target: false, require_header: true, wrap_envelope: false },
      desc: "Upstream API added required header 'X-Client-Version: 2'. Gateway injects authoritative header from trusted OpenAPI contract without altering client code.",
      contractHash: "44fe3892795a439004a0f6405e955bb314a56971db8116408af93db4d821707",
      targetPath: "/get_user",
      severity: "HIGH",
    },
    {
      id: 5,
      title: "Scenario 5: Response Envelope Unwrap (data wrapper)",
      mutation: { rename: false, type_int: false, nest_target: false, require_header: false, wrap_envelope: true },
      desc: "Upstream API wrapped response in {'data': ...}. Gateway inspects response schema, safely unwraps envelope, and returns original expected payload structure.",
      contractHash: "88ae3892795a439004a0f6405e955bb314a56971db8116408af93db4d821707",
      targetPath: "/get_user",
      severity: "HIGH",
    },
  ];

  const patterns = [
    { code: "DP-01", severity: "CRITICAL", label: "nest_object • target • id", avgMttr: 44.2, tags: ["structural", "nesting", "target.id", "move_ast", "v2_promoted"], reports: 42, sub: "Hierarchy Transformation" },
    { code: "DP-02", severity: "HIGH", label: "rename_field • user_id • id", avgMttr: 38.1, tags: ["rename", "user_id", "id", "similarity_1.0", "move_ast"], reports: 31, sub: "Field Renaming" },
    { code: "DP-03", severity: "HIGH", label: "coerce_type • string • integer", avgMttr: 22.4, tags: ["type_cast", "string_to_int", "safe_coercion", "zero_check"], reports: 19, sub: "Type Adaptation" },
    { code: "DP-04", severity: "HIGH", label: "header_injection • X-Client-Version", avgMttr: 18.5, tags: ["headers", "X-Client-Version", "authoritative", "trusted"], reports: 28, sub: "Header Authentication" },
    { code: "DP-05", severity: "HIGH", label: "response_envelope • data • unwrap", avgMttr: 26.0, tags: ["response", "envelope", "data_wrapper", "unwrap_ast"], reports: 14, sub: "Envelope Handling" },
    { code: "DP-06", severity: "CRITICAL", label: "leading_zero • 00123 • unsafe_refusal", avgMttr: 12.0, tags: ["safety_gate", "lossy_conversion", "hard_refusal", "intent_lock"], reports: 10, sub: "Hard Safety Refusal" },
    { code: "DP-07", severity: "HIGH", label: "anti_flap • rate_limit • window", avgMttr: 8.5, tags: ["anti_flap", "sliding_window", "30s_guard", "suppress_loop"], reports: 7, sub: "Stability Guard" },
    { code: "DP-08", severity: "HIGH", label: "drift_memory • replay_cache • hit", avgMttr: 4.2, tags: ["drift_memory", "hash_lookup", "sub_10ms", "cached_recipe"], reports: 65, sub: "Memory Replay" },
  ];

  const handleRunScenario = async (scen: typeof scenarios[0]) => {
    setActiveScenario(scen.id);
    setLoading(true);
    setExecResult(null);
    try {
      await applyMockMutations(scen.mutation);
      const res = await executeProbeTool({
        arguments: { user_id: "456" },
        intent: {
          task_id: `scenario-${scen.id}`,
          intent: `Execute recovery for ${scen.title}`,
          constraints: { user_id: "456" },
          postconditions: ["plan_exists"],
        },
      });
      setExecResult(res);
      onRefreshAll();
    } catch (e: any) {
      setExecResult({ status: "error", refusal_reason: e.message });
    } finally {
      setLoading(false);
    }
  };

  if (currentTab === "patterns") {
    return (
      <div className="view-container">
        <div className="page-header-row">
          <div>
            <h1 className="page-title">Drift Pattern Clusters & Catalog</h1>
            <p className="page-subtitle">Recurring schema drift patterns cataloged across active tool registry executions.</p>
          </div>
        </div>

        <div className="filter-pill-row">
          <button
            className={`filter-pill-btn ${activeFilter === "all" ? "active" : ""}`}
            onClick={() => setActiveFilter("all")}
          >
            All Drift Patterns (8)
          </button>
          <button
            className={`filter-pill-btn ${activeFilter === "actionable" ? "active" : ""}`}
            onClick={() => setActiveFilter("actionable")}
          >
            Actionable Only (8)
          </button>
        </div>

        <div className="pattern-cards-grid">
          {patterns.map((p) => (
            <div key={p.code} className="pattern-card">
              <div className="pattern-card-header">
                <div className="pattern-card-badges">
                  <span className="pattern-code-badge">{p.code}</span>
                  <span className={`severity-badge ${p.severity.toLowerCase()}`}>{p.severity}</span>
                  <span className="actionable-badge">Active Pattern</span>
                </div>
                <div className="pattern-sif-score">
                  <span className="sif-value">{p.avgMttr.toFixed(1)}ms</span>
                  <span className="sif-label">avg MTTR</span>
                </div>
              </div>

              <h3 className="pattern-title">{p.label}</h3>

              <div className="pattern-tags-row">
                {p.tags.map((t, idx) => (
                  <span key={idx} className="pattern-tag">{t}</span>
                ))}
              </div>

              <div className="pattern-footer">
                <span>{p.reports} recoveries</span>
                <span>{p.sub}</span>
                <span className="expand-link">Deterministic AST</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const selectedScen = scenarios.find((s) => s.id === activeScenario) || scenarios[0];

  return (
    <div className="view-container">
      <div className="usp-banner-tag">USP-5 FEATURE</div>
      <h1 className="page-title">Drift Memory & Deterministic Pattern Replay</h1>
      <p className="page-subtitle">
        Surfaces cross-API contract drift patterns matching AST semantic structure. Reuses verified repair recipes in sub-millisecond time without repeated diagnosis.
      </p>

      {/* 1-Click Guided Scenario Demos */}
      <div className="guided-scenarios-card">
        <div className="guided-scenarios-title">1-CLICK GUIDED SCENARIO DEMOS:</div>
        <div className="scenario-buttons-row">
          {scenarios.map((s) => (
            <button
              key={s.id}
              className={`scenario-btn ${activeScenario === s.id ? "active" : ""}`}
              onClick={() => handleRunScenario(s)}
              disabled={loading}
            >
              {s.title}
            </button>
          ))}
        </div>
      </div>

      {/* Search Memory Bar */}
      <div className="search-memory-row">
        <input
          type="text"
          className="search-memory-input"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search drift memory (e.g. get_user, user_id, target.id)"
        />
        <button className="search-memory-btn" onClick={() => handleRunScenario(selectedScen)}>
          Search Drift Memory
        </button>
      </div>

      {/* Target Contract Drift Under Investigation Card */}
      <div className="target-incident-card">
        <div className="target-incident-label">TARGET CONTRACT DRIFT UNDER INVESTIGATION:</div>
        <p className="target-incident-text">"{selectedScen.desc}"</p>
        <div className="target-incident-meta">
          <span>Target Path: <strong>{selectedScen.targetPath}</strong></span>
          <span>Contract Hash: <strong>{selectedScen.contractHash.substring(0, 16)}...</strong></span>
          <span>Severity: <span className="sif-band-badge">{selectedScen.severity}</span></span>
        </div>
      </div>

      {/* Live Self-Healing Execution Result */}
      {execResult && (
        <div className="live-result-banner-card">
          <div className="result-header-bar">
            <span>Live Self-Healing Result — Scenario: {selectedScen.title}</span>
            <span className="latency-tag">✓ {execResult.duration_ms !== undefined && execResult.duration_ms !== null ? Number(execResult.duration_ms).toFixed(1) : "0.0"}ms</span>
          </div>

          <div className="result-body-grid">
            <div className={`score-callout-block ${execResult.status === "verified_success" ? "success" : "refused"}`}>
              <div className="score-main-title">{execResult.status ? execResult.status.toUpperCase() : "VERIFIED_SUCCESS"}</div>
              <div className="score-sub-label">MTTR: {execResult.duration_ms !== undefined && execResult.duration_ms !== null ? Number(execResult.duration_ms).toFixed(1) : "0.0"} ms</div>
              <div className="score-detail-pill">
                {execResult.status === "verified_success"
                  ? (execResult.promoted || (execResult.retry_count && execResult.retry_count > 0) || execResult.decision === "AUTO_REPAIR"
                      ? `AUTO_REPAIR — Schema v${execResult.new_version || 2} Verified`
                      : `DIRECT_SUCCESS — Schema v${execResult.old_version || 1} Validated`)
                  : (execResult.decision === "REFUSE" || execResult.status === "refused"
                      ? "REFUSED — Safety Guard Enforced"
                      : (execResult.status || "ERROR").toUpperCase())}
              </div>
            </div>

            <div className="result-details-col">
              {execResult.refusal_reason && (
                <div className="why-uncertain-banner" style={{ background: "var(--accent-red-soft)", color: "var(--accent-red)", borderColor: "var(--accent-red-border)", marginBottom: "8px" }}>
                  <strong>Refusal reason:</strong> {execResult.refusal_reason}
                </div>
              )}

              <div className="why-uncertain-banner">
                <strong>Evidence trail:</strong>{" "}
                {execResult.evidence_summary && execResult.evidence_summary.length > 0
                  ? execResult.evidence_summary.join(" • ")
                  : execResult.status === "verified_success" && !execResult.promoted && !execResult.retry_count
                  ? "No schema drift detected. Upstream API responded directly with HTTP 200."
                  : "No drift evidence recorded."}
              </div>

              {execResult.transformed_arguments && (
                <div className="evidence-code-row">
                  <span className="code-label">Transformed Arguments:</span>
                  <code className="code-val">{JSON.stringify(execResult.transformed_arguments)}</code>
                </div>
              )}

              {execResult.response_data && (
                <div className="evidence-code-row">
                  <span className="code-label">Response Data:</span>
                  <code className="code-val">{JSON.stringify(execResult.response_data)}</code>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
