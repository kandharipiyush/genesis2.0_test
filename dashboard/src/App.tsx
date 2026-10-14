import React, { useEffect, useState } from "react";
import { HeaderNav } from "./components/HeaderNav";
import { Overview } from "./components/Overview";
import { LiveTimeline } from "./components/LiveTimeline";
import { SchemaExplorer } from "./components/SchemaExplorer";
import { BenchmarkView } from "./components/BenchmarkView";
import { SafetyAnalytics } from "./components/SafetyAnalytics";
import { ControlsView } from "./components/ControlsView";
import { UspScenarioView } from "./components/UspScenarioView";
import {
  fetchMetrics,
  fetchTimeline,
  fetchSchemas,
  fetchAnalytics,
  fetchLatestBenchmark,
} from "./api";
import {
  MetricsData,
  AuditEventItem,
  SchemaExplorerData,
  AnalyticsData,
  BenchmarkData,
} from "./types";
import { AlertCircle } from "lucide-react";

export default function App() {
  const [currentTab, setCurrentTab] = useState<string>("controls");
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [schemas, setSchemas] = useState<SchemaExplorerData | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");

  const loadAllData = async () => {
    try {
      setError(null);
      const [m, ev, sc, an, bm] = await Promise.all([
        fetchMetrics().catch(() => null),
        fetchTimeline(60).catch(() => []),
        fetchSchemas().catch(() => null),
        fetchAnalytics().catch(() => null),
        fetchLatestBenchmark().catch(() => null),
      ]);

      if (m) setMetrics(m);
      if (ev) setEvents(ev);
      if (sc) setSchemas(sc);
      if (an) setAnalytics(an);
      if (bm) setBenchmark(bm);

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err: any) {
      setError(err.message || "Failed to connect to SchemaSurgeon Gateway");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="poorva-app-layout">
      {/* Top Command Center Header */}
      <HeaderNav
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        activeVersion={schemas?.active_version || 1}
        lastRefreshed={lastRefreshed}
        onRefresh={loadAllData}
      />

      {/* Main Stone Canvas */}
      <main className="content-canvas">
        {/* Subtle Background Geometric Watermark from reference images */}
        <div className="canvas-watermark" aria-hidden="true">
          <svg width="450" height="450" viewBox="0 0 300 300" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="210" cy="90" r="14" fill="#99958C" opacity="0.4" />
            <circle cx="245" cy="125" r="8" fill="#99958C" opacity="0.3" />
            <path d="M 210,104 C 210,180 160,260 140,290" stroke="#7E7A71" strokeWidth="1.2" opacity="0.35" />
            <path d="M 210,104 C 230,160 260,240 270,290" stroke="#7E7A71" strokeWidth="1.2" opacity="0.35" />
            <circle cx="210" cy="180" r="45" stroke="#7E7A71" strokeWidth="1.2" opacity="0.3" />
            <circle cx="210" cy="190" r="65" fill="#D3CFBE" opacity="0.3" />
            <path d="M 170,160 Q 210,120 250,160" stroke="#7E7A71" strokeWidth="1.2" opacity="0.35" />
          </svg>
        </div>

        {error && (
          <div className="connection-warning-banner">
            <AlertCircle size={16} />
            <span>Connection Warning: {error} (Ensure FastAPI backend is running on port 8000)</span>
          </div>
        )}

        <div className="inner-page-wrapper">
          {currentTab === "overview" && <Overview metrics={metrics} events={events} />}
          {currentTab === "controls" && <ControlsView onRefreshAll={loadAllData} />}
          {currentTab === "timeline" && <LiveTimeline events={events} onRefresh={loadAllData} />}
          {currentTab === "benchmarks" && <BenchmarkView initialBenchmark={benchmark} />}
          {currentTab === "registry" && <SchemaExplorer data={schemas} onRefresh={loadAllData} />}
          {currentTab === "safety" && <SafetyAnalytics analytics={analytics} metrics={metrics} />}
          {(currentTab === "usp-memory" || currentTab === "usp-learning" || currentTab === "usp-trajectories" || currentTab === "patterns") && (
            <UspScenarioView currentTab={currentTab} onRefreshAll={loadAllData} />
          )}
        </div>
      </main>
    </div>
  );
}
