"""FastAPI SchemaSurgeon Gateway, Control API and Dashboard Server."""

import time
import httpx
from typing import Any, Dict, List, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from schemasurgeon.config import settings
from schemasurgeon.models import TaskIntent, ToolContract
from schemasurgeon.registry import registry
from schemasurgeon.gateway import SchemaSurgeonGateway
from schemasurgeon.audit import audit_logger
from schemasurgeon.metrics import compute_metrics
from schemasurgeon.usps.drift_memory import drift_memory
from schemasurgeon.usps.proactive_monitor import ProactiveMonitor

gateway = SchemaSurgeonGateway()
proactive_monitor = ProactiveMonitor(registry)

app = FastAPI(
    title="SchemaSurgeon Gateway & Control Center",
    version="1.0.0",
    description="Evidence-Driven Self-Healing Tool Registry for AI Agents",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteToolRequest(BaseModel):
    arguments: Dict[str, Any]
    intent: Optional[TaskIntent] = None
    deadline_seconds: Optional[float] = None


class DiagnoseToolRequest(BaseModel):
    arguments: Dict[str, Any]
    status_code: int = 422
    error_payload: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunRequest(BaseModel):
    mutation_type: str = "all"  # rename, nesting, type_int, require_header, wrap_envelope, compound, all
    trials_per_class: int = 3


# Cache for latest benchmark results
LATEST_BENCHMARK_RESULTS: Dict[str, Any] = {}


@app.on_event("startup")
async def startup_event():
    # Register default get_user v1 tool if not present
    from mock_api.schemas import get_v1_request_schema, get_v1_response_schema

    if not registry.get_active("get_user"):
        v1_contract = ToolContract(
            tool_name="get_user",
            version=1,
            method="POST",
            path="/get_user",
            request_schema=get_v1_request_schema(),
            response_schema=get_v1_response_schema(),
            server_url=settings.mock_api_url,
            required_headers={},
        )
        registry.register(v1_contract)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "schemasurgeon_gateway",
        "timestamp": time.time(),
    }


@app.get("/tools")
async def list_tools():
    """Lists registered tools and active versions."""
    tools = []
    for tool_name in ["get_user"]:
        active = registry.get_active(tool_name)
        if active:
            tools.append({
                "tool_name": active.tool_name,
                "active_version": active.version,
                "method": active.method,
                "path": active.path,
                "contract_hash": active.contract_hash,
            })
    return {"tools": tools}


@app.get("/tools/{name}")
async def inspect_tool(name: str):
    """Inspects active contract and metadata for a tool."""
    active = registry.get_active(name)
    if not active:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    return active.model_dump()


@app.get("/tools/{name}/history")
async def tool_history(name: str):
    """Views all schema versions and history."""
    history = registry.get_history(name)
    quarantined = registry.get_quarantined(name)
    return {
        "tool_name": name,
        "versions": [c.model_dump() for c in history],
        "quarantined": quarantined,
    }


@app.post("/tools/{name}/execute")
async def execute_tool_endpoint(name: str, req: ExecuteToolRequest):
    """Executes a tool through the SchemaSurgeon Gateway."""
    outcome = await gateway.execute_tool(
        tool_name=name,
        arguments=req.arguments,
        intent=req.intent,
        deadline_seconds=req.deadline_seconds,
    )
    return outcome.model_dump()


@app.post("/tools/{name}/diagnose")
async def test_diagnose_tool(name: str, req: DiagnoseToolRequest):
    """Runs diagnosis in controlled test mode without modifying active schema."""
    contract = registry.get_active(name)
    if not contract:
        raise HTTPException(status_code=404, detail="Tool not found")

    candidate = await gateway.diagnosis_engine.diagnose_and_plan(
        active_contract=contract,
        original_args=req.arguments,
        status_code=req.status_code,
        error_payload=req.error_payload,
        trusted_headers=contract.required_headers,
    )
    return candidate.model_dump()


@app.get("/tools/{name}/repairs")
async def list_repairs(name: str):
    """Views repair history from audit logs."""
    events = audit_logger.read_events()
    tool_events = [e for e in events if e.get("tool") == name]
    return {"tool_name": name, "events": tool_events}


@app.post("/admin/monitor/run")
async def run_proactive_check(tool_name: str = "get_user"):
    """Triggers proactive contract monitoring check."""
    detected, candidate, evidence = await proactive_monitor.check_for_drift(tool_name)
    if detected and candidate and candidate.decision == "AUTO_REPAIR":
        promoted = await registry.promote_if_current(
            tool_name=tool_name,
            expected_version=candidate.target_version - 1,
            candidate=candidate,
        )
        return {
            "drift_detected": True,
            "promoted": promoted,
            "candidate": candidate.model_dump(),
            "evidence": evidence,
        }
    return {
        "drift_detected": detected,
        "promoted": False,
        "candidate": candidate.model_dump() if candidate else None,
        "evidence": evidence,
    }


@app.get("/admin/memory")
async def inspect_memory():
    """Inspects eligible Drift Memory entries."""
    return {"entries": drift_memory.get_all_entries()}


@app.get("/metrics")
async def get_metrics_endpoint():
    """Retrieves aggregated recovery metrics."""
    return compute_metrics()


# -------------------------------------------------------------
# DASHBOARD SPECIFIC API ENDPOINTS (SECTION 12)
# -------------------------------------------------------------


@app.get("/api/dashboard/metrics")
async def dashboard_metrics():
    """KPI metrics for the SchemaSurgeon Control Center."""
    return compute_metrics()


