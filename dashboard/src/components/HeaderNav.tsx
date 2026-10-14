import React, { useState } from "react";
import { Sparkles, RefreshCw, Layers, ShieldCheck, Cpu, ChevronUp, ChevronDown, Activity, Sliders, History, BarChart2 } from "lucide-react";

interface HeaderNavProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  activeVersion: number;
  lastRefreshed: string;
  onRefresh: () => void;
}

export const HeaderNav: React.FC<HeaderNavProps> = ({
  currentTab,
  onSelectTab,
  activeVersion,
  lastRefreshed,
  onRefresh,
}) => {
  const [selectedEnv, setSelectedEnv] = useState("Gateway Core");
  const [compactNav, setCompactNav] = useState(false);

  return (
    <header className="top-command-header">
      {/* Top Banner Row */}
      <div className="header-top-row">
        <div className="header-brand-group">
          <div className="header-logo-icon">
            <Sparkles size={18} color="#000000" />
          </div>
          <span className="header-brand-title">SCHEMASURGEON</span>
          <span className="role-pill-badge">ROLE: GATEWAY_ADMIN</span>
          <span className="version-pill-badge">ACTIVE TOOL: get_user v{activeVersion}</span>
        </div>

        <div className="header-quick-switches">
          <span className="quick-switch-label">Target Environment:</span>
          <button
            className={`switch-pill-btn ${selectedEnv === "Gateway Core" ? "active-gold" : ""}`}
            onClick={() => setSelectedEnv("Gateway Core")}
          >
            Gateway :8000
          </button>
          <button
            className={`switch-pill-btn ${selectedEnv === "Mock API" ? "active-gold" : ""}`}
            onClick={() => {
              setSelectedEnv("Mock API");
              window.open("http://127.0.0.1:8001/docs", "_blank");
            }}
          >
            Mock API :8001
          </button>
          <button
            className={`switch-pill-btn ${selectedEnv === "LangGraph" ? "active-gold" : ""}`}
            onClick={() => setSelectedEnv("LangGraph")}
          >
            LangGraph Rebind
          </button>
          <button
            className="switch-pill-btn"
            onClick={() => window.open("http://127.0.0.1:8001/openapi.json", "_blank")}
            title="Inspect Live Upstream OpenAPI Specification"
          >
            OpenAPI Spec
          </button>

          <button
            className="compact-nav-btn"
            onClick={() => setCompactNav(!compactNav)}
          >
            {compactNav ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
            <span>{compactNav ? "Expand" : "Compact"}</span>
          </button>
        </div>
      </div>

      {/* Navigation Categories Row */}
      {!compactNav && (
        <div className="header-categories-row">
          {/* Category 1: Core Gateway Workspace */}
          <div className="category-group">
            <span className="category-label">CORE GATEWAY WORKSPACE:</span>
            <div className="category-tabs">
              <button
                className={`category-tab-btn ${currentTab === "overview" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("overview")}
              >
                System Overview
              </button>
              <button
                className={`category-tab-btn ${currentTab === "controls" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("controls")}
              >
                Interactive Tool Probe
              </button>
              <button
                className={`category-tab-btn ${currentTab === "timeline" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("timeline")}
              >
                Recovery Timeline <span className="tab-pill-badge">LIVE</span>
              </button>
              <button
                className={`category-tab-btn ${currentTab === "benchmarks" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("benchmarks")}
              >
                Benchmarks & Latency <span className="tab-pill-badge">0-TOK</span>
              </button>
            </div>
          </div>

          {/* Category 2: Intelligence & USPs */}
          <div className="category-group">
            <span className="category-label">INTELLIGENCE & USPS:</span>
            <div className="category-tabs">
              <button
                className={`category-tab-btn ${currentTab === "usp-memory" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("usp-memory")}
              >
                Drift Memory <span className="tab-pill-badge">USP-5</span>
              </button>
              <button
                className={`category-tab-btn ${currentTab === "usp-learning" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("usp-learning")}
              >
                Field Solver <span className="tab-pill-badge">USP-1</span>
              </button>
              <button
                className={`category-tab-btn ${currentTab === "usp-trajectories" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("usp-trajectories")}
              >
                Safety Gate <span className="tab-pill-badge">USP-2</span>
              </button>
              <button
                className={`category-tab-btn ${currentTab === "patterns" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("patterns")}
              >
                Drift Pattern Clusters
              </button>
            </div>
          </div>

          {/* Category 3: Governance & MLOps */}
          <div className="category-group">
            <span className="category-label">GOVERNANCE & MLOPS:</span>
            <div className="category-tabs">
              <button
                className={`category-tab-btn ${currentTab === "registry" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("registry")}
              >
                Schema Explorer <span className="tab-pill-badge">v{activeVersion}</span>
              </button>
              <button
                className={`category-tab-btn ${currentTab === "safety" ? "active-pill" : ""}`}
                onClick={() => onSelectTab("safety")}
              >
                Safety Invariants
              </button>
              <button
                className="category-tab-btn refresh-tab-btn"
                onClick={onRefresh}
                title="Synchronize live gateway state"
              >
                <RefreshCw size={12} />
                <span>Sync</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
