# SchemaSurgeon: Evidence-Driven Self-Healing Tool Registry for AI Agents

SchemaSurgeon is an evidence-driven self-healing tool registry designed for autonomous AI agents. It sits between an agent and the APIs its tools invoke, actively diagnosing breaking schema drift, safely repairing failed requests using multi-source evidence, verifying task completion, and hot-patching tool definitions at runtime without process restart.

---

## 1. System Architecture

```
+-----------------------------------------------------------------------------+
|                                AI Agent (LangGraph)                         |
|  - Receives user task                                                       |
|  - Calls dynamically bound tools from active registry (v1 -> v2)             |
+--------------------------------------┬--------------------------------------+
                                       │ Tool Call (e.g. get_user)
                                       ▼
+-----------------------------------------------------------------------------+
|                             SchemaSurgeon Gateway                           |
|  - Check Request Suppression (USP 3)                                        |
|  - HTTPX Dispatch & Status Classification                                    |
|  - Anti-Flap Loop Prevention & Bounded Recovery Deadline (4.0s)              |
+--------------------------------------┬--------------------------------------+
                                       │ HTTP 400/422 Schema Validation Error
                                       ▼
+-----------------------------------------------------------------------------+
|                           Diagnosis & Repair Engine                         |
|  - Evidence Collector (OpenAPI doc, error path, old schema, memory)         |
|  - Schema Diff Engine (renamed, nested, type coercion, headers, envelope)   |
|  - Mapping Solver (semantic scoring + path overlap + structural compat)     |
|  - Hard Safety Gates & Confidence Gate (USP 2)                              |
|  - Drift Memory Pattern Matcher (USP 5)                                     |
+--------------------------------------┬--------------------------------------+
                                       │ Candidate Adapter & Validated Payload
                                       ▼
+-----------------------------------------------------------------------------+
|                             Verification & Promotion                        |
|  - Single Bounded Retry Dispatch                                            |
|  - Envelope Unwrapping                                                      |
|  - Intent Lock & Postcondition Verification (USP 4)                         |
|  - Atomic Concurrency-Safe Registry Promotion (v1 -> v2)                    |
|  - Dynamic LangGraph Rebinding on Next Model Step (Zero Process Restart)    |
+-----------------------------------------------------------------------------+
```

---

## 2. The Five Unique Selling Points (USPs)

1. **USP 1 — Proactive Documentation-Based Adaptation** (`proactive_monitor.py`):
   Polls trusted OpenAPI contracts, detects breaking contract hash changes, validates candidate schemas in sandbox probes, and promotes new tool schemas *before* runtime failures occur.
2. **USP 2 — Confidence-Gated, Transparent Recovery** (`confidence_gate.py`):
   Evaluates multi-signal mapping scores (description token similarity 0.50, path token overlap 0.30, structural compatibility 0.20). Enforces mandatory non-negotiable hard safety rules (refuses leading-zero conversions `"00123"` -> `123`, ambiguous mappings, and missing authoritative headers).
3. **USP 3 — Adaptive Invalid-Request Suppression** (`request_suppression.py`):
   Tracks failure fingerprints per tool and contract version. Suppresses repeated invalid requests within a 30s window without hitting backend APIs or LLMs. Never suppresses legitimate first-time tools or 429/5xx/timeout errors.
4. **USP 4 — Intent Lock** (`intent_lock.py`):
   Locks task intent, target entity identifiers, and postconditions. Explicitly rejects technically successful HTTP 200 responses if the returned entity does not match the requested target.
5. **USP 5 — Drift Memory** (`drift_memory.py`):
   Persists verified schema transformation patterns. Reuses verified mappings as supporting evidence for matching drift after revalidating candidate schema compatibility, rejecting stale or incompatible patterns.

---

## 3. Technology Stack

