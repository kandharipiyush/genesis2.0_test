"""Deterministic Request Repair Engine with typed transformations and fingerprinting."""

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from schemasurgeon.models import FieldMapping, RepairCandidate
from schemasurgeon.schema_diff import SchemaDiffResult


def get_nested_value(data: Dict[str, Any], path: str) -> Tuple[bool, Any]:
    """Gets value from dotted path (e.g. 'target.id')."""
    parts = path.split(".")
    curr = data
    for part in parts:
        if not isinstance(curr, dict) or part not in curr:
            return False, None
        curr = curr[part]
    return True, curr


def set_nested_value(data: Dict[str, Any], path: str, value: Any) -> None:
    """Sets value at dotted path, creating intermediate dicts as needed."""
    parts = path.split(".")
    curr = data
    for part in parts[:-1]:
        if part not in curr or not isinstance(curr[part], dict):
            curr[part] = {}
        curr = curr[part]
    curr[parts[-1]] = value


def delete_nested_value(data: Dict[str, Any], path: str) -> None:
    """Deletes value at dotted path."""
    parts = path.split(".")
    curr = data
    for part in parts[:-1]:
        if not isinstance(curr, dict) or part not in curr:
            return
        curr = curr[part]
    if isinstance(curr, dict) and parts[-1] in curr:
        del curr[parts[-1]]


def compute_request_fingerprint(
    tool_name: str,
    method: str,
    path: str,
    arguments: Dict[str, Any],
    headers: Dict[str, str],
) -> str:
    """Computes a stable SHA-256 fingerprint of a request."""
    def _default(o):
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "dict"):
            return o.dict()
        return str(o)

    serialized_args = json.dumps(arguments, default=_default, sort_keys=True, separators=(",", ":"))
    serialized_headers = json.dumps(headers, sort_keys=True, separators=(",", ":"))
    combined = f"{tool_name}:{method}:{path}:{serialized_args}:{serialized_headers}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


class RequestRepairEngine:
    """Applies deterministic transformations to repair failed requests."""

    def build_candidate(
        self,
        tool_name: str,
        current_version: int,
        diff: SchemaDiffResult,
        mappings: List[FieldMapping],
        original_args: Dict[str, Any],
        candidate_req_schema: Dict[str, Any],
        candidate_resp_schema: Dict[str, Any],
        trusted_headers: Optional[Dict[str, str]] = None,
        evidence: Optional[List[str]] = None,
    ) -> RepairCandidate:
        """Constructs a RepairCandidate with adapter operations and transformed arguments."""
        adapter_ops: List[Dict[str, Any]] = []
        transformed = copy.deepcopy(original_args)
        trusted_h = trusted_headers or {}
        candidate_headers: Dict[str, str] = {}

        # 1. Apply field mappings
        for m in mappings:
            exists, val = get_nested_value(transformed, m.source_path)
            actual_src = m.source_path
            if not exists:
                # If exact source_path not found, check if original_args has a key that should map to target
                # e.g., transformed has 'user_id' while schema diff thought old schema had 'id'
                matched_keys = [
                    k for k in transformed.keys()
                    if k == "user_id" or "id" in k or k == m.source_path.split(".")[-1] or k == m.target_path.split(".")[-1]
                ]
                if len(matched_keys) == 1:
                    exists, val = get_nested_value(transformed, matched_keys[0])
                    if exists:
                        actual_src = matched_keys[0]
                if not exists:
                    continue

            val_type_name = type(val).__name__
            # Safe type conversion only when requested
            if m.transformation == "coerce_int":
                if isinstance(val, str) and val.isdigit():
                    try:
                        val = int(val)
                        val_type_name = "int"
                    except ValueError:
                        pass

            if actual_src != m.target_path:
                delete_nested_value(transformed, actual_src)
                set_nested_value(transformed, m.target_path, val)
                adapter_ops.append({
                    "op": "move",
                    "from": actual_src,
                    "to": m.target_path,
                    "val_type": val_type_name,
                })
            else:
                set_nested_value(transformed, m.target_path, val)
                adapter_ops.append({
                    "op": "coerce_type",
                    "path": m.target_path,
                    "new_type": val_type_name,
                })

        # 2. Inject trusted headers
        for h_name in diff.new_headers:
            if h_name in trusted_h:
                candidate_headers[h_name] = trusted_h[h_name]
                adapter_ops.append({
                    "op": "add_header",
                    "header": h_name,
                    "value": trusted_h[h_name],
                })

        # 3. Handle response envelope
        if diff.envelope_added:
            adapter_ops.append({
                "op": "unwrap_response",
                "envelope_key": diff.envelope_key or "data",
            })

        # Calculate average confidence
        if mappings:
            avg_confidence = sum(m.confidence for m in mappings) / len(mappings)
        elif diff.envelope_added or diff.new_headers:
            avg_confidence = 1.0
        else:
            avg_confidence = 0.0

        return RepairCandidate(
            target_version=current_version + 1,
            request_adapter=adapter_ops,
            candidate_request_schema=candidate_req_schema,
            candidate_response_schema=candidate_resp_schema,
            candidate_headers=candidate_headers,
            evidence=evidence or [],
            confidence_score=avg_confidence,
            requires_approval=False,
            decision="AUTO_REPAIR" if avg_confidence >= 0.50 else "REFUSE",
        )

    def apply_adapter(
        self,
        arguments: Dict[str, Any],
        headers: Dict[str, str],
        adapter: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Applies a list of adapter operations to arguments and headers."""
        transformed = copy.deepcopy(arguments)
        updated_headers = copy.deepcopy(headers)

        for op in adapter:
            op_type = op.get("op")
            if op_type == "move":
                from_path = op["from"]
                exists, val = get_nested_value(transformed, from_path)
                if not exists:
                    # Fallback alias check
                    matched_keys = [
                        k for k in transformed.keys()
                        if k == "user_id" or "id" in k or k == from_path.split(".")[-1] or k == op["to"].split(".")[-1]
                    ]
                    if len(matched_keys) == 1:
                        exists, val = get_nested_value(transformed, matched_keys[0])
                        if exists:
                            from_path = matched_keys[0]
                if exists:
                    delete_nested_value(transformed, from_path)
                    if op.get("val_type") == "int" and isinstance(val, str) and val.isdigit():
                        val = int(val)
                    set_nested_value(transformed, op["to"], val)
            elif op_type == "coerce_type":
                path = op["path"]
                exists, val = get_nested_value(transformed, path)
                if exists and op.get("new_type") == "int":
                    try:
                        set_nested_value(transformed, path, int(val))
                    except (ValueError, TypeError):
                        pass
            elif op_type == "add_header":
                updated_headers[op["header"]] = op["value"]

        return transformed, updated_headers

    def unwrap_response(
        self,
        response_data: Any,
        candidate_response_schema: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Safely unwraps response if validated candidate schema describes envelope."""
        if not isinstance(response_data, dict):
            return response_data

        if "data" in response_data:
            # Check if candidate response schema specifies the data wrapper
            if candidate_response_schema:
                props = candidate_response_schema.get("properties", {})
                if "data" in props:
                    return response_data["data"]
            else:
                return response_data["data"]

        return response_data
