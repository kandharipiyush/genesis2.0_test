"""Safety and Verification Acceptance Tests."""

import pytest
from schemasurgeon.models import TaskIntent, ToolContract, RepairCandidate
from schemasurgeon.mapping_solver import MappingSolver
from schemasurgeon.usps.confidence_gate import ConfidenceGate
from schemasurgeon.usps.intent_lock import IntentLock
from schemasurgeon.verification import VerificationEngine
from schemasurgeon.schema_diff import diff_schemas
from mock_api.mutations import active_mutations


def test_acceptance_08_leading_zero_identifier_refused():
    """Acceptance 8: Leading-zero identifier conversion is refused."""
    gate = ConfidenceGate()
    candidate = RepairCandidate(
        target_version=2,
        request_adapter=[{"op": "move", "from": "user_id", "to": "target.id", "val_type": "int"}],
        confidence_score=0.90,
    )

    decision = gate.evaluate(
        candidate=candidate,
        original_args={"user_id": "00123"},
    )

    assert decision.decision == "REFUSE"
    assert decision.safety_checks_passed is False
    assert any("leading zeros" in r.lower() for r in decision.reasons)


def test_acceptance_09_ambiguous_field_mapping_refused():
    """Acceptance 9: Ambiguous field mapping is refused."""
    solver = MappingSolver(min_score=0.50, unique_match_margin=0.15)
    # Schema with two near-identical candidates: owner.id and target.id
    old_req = {
        "properties": {"user_id": {"type": "string", "description": "User identifier"}},
        "required": ["user_id"],
    }
    new_req = {
        "properties": {
            "owner": {"type": "object", "properties": {"id": {"type": "string", "description": "User identifier"}}},
            "target": {"type": "object", "properties": {"id": {"type": "string", "description": "User identifier"}}},
        },
        "required": ["owner", "target"],
    }

    diff = diff_schemas(old_req=old_req, new_req=new_req)
    mappings, evidence, refusals = solver.solve(
        diff=diff,
        original_args={"user_id": "123"},
    )

    assert len(refusals) >= 1
    assert any("ambiguous mapping" in r.lower() for r in refusals)


def test_acceptance_10_conflicting_evidence_refused():
    """Acceptance 10: Conflicting evidence is refused."""
    gate = ConfidenceGate()
    candidate = RepairCandidate(
        target_version=2,
        request_adapter=[{"op": "move", "from": "user_id", "to": "target.id"}],
        confidence_score=0.95,
    )

    decision = gate.evaluate(
        candidate=candidate,
        original_args={"user_id": "123"},
        conflicting_evidence=True,
    )

    assert decision.decision == "REFUSE"
    assert any("conflicting evidence" in r.lower() for r in decision.reasons)


def test_acceptance_11_missing_authoritative_header_refused():
    """Acceptance 11: Missing authoritative header is refused."""
    gate = ConfidenceGate()
    candidate = RepairCandidate(
        target_version=2,
        request_adapter=[{"op": "add_header", "header": "X-Custom-Auth", "value": ""}],
        confidence_score=0.90,
    )

    decision = gate.evaluate(
        candidate=candidate,
        original_args={"user_id": "123"},
        trusted_headers={},  # Missing X-Custom-Auth!
    )

    assert decision.decision == "REFUSE"
    assert any("trusted authoritative source" in r.lower() for r in decision.reasons)


def test_acceptance_12_wrong_entity_with_http_200_rejected():
    """Acceptance 12: Wrong entity returned with HTTP 200 is rejected."""
    intent_lock = IntentLock()
    intent = TaskIntent(
        task_id="task-123",
        intent="Get user 123 plan",
        constraints={"user_id": "123"},
        postconditions=["plan_exists"],
    )

    # API returns 200, but with different user 999!
    api_response = {"id": 999, "plan": "basic"}

    is_valid, reason = intent_lock.validate_response_intent(intent, api_response)
    assert is_valid is False
    assert "wrong target rejected" in reason.lower() or "999" in reason


@pytest.mark.asyncio
async def test_acceptance_13_failed_verification_never_promotes_v2(fresh_registry):
    """Acceptance 13: Failed verification never promotes v2."""
    candidate = RepairCandidate(
        target_version=2,
        candidate_request_schema={"properties": {"target": {"type": "object"}}},
        candidate_response_schema={"properties": {"id": {"type": "integer"}}},
        confidence_score=0.95,
    )

    # Quarantine due to failed verification
    fresh_registry.quarantine("get_user", candidate, reason="Postcondition plan_exists failed")

    # Verify that active schema remains v1!
    active = fresh_registry.get_active("get_user")
    assert active.version == 1
    quarantined = fresh_registry.get_quarantined("get_user")
    assert len(quarantined) == 1
    assert "plan_exists" in quarantined[0]["reason"]


@pytest.mark.asyncio
async def test_acceptance_14_write_operations_verify_actual_state(mock_api_client):
    """Acceptance 14: Write operations verify actual state."""
    # 1. Update user 123 plan to 'enterprise'
    update_res = await mock_api_client.post(
        "/update_plan",
        json={"user_id": "123", "plan": "enterprise"},
    )
    assert update_res.status_code == 200

    # 2. Perform fresh read verification
    read_res = await mock_api_client.get("/users/123")
    assert read_res.status_code == 200
    data = read_res.json()
    assert data["plan"] == "enterprise"