- **Backend & Core Healer**: Python 3.10+, FastAPI, Uvicorn, HTTPX
- **Schema & Diffing**: JSON Schema (Draft 7), `jsonschema`, `jsonpatch`
- **Agent Orchestration**: LangGraph (`StateGraph`), LangChain Core (`StructuredTool`)
- **Audit & Observability**: JSONL structured event logs with credential redaction
- **Testing**: `pytest`, `pytest-asyncio`
- **Terminal Demo**: `rich`
- **Interactive Control Center**: React 18, TypeScript, Vite, Recharts, Lucide React

---

## 4. Windows Setup & Installation

### Step 1: Clone and Create Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 2: Install Python Dependencies & Package
```powershell
.venv\Scripts\pip.exe install -e .
```

### Step 3: Install Dashboard Dependencies
```powershell
cd dashboard
npm install
npm run build
cd ..
```

---

## 5. Running the System

### Option A: Run All 44 Automated Unit, Safety & Integration Tests
```powershell
.venv\Scripts\pytest.exe -v
```

### Option B: Run the Terminal Live Demonstration
Demonstrates initial v1 execution, compound drift injection, 422 detection, automatic repair, Intent Lock verification, atomic promotion to v2, live model tool rebinding without restart, and safety refusal of `"00123"`.
```powershell
.venv\Scripts\python.exe scripts/run_demo.py
```

### Option C: Run the Real HTTP Benchmark Suite
Runs fair side-by-side trials comparing Baseline Agent vs SchemaSurgeon across mutation classes:
```powershell
.venv\Scripts\python.exe scripts/benchmark.py
```

### Option D: Run the Full Servers & Interactive Control Center Dashboard
In Terminal 1 (Start Mock API on port 8001):
```powershell
.venv\Scripts\uvicorn.exe mock_api.app:mock_app --port 8001 --host 127.0.0.1
```

In Terminal 2 (Start SchemaSurgeon Gateway & Dashboard on port 8000):
```powershell
.venv\Scripts\uvicorn.exe schemasurgeon.main:app --port 8000 --host 127.0.0.1
```

Open your browser to:
- **Interactive Control Center Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Gateway Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Mock API Dynamic Swagger Docs**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

## 6. Complete Acceptance Checklist (33/33 Complete)

### Core Recovery
- [x] **1. Normal v1 request succeeds** (`test_acceptance_01_normal_v1_request_succeeds`)
- [x] **2. Field rename is diagnosed and repaired** (`test_acceptance_02_field_rename_repaired`)
- [x] **3. Type conversion is safely handled** (`test_acceptance_03_type_conversion_handled`)
- [x] **4. Nested identifier is handled** (`test_acceptance_04_nested_identifier_handled`)
- [x] **5. Required header comes from trusted contract evidence** (`test_acceptance_05_required_header_from_trusted_contract`)
- [x] **6. Response envelope is validated and handled** (`test_acceptance_06_response_envelope_validated_and_handled`)
- [x] **7. Compound schema change is tested** (`test_acceptance_07_compound_schema_change_tested`)

### Safety and Verification
- [x] **8. Leading-zero identifier conversion is refused** (`test_acceptance_08_leading_zero_identifier_refused`)
- [x] **9. Ambiguous field mapping is refused** (`test_acceptance_09_ambiguous_field_mapping_refused`)
- [x] **10. Conflicting evidence is refused** (`test_acceptance_10_conflicting_evidence_refused`)
- [x] **11. Missing authoritative header is refused** (`test_acceptance_11_missing_authoritative_header_refused`)
- [x] **12. Wrong entity returned with HTTP 200 is rejected** (`test_acceptance_12_wrong_entity_with_http_200_rejected`)
- [x] **13. Failed verification never promotes v2** (`test_acceptance_13_failed_verification_never_promotes_v2`)
- [x] **14. Write operations verify actual state** (`test_acceptance_14_write_operations_verify_actual_state`)