@app.get("/api/dashboard/timeline")
async def dashboard_timeline(limit: int = 50):
    """Live recovery event timeline."""
    events = audit_logger.read_events()
    # Sort newest first
    events_sorted = sorted(events, key=lambda x: x.get("timestamp", 0), reverse=True)
    return {"events": events_sorted[:limit]}


@app.get("/api/dashboard/schemas")
async def dashboard_schemas():
    """Registry explorer data with schema versions and diffs."""
    active = registry.get_active("get_user")
    history = registry.get_history("get_user")
    quarantined = registry.get_quarantined("get_user")

    return {
        "active_tool": "get_user",
        "active_version": active.version if active else 1,
        "active_contract": active.model_dump() if active else None,
        "history": [c.model_dump() for c in history],
        "quarantined": quarantined,
    }


@app.get("/api/dashboard/analytics")
async def dashboard_analytics():
    """Safety and repair analytics broken down by decision and mutation."""
    events = audit_logger.read_events()
    decisions = {"AUTO_REPAIR": 0, "REQUIRES_APPROVAL": 0, "REFUSE": 0, "SUPPRESSED": 0}
    error_types: Dict[str, int] = {}

    for ev in events:
        dec = ev.get("decision")
        if dec in decisions:
            decisions[dec] += 1
        err_cls = ev.get("error_class")
        if err_cls:
            error_types[err_cls] = error_types.get(err_cls, 0) + 1

    return {
        "decisions": decisions,
        "error_types": error_types,
    }


@app.post("/api/dashboard/benchmark/run")
async def run_benchmark_endpoint(req: BenchmarkRunRequest):
    """Runs a controlled benchmark and stores results."""
    from scripts.benchmark import run_real_http_benchmark

    results = await run_real_http_benchmark(
        mutation_class=req.mutation_type,
        trials=req.trials_per_class,
    )
    global LATEST_BENCHMARK_RESULTS
    LATEST_BENCHMARK_RESULTS = results
    return results


@app.get("/api/dashboard/benchmark/latest")
async def latest_benchmark():
    if not LATEST_BENCHMARK_RESULTS:
        return {"status": "no_runs_yet", "message": "No data yet. Run a benchmark to view results."}
    return LATEST_BENCHMARK_RESULTS


# Mock API integration endpoints for Dashboard
from mock_api.mutations import active_mutations, MutationState
import mock_api.app as mock_api_module


@app.get("/api/dashboard/mock/state")
async def get_dashboard_mock_state():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.mock_api_url}/admin/state")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {
        "status": "ok",
        "mutations": active_mutations.model_dump(),
        "is_v1": active_mutations.is_v1(),
    }


@app.post("/api/dashboard/mock/mutate")
async def apply_dashboard_mock_mutation(mutations: MutationState):
    active_mutations.rename = mutations.rename
    active_mutations.type_int = mutations.type_int
    active_mutations.nest_target = mutations.nest_target
    active_mutations.require_header = mutations.require_header
    active_mutations.wrap_envelope = mutations.wrap_envelope
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(f"{settings.mock_api_url}/admin/mutate", json=mutations.model_dump())
    except Exception:
        pass

    # Log to persistent audit trail so dashboard timeline reflects this action immediately
    from schemasurgeon.models import AuditEvent
    audit_logger.log(
        AuditEvent(
            event="mock_api_mutated",
            tool="mock_api",
            metadata={"mutations": mutations.model_dump()},
            evidence=[f"Mutation applied: rename={mutations.rename}, type_int={mutations.type_int}, nest={mutations.nest_target}, header={mutations.require_header}, envelope={mutations.wrap_envelope}"],
        )
    )

    return {
        "status": "mutated",
        "mutations": active_mutations.model_dump(),
        "is_v1": active_mutations.is_v1(),
    }


@app.post("/api/dashboard/mock/reset")
async def reset_dashboard_mock():
    active_mutations.reset()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(f"{settings.mock_api_url}/admin/reset")
    except Exception:
        pass
    mock_api_module.USERS_DB[123] = {"id": 123, "plan": "basic"}
    mock_api_module.USERS_DB[456] = {"id": 456, "plan": "pro"}
    mock_api_module.USERS_DB[789] = {"id": 789, "plan": "enterprise"}

    # Also reset gateway registry back to v1 clean state
    from mock_api.schemas import get_v1_request_schema, get_v1_response_schema
    registry.reset()
    v1_contract = ToolContract(
        tool_name="get_user",
        version=1,
        method="POST",
        path="/get_user",
        request_schema=get_v1_request_schema(),
        response_schema=get_v1_response_schema(),
        server_url=settings.mock_api_url,
        required_headers={},
    )
    registry.register(v1_contract)
    gateway.reset_history()
    drift_memory.reset()

    # Log to persistent audit trail so dashboard timeline reflects this action immediately
    from schemasurgeon.models import AuditEvent
    audit_logger.log(
        AuditEvent(
            event="mock_api_reset",
            tool="mock_api",
            metadata={"reset_to_version": 1},
            evidence=["Reset mock API and Gateway registry back to initial v1 contract"],
        )
    )

    return {
        "status": "reset",
        "mutations": active_mutations.model_dump(),
        "is_v1": True,
        "active_version": 1,
    }


@app.post("/api/dashboard/tools/execute-probe")
async def execute_dashboard_probe(req: ExecuteToolRequest):
    outcome = await gateway.execute_tool(
        tool_name="get_user",
        arguments=req.arguments,
        intent=req.intent,
        deadline_seconds=req.deadline_seconds,
    )
    return outcome.model_dump()


# Mount production dashboard bundle if built
dashboard_dist = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")
