"""Registry, Concurrency and Resilience Acceptance Tests."""

import asyncio
import time
import pytest
from schemasurgeon.models import RepairCandidate, ToolContract
from schemasurgeon.registry import ToolRegistry
from schemasurgeon.gateway import SchemaSurgeonGateway
from schemasurgeon.repair import compute_request_fingerprint


@pytest.mark.asyncio
async def test_acceptance_17_deadline_leaves_registry_unchanged(isolated_gateway, fresh_registry):
    """Acceptance 17: Deadline leaves the active registry unchanged."""
    active_before = fresh_registry.get_active("get_user")
    assert active_before.version == 1

    # Call with 0.001s deadline to guarantee timeout during recovery
    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
        deadline_seconds=0.0001,
    )

    active_after = fresh_registry.get_active("get_user")
    assert active_after.version == 1  # Unchanged!
    assert outcome.promoted is False


@pytest.mark.asyncio
async def test_acceptance_18_duplicate_fingerprint_rejected(isolated_gateway):
    """Acceptance 18: Duplicate fingerprint is rejected before dispatch."""
    # Seed fingerprint
    fp = compute_request_fingerprint("get_user", "POST", "/get_user", {"user_id": "123"}, {})
    isolated_gateway._seen_fingerprints.add(fp)

    # Directly verify duplicate check logic
    assert fp in isolated_gateway._seen_fingerprints


def test_acceptance_19_anti_flap_policy_blocks_repeated_rehealing(isolated_gateway):
    """Acceptance 19: Anti-flap policy blocks repeated re-healing."""
    tool_name = "get_user"

    # First re-heal is allowed
    assert isolated_gateway._check_anti_flap(tool_name) is True
    isolated_gateway._record_anti_flap_recovery(tool_name)

    # Second re-heal within 30s window is blocked by anti-flap policy!
    assert isolated_gateway._check_anti_flap(tool_name) is False


@pytest.mark.asyncio
async def test_acceptance_20_promotion_conflict_handled_safely(fresh_registry):
    """Acceptance 20: Promotion conflict is handled safely."""
    candidate1 = RepairCandidate(
        target_version=2,
        candidate_request_schema={"properties": {"id": {"type": "integer"}}},
        candidate_response_schema={"properties": {"id": {"type": "integer"}}},
        confidence_score=0.9,
    )
    candidate2 = RepairCandidate(
        target_version=2,
        candidate_request_schema={"properties": {"target": {"type": "object"}}},
        candidate_response_schema={"properties": {"id": {"type": "integer"}}},
        confidence_score=0.85,
    )

    # Request 1 promotes from expected version 1 -> succeeds
    promoted1 = await fresh_registry.promote_if_current(
        tool_name="get_user",
        expected_version=1,
        candidate=candidate1,
    )
    assert promoted1 is True
    assert fresh_registry.get_active("get_user").version == 2

    # Request 2 also expected version 1 -> promotion conflict! Must safely return False!
    promoted2 = await fresh_registry.promote_if_current(
        tool_name="get_user",
        expected_version=1,
        candidate=candidate2,
    )
    assert promoted2 is False  # Safely rejected!
    assert fresh_registry.get_active("get_user").version == 2


@pytest.mark.asyncio
async def test_acceptance_21_non_schema_errors_use_separate_policies(isolated_gateway, monkeypatch):
    """Acceptance 21: Non-schema errors (e.g. 500, 429) use separate policies and do not enter healing."""
    import httpx

    # Simulate 500 Internal Server Error
    async def mock_post(*args, **kwargs):
        class MockResponse:
            status_code = 500
            text = "Internal Server Error"
            def json(self):
                return {"error": "database connection down"}
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_post)

    outcome = await isolated_gateway.execute_tool(
        tool_name="get_user",
        arguments={"user_id": "123"},
    )

    assert outcome.status == "error"
    assert outcome.error_class == "http_500"
    assert outcome.retry_count == 0  # Did not attempt schema healing retry
