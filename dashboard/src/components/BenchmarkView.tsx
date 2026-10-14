import React, { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Play, RotateCcw, CheckCircle2, TrendingUp, Cpu, Clock } from "lucide-react";
import { BenchmarkData } from "../types";
import { runBenchmark } from "../api";

interface BenchmarkViewProps {
  initialBenchmark: BenchmarkData | null;
}

export const BenchmarkView: React.FC<BenchmarkViewProps> = ({ initialBenchmark }) => {
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(initialBenchmark);
  const [selectedMutation, setSelectedMutation] = useState<string>("all");
  const [trials, setTrials] = useState<number>(2);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleLaunch = async () => {
    setRunning(true);
    setError(null);
    try {
      const data = await runBenchmark(selectedMutation, trials);
      setBenchmark(data);
    } catch (e: any) {
      setError(e.message || "Failed to run benchmark");
    } finally {
      setRunning(false);
    }
  };

  // Build chart comparison data
  const comparisonData = React.useMemo(() => {
    if (!benchmark || !benchmark.scenarios) return [];
    return Object.entries(benchmark.scenarios).map(([scenName, res]) => ({
      scenario: scenName,
      Baseline: res.baseline_success_rate,
      SchemaSurgeon: res.healer_success_rate,
      BaselineLatency: res.baseline_mean_ms,
      HealerLatency: res.healer_mean_ms,
      trials: res.trials,
    }));
  }, [benchmark]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Benchmark Control Panel */}
      <div className="card">
        <div className="card-title">
          <span>Real HTTP Benchmark Suite: SchemaSurgeon vs Baseline Agent</span>
          <span className="badge badge-info">Fair Side-by-Side Evaluation</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap", marginTop: "12px" }}>
          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Mutation Class
            </label>
            <select
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
                fontSize: "13px",
                backgroundColor: "var(--bg-surface)",
              }}
              value={selectedMutation}
              onChange={(e) => setSelectedMutation(e.target.value)}
              disabled={running}
            >
              <option value="all">All Mutation Classes (Compound Evaluation)</option>
              <option value="rename">Field Rename (user_id &rarr; id)</option>
              <option value="type_int">Type Coercion (string &rarr; int)</option>
              <option value="nesting">Nesting (user_id &rarr; target.id)</option>
              <option value="require_header">Required Header (X-Client-Version)</option>
              <option value="wrap_envelope">Response Envelope (data wrapper)</option>
              <option value="compound">Compound Drift (all 5 mutations combined)</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Trials per Class
            </label>
            <select
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
                fontSize: "13px",
                backgroundColor: "var(--bg-surface)",
              }}
              value={trials}
              onChange={(e) => setTrials(Number(e.target.value))}
              disabled={running}
            >
              <option value={1}>1 Trial (Quick Verification)</option>
              <option value={2}>2 Trials (Balanced)</option>
              <option value={3}>3 Trials (Standard Statistical Sample)</option>
              <option value={5}>5 Trials (High Confidence)</option>
            </select>
          </div>

          <div style={{ alignSelf: "flex-end" }}>
            <button
              className="btn btn-primary"
              style={{ padding: "9px 20px" }}
              onClick={handleLaunch}
              disabled={running}
            >
              {running ? (
                <>
                  <RotateCcw size={16} className="pulse-dot" />
                  <span>Executing Benchmark Trials...</span>
                </>
              ) : (
                <>
                  <Play size={16} />
                  <span>Launch Live Benchmark</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ marginTop: "12px", padding: "10px", backgroundColor: "var(--red-soft)", color: "var(--red-primary)", borderRadius: "var(--radius-sm)", fontSize: "13px" }}>
            {error}
          </div>
        )}
      </div>

      {/* Summary KPI Cards */}
      {benchmark && benchmark.summary && (
        <div className="grid-cards">
          <div className="kpi-card">
            <div className="kpi-header">
              <span>Zero-Touch Adaptation</span>
              <TrendingUp size={18} color="var(--green-primary)" />
            </div>
            <div className="kpi-value" style={{ color: "var(--green-primary)" }}>
              {benchmark.summary.healer_overall_adaptation_rate}%
            </div>
            <div className="kpi-subtext">Baseline: {benchmark.summary.baseline_overall_success_rate}%</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span>Mean Recovery Time (MTTR)</span>
              <Clock size={18} color="var(--blue-primary)" />
            </div>
            <div className="kpi-value">{benchmark.summary.healer_mean_mttr_ms} ms</div>
            <div className="kpi-subtext">P95: {benchmark.summary.healer_p95_mttr_ms} ms</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span>Token Overhead</span>
              <Cpu size={18} color="var(--text-muted)" />
            </div>
            <div className="kpi-value" style={{ fontSize: "18px", color: "var(--green-primary)" }}>
              {benchmark.summary.token_overhead}
            </div>
            <div className="kpi-subtext">Zero extra model prompt tokens</div>
          </div>

          <div className="kpi-card">
            <div className="kpi-header">
              <span>Safe-Refusal Accuracy</span>
              <CheckCircle2 size={18} color="var(--green-primary)" />
            </div>
            <div className="kpi-value">{benchmark.summary.safe_refusal_accuracy}</div>
            <div className="kpi-subtext">Incorrect repairs: {benchmark.summary.incorrect_repair_rate}</div>
          </div>
        </div>
      )}

      {/* Graph: Baseline vs SchemaSurgeon Bar Chart */}
      <div className="card">
        <div className="card-title">
          <span>Success Rate Comparison: Baseline Agent vs SchemaSurgeon</span>
          <span style={{ fontSize: "12px", color: "var(--text-light)" }}>Measured on Real HTTPX / Uvicorn</span>
        </div>

        {comparisonData.length > 0 ? (
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={comparisonData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="scenario" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--bg-surface)",
                    borderColor: "var(--border-subtle)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                />
                <Legend />
                <Bar dataKey="Baseline" fill="var(--red-primary)" name="Baseline Agent (%)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="SchemaSurgeon" fill="var(--green-primary)" name="SchemaSurgeon Healer (%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div style={{ padding: "60px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            No benchmark results yet. Select a mutation class and click "Launch Live Benchmark" above.
          </div>
        )}
      </div>

      {/* Detailed Scenario Breakdown Table */}
      {comparisonData.length > 0 && (
        <div className="card">
          <div className="card-title">
            <span>Scenario Performance Breakdown</span>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Mutation Scenario</th>
                  <th>Trials</th>
                  <th>Baseline Success</th>
                  <th>SchemaSurgeon Success</th>
                  <th>Baseline Latency</th>
                  <th>Healer MTTR</th>
                </tr>
              </thead>
              <tbody>
                {comparisonData.map((row, i) => (
                  <tr key={i}>
                    <td className="font-mono" style={{ fontWeight: "600" }}>{row.scenario}</td>
                    <td>{row.trials}</td>
                    <td style={{ color: "var(--red-primary)", fontWeight: "600" }}>{row.Baseline}%</td>
                    <td style={{ color: "var(--green-primary)", fontWeight: "600" }}>{row.SchemaSurgeon}%</td>
                    <td>{row.BaselineLatency} ms</td>
                    <td style={{ fontWeight: "600" }}>{row.HealerLatency} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