### Runtime and Resilience
- [x] **15. Next actual model call receives v2** (`test_acceptance_15_and_16_live_tool_rebinding_without_restart`)
- [x] **16. Agent continues without restarting** (`test_acceptance_15_and_16_live_tool_rebinding_without_restart`)
- [x] **17. Deadline leaves the active registry unchanged** (`test_acceptance_17_deadline_leaves_registry_unchanged`)
- [x] **18. Duplicate fingerprint is rejected before dispatch** (`test_acceptance_18_duplicate_fingerprint_rejected`)
- [x] **19. Anti-flap policy blocks repeated re-healing** (`test_acceptance_19_anti_flap_policy_blocks_repeated_rehealing`)
- [x] **20. Promotion conflict is handled safely** (`test_acceptance_20_promotion_conflict_handled_safely`)
- [x] **21. Non-schema errors use separate policies** (`test_acceptance_21_non_schema_errors_use_separate_policies`)

### USP Tests
- [x] **22. Proactive monitor detects a changed OpenAPI contract** (`test_acceptance_22_proactive_monitor_detects_changed_openapi`)
- [x] **23. Confidence gate refuses unsafe candidates** (`test_acceptance_23_confidence_gate_refuses_unsafe_candidates`)
- [x] **24. Repeated invalid requests are suppressed appropriately** (`test_acceptance_24_repeated_invalid_requests_suppressed`)
- [x] **25. Intent Lock detects a wrong-target result** (`test_acceptance_25_intent_lock_detects_wrong_target`)
- [x] **26. Drift Memory reuses a compatible verified pattern** (`test_acceptance_26_drift_memory_reuses_compatible_pattern`)
- [x] **27. Drift Memory rejects an incompatible or stale pattern** (`test_acceptance_27_drift_memory_rejects_incompatible_pattern`)

### Operations and Evaluation
- [x] **28. Success and refusal paths are audited** (`test_acceptance_28_and_29_audit_logging_success_and_timeout`)
- [x] **29. Timeout and exception paths are audited** (`test_acceptance_28_and_29_audit_logging_success_and_timeout`)
- [x] **30. Audit failure is surfaced** (`test_acceptance_30_audit_failure_is_surfaced`)
- [x] **31. Baseline runs under equivalent conditions** (`test_acceptance_31_and_33_baseline_runs_and_records_tokens`)
- [x] **32. Real HTTP benchmark is reproducible** (`test_acceptance_32_real_http_benchmark_is_reproducible`)
- [x] **33. Token usage and recovery latency are recorded** (`test_acceptance_31_and_33_baseline_runs_and_records_tokens`)

---

## 7. Empirical Benchmark Results

Measured side-by-side on real HTTP transport (`Uvicorn` + `HTTPX`):

| Mutation Scenario | Trials | Baseline Success Rate | SchemaSurgeon Recovery Rate | Baseline Latency | Healer MTTR |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Field Rename** (`user_id` &rarr; `id`) | 2 | 0.0% | **100.0%** | 20.6 ms | 35.1 ms |
| **Type Coercion** (`"123"` &rarr; `123`) | 2 | 0.0% | **100.0%** | 20.5 ms | 36.0 ms |
| **Nesting** (`user_id` &rarr; `target.id`) | 2 | 0.0% | **100.0%** | 25.9 ms | 44.7 ms |
| **Required Header** (`X-Client-Version: 2`) | 2 | 0.0% | **100.0%** | 23.9 ms | 14.5 ms |
| **Response Envelope** (`{"data": ...}`) | 2 | 0.0% | **100.0%** | 24.1 ms | 56.2 ms |
| **Compound Mutation** (All 5 combined) | 2 | 0.0% | **100.0%** | 29.6 ms | 60.5 ms |

- **Zero-Touch Adaptation Rate**: **100.0%**
- **Mean Healer MTTR**: **41.2 ms**
- **Token Overhead**: **0%** (deterministic Python repair engine; zero re-prompting tokens required)
- **Incorrect Repair Rate**: **0.0%**
- **Safe-Refusal Accuracy**: **100.0%**
