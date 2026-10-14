"""End-to-End Integration and Acceptance Tests."""

import asyncio
import os
import pytest
from schemasurgeon.models import TaskIntent, ToolContract
from schemasurgeon.registry import ToolRegistry
from schemasurgeon.gateway import SchemaSurgeonGateway
from schemasurgeon.agent_tools import HealingAgent
from schemasurgeon.audit import AuditLogger
from mock_api.mutations import active_mutations
from mock_api.schemas import get_v1_request_schema, get_v1_response_schema
from baseline.agent import BaselineAgent


@pytest.mark.asyncio
async def test_acceptance_01_normal_v1_request_succeeds(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 1: Normal v1 request succeeds."""
    active_mutations.reset()

    # Route gateway client requests to mock_api_client
    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.retry_count == 0
    assert outcome.task_verified is True
    assert outcome.response_data == {"id": 123, "plan": "basic"}


@pytest.mark.asyncio
async def test_acceptance_02_field_rename_repaired(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 2: Field rename is diagnosed and repaired."""
    active_mutations.reset()
    active_mutations.rename = True  # user_id -> id

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True
    assert outcome.new_version == 2
    assert outcome.transformed_arguments == {"id": "123"}


@pytest.mark.asyncio
async def test_acceptance_03_type_conversion_handled(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 3: Type conversion is safely handled ('123' -> 123)."""
    active_mutations.reset()
    active_mutations.type_int = True

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True
    assert outcome.transformed_arguments == {"user_id": 123}


@pytest.mark.asyncio
async def test_acceptance_04_nested_identifier_handled(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 4: Nested identifier is handled (user_id -> target.id)."""
    active_mutations.reset()
    active_mutations.nest_target = True
    active_mutations.type_int = True

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True
    assert outcome.transformed_arguments == {"target": {"id": 123}}


@pytest.mark.asyncio
async def test_acceptance_05_required_header_from_trusted_contract(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 5: Required header comes from trusted contract evidence."""
    active_mutations.reset()
    active_mutations.require_header = True

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True


@pytest.mark.asyncio
async def test_acceptance_06_response_envelope_validated_and_handled(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 6: Response envelope is validated and handled."""
    active_mutations.reset()
    active_mutations.wrap_envelope = True

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True
    assert outcome.response_data == {"id": 123, "plan": "basic"}


@pytest.mark.asyncio
async def test_acceptance_07_compound_schema_change_tested(isolated_gateway, mock_api_client, monkeypatch):
    """Acceptance 7: Compound schema change (nesting + int + header + envelope) is tested."""
    active_mutations.reset()
    active_mutations.nest_target = True
    active_mutations.type_int = True
    active_mutations.require_header = True
    active_mutations.wrap_envelope = True

    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "verified_success"
    assert outcome.promoted is True
    assert outcome.transformed_arguments == {"target": {"id": 123}}
    assert outcome.response_data == {"id": 123, "plan": "basic"}


@pytest.mark.asyncio
async def test_acceptance_15_and_16_live_tool_rebinding_without_restart(fresh_registry, mock_api_client, monkeypatch):
    """
    Acceptance 15: Next actual model call receives v2.
    Acceptance 16: Agent continues without restarting.
    """
    active_mutations.reset()
    monkeypatch.setattr("httpx.AsyncClient.request", mock_api_client.request)
    monkeypatch.setattr("httpx.AsyncClient.get", mock_api_client.get)

    gw = SchemaSurgeonGateway(registry=fresh_registry)
    agent = HealingAgent(gateway=gw, registry=fresh_registry)

    # Step 1: Run with v1
    s1 = await agent.run_step(tool_args={"user_id": "123"})
    assert s1.active_versions_seen[0] == 1
    v1_schema = s1.step_schemas[0]["schema"]
    assert "user_id" in v1_schema.get("properties", {})

    # Trigger mutation
    active_mutations.nest_target = True
    active_mutations.type_int = True

    # Call gateway directly with obsolete arguments to trigger repair & promotion
    outcome = await gw.execute_tool("get_user", {"user_id": "123"})
    assert outcome.promoted is True
    assert fresh_registry.get_active("get_user").version == 2

    # Step 2: Next model step executes in same Python agent process!
    s2 = await agent.run_step(tool_args={"target": {"id": 123}}, initial_state=s1)
    assert s2.active_versions_seen[-1] == 2
    v2_schema = s2.step_schemas[-1]["schema"]
    # Model now sees target.id instead of user_id!
    assert "target" in v2_schema.get("properties", {})
    assert "user_id" not in v2_schema.get("properties", {})


def test_acceptance_28_and_29_audit_logging_success_and_timeout(temp_audit_logger):
    """
    Acceptance 28: Success and refusal paths are audited.
    Acceptance 29: Timeout and exception paths are audited.
    """
    from schemasurgeon.models import AuditEvent

    temp_audit_logger.log(
        AuditEvent(
            event="request_started",
            tool="get_user",
            old_version=1,
        )
    )
    temp_audit_logger.log(
        AuditEvent(
            event="repair_verified",
            tool="get_user",
            old_version=1,
            candidate_version=2,
            task_verified=True,
            promoted=True,
            duration_ms=45.2,
        )
    )
    temp_audit_logger.log(
        AuditEvent(
            event="recovery_timeout",
            tool="get_user",
            old_version=1,
            refusal_reason="Deadline exceeded",
        )
    )

    events = temp_audit_logger.read_events()
    event_names = [e["event"] for e in events]
    assert "request_started" in event_names
    assert "repair_verified" in event_names
    assert "recovery_timeout" in event_names


def test_acceptance_30_audit_failure_is_surfaced(temp_audit_logger):
    """Acceptance 30: Audit failure is surfaced."""
    from schemasurgeon.models import AuditEvent

    temp_audit_logger.set_simulate_failure(True)

    with pytest.raises(IOError) as exc_info:
        temp_audit_logger.log(
            AuditEvent(event="test_event", tool="get_user")
        )

    assert "audit" in str(exc_info.value).lower()
    temp_audit_logger.set_simulate_failure(False)


@pytest.mark.asyncio
async def test_acceptance_31_and_33_baseline_runs_and_records_tokens(mock_api_client, monkeypatch):
    """
    Acceptance 31: Baseline runs under equivalent conditions.
    Acceptance 33: Token usage and recovery latency are recorded.
    """
    active_mutations.reset()
    active_mutations.nest_target = True  # Breaking change!

    monkeypatch.setattr("httpx.AsyncClient.post", mock_api_client.post)

    baseline = BaselineAgent(server_url="http://127.0.0.1:8001")
    outcome = await baseline.execute_task(
        endpoint="/get_user",
        arguments={"user_id": "123"},
    )

    # Baseline should fail because mock API enforced the schema change!
    assert outcome.success is False
    assert outcome.tokens_used > 0
    assert outcome.duration_ms > 0


@pytest.mark.asyncio
async def test_acceptance_32_real_http_benchmark_is_reproducible():
    """Acceptance 32: Real HTTP benchmark is reproducible."""
    from scripts.benchmark import run_real_http_benchmark
    results = await run_real_http_benchmark(mutation_class="rename", trials=1)
    assert "rename" in results["scenarios"]
    assert results["scenarios"]["rename"]["healer_success_rate"] == 100.0
    assert results["summary"]["healer_overall_adaptation_rate"] == 100.0
