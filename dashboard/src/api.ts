import {
  MetricsData,
  AuditEventItem,
  SchemaExplorerData,
  AnalyticsData,
  BenchmarkData,
} from "./types";

const API_BASE = "";

export async function fetchMetrics(): Promise<MetricsData> {
  const res = await fetch(`${API_BASE}/api/dashboard/metrics?_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchTimeline(limit = 60): Promise<AuditEventItem[]> {
  const res = await fetch(`${API_BASE}/api/dashboard/timeline?limit=${limit}&_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch timeline");
  const data = await res.json();
  return data.events || [];
}

export async function fetchSchemas(): Promise<SchemaExplorerData> {
  const res = await fetch(`${API_BASE}/api/dashboard/schemas?_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch schemas");
  return res.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${API_BASE}/api/dashboard/analytics?_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export async function fetchLatestBenchmark(): Promise<BenchmarkData> {
  const res = await fetch(`${API_BASE}/api/dashboard/benchmark/latest?_t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch benchmark");
  return res.json();
}

export async function runBenchmark(mutationType: string, trials: number): Promise<BenchmarkData> {
  const res = await fetch(`${API_BASE}/api/dashboard/benchmark/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mutation_type: mutationType,
      trials_per_class: trials,
    }),
  });
  if (!res.ok) throw new Error("Failed to execute benchmark");
  return res.json();
}

export async function triggerProactiveCheck(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/monitor/run`, { method: "POST" });
  if (!res.ok) throw new Error("Proactive monitor trigger failed");
  return res.json();
}

export async function getMockState(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/dashboard/mock/state`);
  if (!res.ok) throw new Error("Failed to fetch mock state");
  return res.json();
}

export async function applyMockMutations(mutations: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/dashboard/mock/mutate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mutations),
  });
  if (!res.ok) throw new Error("Failed to apply mock mutations");
  return res.json();
}

export async function resetMockApi(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/dashboard/mock/reset`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset mock API");
  return res.json();
}

export async function executeProbeTool(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/dashboard/tools/execute-probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to execute tool probe");
  return res.json();
}
