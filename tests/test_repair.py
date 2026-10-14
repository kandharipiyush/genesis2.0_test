"""Unit tests for RequestRepairEngine."""

from schemasurgeon.repair import (
    RequestRepairEngine,
    compute_request_fingerprint,
    get_nested_value,
    set_nested_value,
    delete_nested_value,
)


def test_nested_path_helpers():
    data = {"a": {"b": 10}}
    exists, val = get_nested_value(data, "a.b")
    assert exists is True and val == 10

    set_nested_value(data, "target.id", 123)
    assert data["target"]["id"] == 123

    delete_nested_value(data, "a.b")
    assert "b" not in data["a"]


def test_apply_adapter_move_and_header():
    engine = RequestRepairEngine()
    adapter = [
        {"op": "move", "from": "user_id", "to": "target.id", "val_type": "int"},
        {"op": "add_header", "header": "X-Client-Version", "value": "2"},
    ]

    transformed, headers = engine.apply_adapter(
        arguments={"user_id": "123"},
        headers={},
        adapter=adapter,
    )

    assert "user_id" not in transformed
    assert transformed["target"]["id"] == 123
    assert headers["X-Client-Version"] == "2"


def test_unwrap_response():
    engine = RequestRepairEngine()
    wrapped = {"data": {"id": 123, "plan": "basic"}}
    schema = {"properties": {"data": {"type": "object"}}}

    unwrapped = engine.unwrap_response(wrapped, schema)
    assert unwrapped == {"id": 123, "plan": "basic"}


def test_request_fingerprint_uniqueness():
    fp1 = compute_request_fingerprint("get_user", "POST", "/get_user", {"user_id": "123"}, {})
    fp2 = compute_request_fingerprint("get_user", "POST", "/get_user", {"user_id": "123"}, {})
    fp3 = compute_request_fingerprint("get_user", "POST", "/get_user", {"user_id": "456"}, {})

    assert fp1 == fp2
    assert fp1 != fp3
