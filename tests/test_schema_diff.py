"""Unit tests for SchemaDiff engine."""

from schemasurgeon.schema_diff import diff_schemas
from mock_api.schemas import (
    get_v1_request_schema,
    get_v1_response_schema,
    generate_dynamic_request_schema,
    generate_dynamic_response_schema,
)


def test_diff_field_rename():
    """Detects renamed field from user_id to id."""
    old_req = get_v1_request_schema()
    new_req = generate_dynamic_request_schema(rename=True)

    diff = diff_schemas(old_req=old_req, new_req=new_req)

    assert "user_id" in diff.removed_paths
    assert "id" in diff.added_paths
    assert diff.old_properties["user_id"].type == "string"


def test_diff_nesting_detection():
    """Detects nesting of user_id inside target.id."""
    old_req = get_v1_request_schema()
    new_req = generate_dynamic_request_schema(nest_target=True, type_int=True)

    diff = diff_schemas(old_req=old_req, new_req=new_req)

    assert "target.id" in diff.added_paths
    assert len(diff.nested_changes) >= 1
    assert diff.nested_changes[0]["source"] == "user_id"
    assert diff.nested_changes[0]["target"] == "target.id"
    assert diff.nested_changes[0]["new_type"] == "integer"


def test_diff_type_change():
    """Detects direct type changes string -> integer."""
    old_req = get_v1_request_schema()
    new_req = generate_dynamic_request_schema(type_int=True)

    diff = diff_schemas(old_req=old_req, new_req=new_req)

    assert len(diff.type_changes) == 1
    assert diff.type_changes[0]["path"] == "user_id"
    assert diff.type_changes[0]["old_type"] == "string"
    assert diff.type_changes[0]["new_type"] == "integer"


def test_diff_response_envelope():
    """Detects response envelope wrapping in data."""
    old_resp = get_v1_response_schema()
    new_resp = generate_dynamic_response_schema(wrap_envelope=True)

    diff = diff_schemas(
        old_req={},
        new_req={},
        old_resp=old_resp,
        new_resp=new_resp,
    )

    assert diff.envelope_added is True
    assert diff.envelope_key == "data"


def test_diff_required_headers():
    """Detects newly required headers."""
    diff = diff_schemas(
        old_req={},
        new_req={},
        old_headers={},
        new_headers={"X-Client-Version": "2"},
    )

    assert "X-Client-Version" in diff.new_headers
    assert diff.new_headers["X-Client-Version"] == "2"
