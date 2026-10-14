import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ShieldCheck, AlertOctagon, XCircle, FileWarning } from "lucide-react";
import { AnalyticsData, MetricsData } from "../types";

interface SafetyAnalyticsProps {
  analytics: AnalyticsData | null;
  metrics: MetricsData | null;
}

export const SafetyAnalytics: React.FC<SafetyAnalyticsProps> = ({ analytics, metrics }) => {
  const decisions = analytics?.decisions || {};
  const decisionData = [
    { name: "AUTO_REPAIR", count: decisions["AUTO_REPAIR"] || 0, color: "var(--green-primary)" },
    { name: "REQUIRES_APPROVAL", count: decisions["REQUIRES_APPROVAL"] || 0, color: "var(--amber-primary)" },
    { name: "REFUSE", count: decisions["REFUSE"] || 0, color: "var(--red-primary)" },
    { name: "SUPPRESSED", count: decisions["SUPPRESSED"] || 0, color: "var(--purple-primary)" },
  ];

  const hardSafetyRules = [
    {
      title: "Leading-Zero Conversion Refusal",
      status: "Enforced",
      rule: "Prevents '00123' -> 123 conversion to prevent destructive entity key loss.",
      count: metrics?.unsafe_repairs_refused || 0,
    },
    {
      title: "Ambiguous Target Field Rejection",
      status: "Enforced",
      rule: "Requires minimum confidence 0.50 and unique-match margin 0.15; rejects ambiguous targets.",
      count: "Active",
    },
    {
      title: "Required Header Provenance Gate",
      status: "Enforced",
      rule: "Refuses newly required headers lacking authoritative values in gateway configuration.",
      count: "Active",
    },
    {
      title: "Intent Lock: Wrong-Target HTTP 200 Rejection",
      status: "Enforced",
      rule: "Detects technically successful 200 responses returning mismatched entity IDs and rejects them.",
      count: "Active",
    },
    {
      title: "Anti-Flap Loop Prevention",
      status: "Enforced",
      rule: "Restricts re-healing to at most 1 recovery per tool per 30-second window.",
      count: "Active",
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Decisions Distribution Bar Chart */}
      <div className="card">
        <div className="card-title">
          <span>Confidence Gate Decisions Breakdown</span>
          <span style={{ fontSize: "12px", color: "var(--text-light)" }}>Automated Safety Policy Enforcement</span>
        </div>

        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={decisionData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--bg-surface)",
                  borderColor: "var(--border-subtle)",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="count" name="Decision Count" radius={[4, 4, 0, 0]}>
                {decisionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Mandatory Hard Safety Checks Audit */}
      <div className="card">
        <div className="card-title">
          <span>Non-Negotiable Hard Safety Gates (Mandatory Invariants)</span>
          <span className="badge badge-success">Zero Tolerated Violations</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {hardSafetyRules.map((rule, idx) => (
            <div
              key={idx}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 18px",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--bg-surface)",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: "600", fontSize: "14px" }}>
                  <ShieldCheck size={16} color="var(--green-primary)" />
                  <span>{rule.title}</span>
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  {rule.rule}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span className="badge badge-success">{rule.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
