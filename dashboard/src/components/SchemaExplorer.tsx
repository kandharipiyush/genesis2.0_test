import React, { useState } from "react";
import { Layers, ShieldAlert, Check, Copy, ArrowRight } from "lucide-react";
import { SchemaExplorerData, ToolContractItem } from "../types";

interface SchemaExplorerProps {
  data: SchemaExplorerData | null;
  onRefresh: () => void;
}

export const SchemaExplorer: React.FC<SchemaExplorerProps> = ({ data, onRefresh }) => {
  const [selectedVersion, setSelectedVersion] = useState<number>(1);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  if (!data) {
    return <div className="card">Loading schema registry...</div>;
  }

  const activeContract = data.active_contract;
  const history = data.history || [];
  const quarantined = data.quarantined || [];

  // Find selected contract from history
  const selectedContract = history.find((c) => c.version === selectedVersion) || activeContract;

  // Compute differences between v1 and selectedContract
  const v1Contract = history.find((c) => c.version === 1);

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Active Contract Header */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: "700" }}>Tool: {data.active_tool}</h3>
              <span className="badge badge-success">Active: v{data.active_version}</span>
            </div>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
              Target Endpoint: <code className="font-mono">{activeContract?.path || "/get_user"}</code> via{" "}
              <strong>{activeContract?.method || "POST"}</strong>
            </p>
          </div>

          <button className="btn btn-secondary" onClick={onRefresh}>
            Refresh Registry
          </button>
        </div>

        {/* Contract Hashes */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <div style={{ padding: "12px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
            <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>
              Canonical Contract Hash (SHA-256)
            </span>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "4px" }}>
              <code className="font-mono" style={{ fontSize: "12px", color: "var(--text-main)" }}>
                {activeContract?.contract_hash || "None"}
              </code>
              <button
                className="btn btn-secondary"
                style={{ padding: "3px 6px" }}
                onClick={() => copyHash(activeContract?.contract_hash || "")}
              >
                {copiedHash ? <Check size={12} color="var(--green-primary)" /> : <Copy size={12} />}
              </button>
            </div>
          </div>

          <div style={{ padding: "12px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
            <span style={{ fontSize: "12px", color: "var(--text-muted)", display: "block" }}>
              Target Server & Configured Headers
            </span>
            <div style={{ marginTop: "4px", fontSize: "13px" }}>
              <span>{activeContract?.server_url || "http://127.0.0.1:8001"}</span>
              <span style={{ marginLeft: "12px", color: "var(--text-muted)" }}>
                Headers: {JSON.stringify(activeContract?.required_headers || {})}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Version Tabs and Side-by-Side Schema Explorer */}
      <div className="card">
        <div className="card-title">
          <span>Side-by-Side Schema Diff & Evolution</span>
          <div style={{ display: "flex", gap: "6px" }}>
            {history.map((ver) => (
              <button
                key={ver.version}
                className={`btn ${selectedVersion === ver.version ? "btn-primary" : "btn-secondary"}`}
                style={{ padding: "4px 10px", fontSize: "12px" }}
                onClick={() => setSelectedVersion(ver.version)}
              >
                Version {ver.version} {ver.version === data.active_version && "(Active)"}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {/* Base Version Schema */}
          <div>
            <div style={{ fontSize: "13px", fontWeight: "600", marginBottom: "8px", color: "var(--text-muted)" }}>
              Initial Schema (v1 Base)
            </div>
            <pre
              style={{
                backgroundColor: "var(--bg-hover)",
                padding: "16px",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                height: "320px",
                overflowY: "auto",
                border: "1px solid var(--border-subtle)",
              }}
            >
              {JSON.stringify(v1Contract?.request_schema || {}, null, 2)}
            </pre>
          </div>

          {/* Selected/Promoted Schema */}
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--blue-primary)" }}>
                Selected Contract (v{selectedContract?.version || 1})
              </span>
              <span className="badge badge-info">
                {selectedContract?.version === 1 ? "Original" : "Self-Healed & Promoted"}
              </span>
            </div>
            <pre
              style={{
                backgroundColor: "var(--bg-hover)",
                padding: "16px",
                borderRadius: "var(--radius-sm)",
                fontSize: "12px",
                height: "320px",
                overflowY: "auto",
                border: "1px solid var(--border-subtle)",
              }}
            >
              {JSON.stringify(selectedContract?.request_schema || {}, null, 2)}
            </pre>
          </div>
        </div>
      </div>

      {/* Quarantined Candidates Section */}
      <div className="card">
        <div className="card-title">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <ShieldAlert size={16} color="var(--red-primary)" />
            <span>Quarantined Candidate Schemas</span>
          </div>
          <span className="badge badge-danger">{quarantined.length} Quarantined</span>
        </div>

        {quarantined.length === 0 ? (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            No quarantined candidates. All generated repairs met hard safety and task verification criteria.
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Target Version</th>
                  <th>Quarantine Reason</th>
                  <th>Candidate Adapter</th>
                </tr>
              </thead>
              <tbody>
                {quarantined.map((item, idx) => (
                  <tr key={idx}>
                    <td className="font-mono">v{item.candidate?.target_version || "?"}</td>
                    <td style={{ color: "var(--red-primary)", fontWeight: "500" }}>{item.reason}</td>
                    <td className="font-mono" style={{ fontSize: "11px" }}>
                      {JSON.stringify(item.candidate?.request_adapter || [])}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
