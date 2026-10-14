import React, { useState, useEffect } from "react";
import { Sliders, RefreshCw, Zap, CheckCircle2, Play, Activity, AlertTriangle, ShieldCheck } from "lucide-react";
import { triggerProactiveCheck, applyMockMutations, resetMockApi, getMockState, executeProbeTool } from "../api";
import { getProbeDisplayData } from "./probeResultFormat";

interface ControlsViewProps {
  onRefreshAll: () => void;
}

export const ControlsView: React.FC<ControlsViewProps> = ({ onRefreshAll }) => {
  const [mutations, setMutations] = useState({
    rename: false,
    type_int: false,
    nest_target: false,
    require_header: false,
    wrap_envelope: false,
  });

  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [probeUserId, setProbeUserId] = useState("456");
  const [probePayload, setProbePayload] = useState(
    JSON.stringify({ tool: "get_user", method: "POST", path: "/get_user", arguments: { user_id: "456" } }, null, 2)
  );
  const [probeResult, setProbeResult] = useState<any>(null);

  useEffect(() => {
    getMockState()
      .then((data) => {
        if (data && data.mutations) setMutations(data.mutations);
      })
      .catch(() => {});
  }, []);

  const handleApplyMutations = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      await applyMockMutations(mutations);
      setStatusMsg("Mock API mutations applied successfully! Target OpenAPI schema has drifted on port 8001.");
      onRefreshAll();
    } catch (e: any) {
      setStatusMsg(`Error applying mutations: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResetMock = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      await resetMockApi();
      setMutations({
        rename: false,
        type_int: false,
        nest_target: false,
        require_header: false,
        wrap_envelope: false,
      });
      setStatusMsg("Mock API and Gateway registry reset back to clean v1 initial contract.");
      onRefreshAll();
    } catch (e: any) {
      setStatusMsg(`Error resetting: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunProbe = async () => {
    setLoading(true);
    setProbeResult(null);
    try {
      const res = await executeProbeTool({
        arguments: { user_id: probeUserId },
        intent: {
          task_id: "probe-ui",
          intent: `Retrieve subscription plan for user ${probeUserId}`,
          constraints: { user_id: probeUserId },
          postconditions: ["plan_exists"],
        },
      });
      setProbeResult(res);
      onRefreshAll();
    } catch (e: any) {
      setProbeResult({ status: "error", refusal_reason: e.message });
    } finally {
      setLoading(false);
    }
  };

  const handleProactiveCheck = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      const res = await triggerProactiveCheck();
      if (res.drift_detected) {
        setStatusMsg(`Proactive Monitor: Breaking drift detected and ${res.promoted ? "promoted to v2" : "staged"}!`);
      } else {
        setStatusMsg("Proactive Monitor: No breaking contract drift detected on target API.");
      }
      onRefreshAll();
    } catch (e: any) {
      setStatusMsg(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const probeDisplay = probeResult ? getProbeDisplayData(probeResult, probeUserId) : null;

  return (
    <div className="view-container">
      {/* Header Row */}
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Interactive Tool Probe & Mutation Controls</h1>
          <p className="page-subtitle">Simulate upstream OpenAPI contract drift and observe real-time deterministic self-healing.</p>
        </div>
        <div className="header-actions-group">
          <button className="btn-export-excel" onClick={handleResetMock} title="Reset upstream contract back to v1">
            <RefreshCw size={14} />
            <span>Reset API to v1 State</span>
          </button>
          <button className="btn-export-excel gold" onClick={handleProactiveCheck} title="Run Proactive Drift Monitor">
            <Zap size={14} />
            <span>Proactive Monitor</span>
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="live-status-alert">
          <CheckCircle2 size={16} />
          <span>{statusMsg}</span>
        </div>
      )}

      {/* Dark Try It Yourself Box - Pure SchemaSurgeon Tool Probe */}
      <div className="try-it-dark-card">
        <div className="try-it-header">
          <span className="try-it-title">Try it yourself — Interactive Self-Healing Tool Probe</span>
        </div>
        <p className="try-it-subtitle">
          Send a client request with any User ID (e.g. 123, 456, 789). If the upstream API has drifted, SchemaSurgeon will intercept the HTTP 422 error, diagnose the new OpenAPI v2 contract, transform the payload deterministically, verify the response, and return the result.
        </p>

        <textarea
          className="try-it-textarea"
          value={probePayload}
          onChange={(e) => setProbePayload(e.target.value)}
          rows={4}
        />

        <div className="try-it-bottom-bar">
          <div className="try-it-inputs-row">
            <select
              className="try-it-select"
              value="POST /get_user"
              disabled
            >
              <option value="POST /get_user">POST /get_user (User Plan)</option>
            </select>

            <input
              type="text"
              className="try-it-site-input"
              value={probeUserId}
              onChange={(e) => {
                setProbeUserId(e.target.value);
                setProbePayload(
                  JSON.stringify({ tool: "get_user", method: "POST", path: "/get_user", arguments: { user_id: e.target.value } }, null, 2)
                );
              }}
              placeholder="User ID (e.g. 123, 456, 789, 00123)"
            />
          </div>

          <div className="try-it-btn-group">
            <button className="btn-classify-cyan" onClick={handleRunProbe} disabled={loading}>
              <span>Run Live Tool Probe →</span>
            </button>
            <span className="latency-pill">
              ✓ {probeResult?.duration_ms !== undefined && probeResult?.duration_ms !== null ? Number(probeResult.duration_ms).toFixed(1) : "0.0"}ms
            </span>
          </div>
        </div>
      </div>

      {/* Live Gateway Execution Result Card */}
      {probeDisplay && (
        <div className="live-result-card">
          <div className="live-result-header-bar">
            <span>Live Gateway Execution Result — Tool: get_user (User ID: {probeUserId})</span>
          </div>

          <div className="live-result-body">
            <div className="score-and-why-row">
              <div className={`main-score-box ${probeDisplay.scoreBoxClass}`}>
                <div className="score-level-text">
                  {probeDisplay.scoreLevelText}
                </div>
                <div className="score-sub-text">
                  {probeDisplay.latencyLabel}
                </div>
              </div>

              <div className="score-summary-text">
                <div style={{ fontWeight: "700", fontSize: "15px", color: "var(--text-dark-primary)" }}>
                  {probeDisplay.summaryTitle}
                </div>
                <div className={probeDisplay.decisionPillClass}>
                  {probeDisplay.decisionPillText}
                </div>
              </div>
            </div>

            {probeDisplay.refusalReason && (
              <div className="why-uncertain-box red">
                <span style={{ fontWeight: "700" }}>Refusal Reason:</span> {probeDisplay.refusalReason}
              </div>
            )}

            <div className={`why-uncertain-box ${probeDisplay.isEvidenceGreen ? "green" : ""}`}>
              <span style={{ fontWeight: "700" }}>Evidence Trail:</span>{" "}
              {probeDisplay.evidenceTrail}
            </div>

            {/* Transformed Payload and Result Section */}
            <div className="keyword-evidence-section">
              <div className="section-label">Payload Transformation & Verification Details</div>
              <div className="highlighted-text-box">
                {probeDisplay.highlightedText}
              </div>
              <div className="rule-tags-row">
                <span className="tag-pill yellow">Original Input: {probeDisplay.originalInput}</span>
                {probeDisplay.transformedArgumentsText && (
                  <span className="tag-pill cyan">
                    Transformed Arguments: {probeDisplay.transformedArgumentsText}
                  </span>
                )}
                {probeDisplay.verifiedResponseText && (
                  <span className="tag-pill green">
                    Verified Response: {probeDisplay.verifiedResponseText}
                  </span>
                )}
                {probeDisplay.safetyTagText && (
                  <span className="tag-pill red">
                    {probeDisplay.safetyTagText}
                  </span>
                )}
              </div>
            </div>

            {/* Life-Saving Rule / USP Invariant Matches */}
            <div className="lsr-matches-section">
              <div className="section-label">Active SchemaSurgeon Invariant Guarantees</div>
              <div className="lsr-match-row">
                <div className="lsr-left">
                  <span className="tag-pill yellow bold">USP-1</span>
                  <span className="lsr-name">{probeDisplay.usp1Title}</span>
                </div>
                <div className="lsr-right">
                  <span className={probeDisplay.usp1StatusClass}>{probeDisplay.usp1StatusText}</span>
                  <span className="ml-pct">{probeDisplay.usp1MetricText}</span>
                </div>
              </div>

              <div className="lsr-match-row">
                <div className="lsr-left">
                  <span className="tag-pill cyan bold">USP-2</span>
                  <span className="lsr-name">{probeDisplay.usp2Title}</span>
                </div>
                <div className="lsr-right">
                  <span className={probeDisplay.usp2StatusClass}>{probeDisplay.usp2StatusText}</span>
                  <span className="ml-pct">{probeDisplay.usp2TokensText}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Target API Mutation Simulator - Clean Pattern Explorer Card Style */}
      <div className="card" style={{ marginTop: "16px" }}>
        <div className="card-title">
          <span>Live Mock API Mutation Simulator (5 Independent Switches)</span>
          <span className="severity-badge high">Port 8001 Live</span>
        </div>
        <p style={{ fontSize: "13px", color: "var(--text-dark-secondary)", marginBottom: "20px" }}>
          Toggle individual contract mutations to test SchemaSurgeon's real-time drift diagnosis and safe self-healing.
        </p>

        <div className="switches-grid">
          {/* Switch 1 */}
          <label className="switch-card">
            <div className="switch-card-header">
              <span className="switch-code">SW-01</span>
              <span className="actionable-badge">Active Schema</span>
            </div>
            <input
              type="checkbox"
              checked={mutations.rename}
              onChange={(e) => setMutations({ ...mutations, rename: e.target.checked })}
            />
            <div className="switch-card-body">
              <div className="switch-title">Switch 1: Rename Field</div>
              <div className="switch-sub">user_id &rarr; id</div>
            </div>
          </label>

          {/* Switch 2 */}
          <label className="switch-card">
            <div className="switch-card-header">
              <span className="switch-code">SW-02</span>
              <span className="actionable-badge">Active Schema</span>
            </div>
            <input
              type="checkbox"
              checked={mutations.type_int}
              onChange={(e) => setMutations({ ...mutations, type_int: e.target.checked })}
            />
            <div className="switch-card-body">
              <div className="switch-title">Switch 2: Identifier Type</div>
              <div className="switch-sub">string "123" &rarr; integer 123</div>
            </div>
          </label>

          {/* Switch 3 */}
          <label className="switch-card">
            <div className="switch-card-header">
              <span className="switch-code">SW-03</span>
              <span className="severity-badge critical">CRITICAL DRIFT</span>
            </div>
            <input
              type="checkbox"
              checked={mutations.nest_target}
              onChange={(e) => setMutations({ ...mutations, nest_target: e.target.checked })}
            />
            <div className="switch-card-body">
              <div className="switch-title">Switch 3: Nesting Identifier</div>
              <div className="switch-sub">user_id &rarr; target.id</div>
            </div>
          </label>

          {/* Switch 4 */}
          <label className="switch-card">
            <div className="switch-card-header">
              <span className="switch-code">SW-04</span>
              <span className="actionable-badge">Active Schema</span>
            </div>
            <input
              type="checkbox"
              checked={mutations.require_header}
              onChange={(e) => setMutations({ ...mutations, require_header: e.target.checked })}
            />
            <div className="switch-card-body">
              <div className="switch-title">Switch 4: Require Header</div>
              <div className="switch-sub">X-Client-Version: 2</div>
            </div>
          </label>

          {/* Switch 5 */}
          <label className="switch-card">
            <div className="switch-card-header">
              <span className="switch-code">SW-05</span>
              <span className="actionable-badge">Active Schema</span>
            </div>
            <input
              type="checkbox"
              checked={mutations.wrap_envelope}
              onChange={(e) => setMutations({ ...mutations, wrap_envelope: e.target.checked })}
            />
            <div className="switch-card-body">
              <div className="switch-title">Switch 5: Response Envelope</div>
              <div className="switch-sub">Wrap in &#123;"data": ...&#125;</div>
            </div>
          </label>
        </div>

        <div style={{ display: "flex", gap: "12px", marginTop: "20px" }}>
          <button className="btn-export-excel gold" onClick={handleApplyMutations} disabled={loading}>
            <Zap size={16} />
            <span>Apply Selected Mutations</span>
          </button>
          <button className="btn-export-excel" onClick={handleResetMock} disabled={loading}>
            <RefreshCw size={16} />
            <span>Reset API to v1 Initial State</span>
          </button>
        </div>
      </div>
    </div>
  );
};
