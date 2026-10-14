export interface MetricsData {
  total_calls: number;
  schema_drift_incidents: number;
  verified_recoveries: number;
  zero_touch_adaptation_rate: number;
  mean_mttr_ms: number;
  median_mttr_ms: number;
  p95_mttr_ms: number;
  max_mttr_ms: number;
  unsafe_repairs_refused: number;
  failed_verifications: number;
  requests_suppressed: number;
  timeouts: number;
  proactive_adaptations: number;
  sample_count: number;
}

export interface AuditEventItem {
  timestamp: number;
  event: string;
  tool: string;
  task_id?: string;
  recovery_id?: string;
  old_version?: number;
  candidate_version?: number;
  decision?: string;
  retry_count?: number;
  task_verified?: boolean;
  promoted?: boolean;
  error_class?: string;
  refusal_reason?: string;
  evidence?: string[];
  duration_ms?: number;
  metadata?: Record<string, any>;
}

export interface ToolContractItem {
  tool_name: string;
  version: number;
  method: string;
  path: string;
  request_schema: Record<string, any>;
  response_schema: Record<string, any>;
  contract_hash: string;
  server_url: string;
  required_headers: Record<string, string>;
  metadata: Record<string, any>;
}

export interface SchemaExplorerData {
  active_tool: string;
  active_version: number;
  active_contract: ToolContractItem | null;
  history: ToolContractItem[];
  quarantined: Array<{
    candidate: any;
    reason: string;
  }>;
}

export interface AnalyticsData {
  decisions: Record<string, number>;
  error_types: Record<string, number>;
}

export interface ScenarioResult {
  trials: number;
  baseline_success_rate: number;
  healer_success_rate: number;
  baseline_mean_ms: number;
  healer_mean_ms: number;
}

export interface BenchmarkSummary {
  total_trials: number;
  baseline_overall_success_rate: number;
  healer_overall_adaptation_rate: number;
  healer_mean_mttr_ms: number;
  healer_median_mttr_ms: number;
  healer_p95_mttr_ms: number;
  token_overhead: string;
  incorrect_repair_rate: string;
  safe_refusal_accuracy: string;
}

export interface BenchmarkData {
  timestamp?: number;
  trials_per_class?: number;
  scenarios: Record<string, ScenarioResult>;
  summary: BenchmarkSummary;
  status?: string;
  message?: string;
}

export interface ExecutionOutcome {
  status: string;
  tool_name: string;
  old_version: number;
  new_version?: number | null;
  retry_count: number;
  task_verified: boolean;
  promoted: boolean;
  refusal_reason?: string | null;
  transformed_arguments?: Record<string, any> | null;
  response_data?: any;
  duration_ms: number;
  error_class?: string | null;
  evidence_summary: string[];
  decision?: string | null;
  confidence_score?: number | null;
}
