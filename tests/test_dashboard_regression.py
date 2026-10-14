"""Regression tests for SchemaSurgeon Dashboard probe execution scenarios."""

import pytest
from mock_api.mutations import MutationState
from schemasurgeon.main import (
    reset_dashboard_mock,
    apply_dashboard_mock_mutation,
    execute_dashboard_probe,
    ExecuteToolRequest,
)
from schemasurgeon.models import TaskIntent
from schemasurgeon.audit import audit_logger


@pytest.mark.asyncio
async def test_scenario_1_baseline_probe_direct_success():
    """
    Scenario 1:
    After resetting API and registry to v1, probing user '456' succeeds directly.
    Outcome must reflect direct success, NOT auto-repair:
    - status: 'verified_success'
    - decision: 'DIRECT_SUCCESS'
    - retry_count: 0
    - promoted: False
    - transformed_arguments: None
    - evidence_summary: [] (No 422 evidence, no target.id mapping, no score 0.73)
    - response_data: {'id': 456, 'plan': 'pro'}
    - task_verified: True
    """
    await reset_dashboard_mock()
    req = ExecuteToolRequest(
        arguments={"user_id": "456"},
        intent=TaskIntent(
            task_id="probe-ui",
            intent="Retrieve subscription plan for user 456",
            constraints={"user_id": "456"},
            postconditions=["plan_exists"],
        ),
    )
    res = await execute_dashboard_probe(req)

    assert res["status"] == "verified_success"
    assert res["decision"] == "DIRECT_SUCCESS"
    assert res["retry_count"] == 0
    assert res["promoted"] is False
    assert res["new_version"] == 1
    assert res["transformed_arguments"] is None
    assert res["evidence_summary"] == []
    assert res["response_data"] == {"id": 456, "plan": "pro"}
    assert res["task_verified"] is True
    assert res["refusal_reason"] is None


@pytest.mark.asyncio
async def test_scenario_2_unsafe_leading_zero_refused():
    """
    Scenario 2:
    After resetting to v1, enabling only SW-02 Identifier Type (type_int),
    probing '00123' must be REFUSED:
    - status: 'refused'
    - decision: 'REFUSE' (Must NOT be AUTO_REPAIR!)
    - retry_count: 0
    - task_verified: False
    - promoted: False
    - transformed_arguments: None
    - refusal_reason: contains 'leading zeros'
    - error_class: 'safety_refusal'
    - evidence_summary: contains safety refusal explanation
    """
    await reset_dashboard_mock()
    await apply_dashboard_mock_mutation(MutationState(type_int=True))

    req = ExecuteToolRequest(
        arguments={"user_id": "00123"},
        intent=TaskIntent(
            task_id="probe-ui",
            intent="Retrieve subscription plan for user 00123",
            constraints={"user_id": "00123"},
            postconditions=["plan_exists"],
        ),
    )
    res = await execute_dashboard_probe(req)

    assert res["status"] == "refused"
    assert res["decision"] == "REFUSE"
    assert res["decision"] != "AUTO_REPAIR"
    assert res["retry_count"] == 0
    assert res["task_verified"] is False
    assert res["promoted"] is False
    assert res["transformed_arguments"] is None
    assert res["response_data"] is None
    assert res["refusal_reason"] is not None
    assert "leading zeros" in res["refusal_reason"].lower()
    assert res["error_class"] == "safety_refusal"
    assert any("leading zeros" in ev.lower() for ev in res["evidence_summary"])


@pytest.mark.asyncio
async def test_scenario_3_nesting_repair_verified_and_promoted():
    """
    Scenario 3:
    After resetting to v1, enabling SW-03 Identifier Nesting (nest_target),
    probing user '456' triggers successful self-healing and registry promotion:
    - status: 'verified_success'
    - decision: 'AUTO_REPAIR'
    - retry_count: 1
    - task_verified: True
    - promoted: True
    - new_version: 2
    - transformed_arguments: {'target': {'id': '456'}}
    - response_data: {'id': 456, 'plan': 'pro'}
    - evidence_summary: includes mapping to target.id and score
    - Audit log records registry_promoted event with:
        event: registry_promoted, old_version: 1, candidate_version: 2,
        retry_count: 1, task_verified: True, promoted: True
    """
    await reset_dashboard_mock()
    await apply_dashboard_mock_mutation(MutationState(nest_target=True))

    req = ExecuteToolRequest(
        arguments={"user_id": "456"},
        intent=TaskIntent(
            task_id="probe-ui",
            intent="Retrieve subscription plan for user 456",
            constraints={"user_id": "456"},
            postconditions=["plan_exists"],
        ),
    )
    res = await execute_dashboard_probe(req)

    assert res["status"] == "verified_success"
    assert res["decision"] == "AUTO_REPAIR"
    assert res["retry_count"] == 1
    assert res["task_verified"] is True
    assert res["promoted"] is True
    assert res["new_version"] == 2
    assert res["transformed_arguments"] == {"target": {"id": "456"}}
    assert res["response_data"] == {"id": 456, "plan": "pro"}
    assert res["refusal_reason"] is None
    assert any("target.id" in ev for ev in res["evidence_summary"])

    # Verify audit event matches Scenario 3 spec
    events = audit_logger.read_events()
    promoted_events = [e for e in events if e.get("event") == "registry_promoted"]
    assert len(promoted_events) > 0
    latest_promotion = promoted_events[-1]
    assert latest_promotion.get("old_version") == 1
    assert latest_promotion.get("candidate_version") == 2
    assert latest_promotion.get("retry_count") == 1
    assert latest_promotion.get("task_verified") is True
    assert latest_promotion.get("promoted") is True
