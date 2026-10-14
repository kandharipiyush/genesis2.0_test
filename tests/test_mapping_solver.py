"""Unit tests for MappingSolver and hard safety checks."""

from schemasurgeon.mapping_solver import (
    MappingSolver,
    is_safe_integer_conversion,
    is_security_sensitive,
)
from schemasurgeon.schema_diff import diff_schemas
from mock_api.schemas import get_v1_request_schema, generate_dynamic_request_schema


def test_is_safe_integer_conversion():
    """Confirms '123' is safe but '00123' is rejected due to leading zero information loss."""
    assert is_safe_integer_conversion("123") is True
    assert is_safe_integer_conversion(123) is True
    assert is_safe_integer_conversion("00123") is False
    assert is_safe_integer_conversion("01") is False
    assert is_safe_integer_conversion("abc") is False


def test_security_sensitive_detection():
    """Identifies security-sensitive fields."""
    assert is_security_sensitive("api_key") is True
    assert is_security_sensitive("user_password") is True
    assert is_security_sensitive("auth_token") is True
    assert is_security_sensitive("user_id") is False
    assert is_security_sensitive("target.id") is False


def test_mapping_solver_nesting():
    """Solves mapping for user_id -> target.id with safe integer conversion."""
    solver = MappingSolver(min_score=0.50, unique_match_margin=0.15)
    old_req = get_v1_request_schema()
    new_req = generate_dynamic_request_schema(nest_target=True, type_int=True)

    diff = diff_schemas(old_req=old_req, new_req=new_req)
    mappings, evidence, refusals = solver.solve(
        diff=diff,
        original_args={"user_id": "123"},
        trusted_headers={},
    )

    assert not refusals
    assert len(mappings) == 1
    assert mappings[0].source_path == "user_id"
    assert mappings[0].target_path == "target.id"
    assert mappings[0].transformation == "coerce_int"
    assert mappings[0].confidence >= 0.50


def test_mapping_solver_refuses_unsafe_leading_zero():
    """Refuses mapping when identifier is '00123'."""
    solver = MappingSolver()
    old_req = get_v1_request_schema()
    new_req = generate_dynamic_request_schema(nest_target=True, type_int=True)

    diff = diff_schemas(old_req=old_req, new_req=new_req)
    mappings, evidence, refusals = solver.solve(
        diff=diff,
        original_args={"user_id": "00123"},
        trusted_headers={},
    )

    assert len(refusals) >= 1
    assert any("leading zeros" in r.lower() for r in refusals)


def test_mapping_solver_refuses_missing_authoritative_header():
    """Refuses candidate if newly required header has no trusted value."""
    solver = MappingSolver()
    diff = diff_schemas(
        old_req={},
        new_req={},
        old_headers={},
        new_headers={"X-Client-Version": "2"},
    )

    mappings, evidence, refusals = solver.solve(
        diff=diff,
        original_args={},
        trusted_headers={},  # Missing X-Client-Version!
    )

    assert len(refusals) >= 1
    assert any("missing authoritative value" in r.lower() for r in refusals)
