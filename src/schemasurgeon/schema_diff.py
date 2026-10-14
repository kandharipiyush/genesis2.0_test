"""Schema diff engine to detect structural, typing, nesting, header and envelope changes."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PropertyMeta(BaseModel):
    path: str
    name: str
    type: str
    description: str = ""
    required: bool = False
    parent_path: str = ""


class SchemaDiffResult(BaseModel):
    old_properties: Dict[str, PropertyMeta] = Field(default_factory=dict)
    new_properties: Dict[str, PropertyMeta] = Field(default_factory=dict)
    added_paths: List[str] = Field(default_factory=list)
    removed_paths: List[str] = Field(default_factory=list)
    type_changes: List[Dict[str, Any]] = Field(default_factory=list)
    required_changes: List[Dict[str, Any]] = Field(default_factory=list)
    nested_changes: List[Dict[str, Any]] = Field(default_factory=list)
    envelope_added: bool = False
    envelope_key: Optional[str] = None
    new_headers: Dict[str, str] = Field(default_factory=dict)


def _flatten_schema_properties(
    schema: Dict[str, Any],
    parent_path: str = "",
    parent_required: Optional[List[str]] = None,
) -> Dict[str, PropertyMeta]:
    """Recursively flattens JSON schema properties into dotted paths."""
    results: Dict[str, PropertyMeta] = {}
    if not isinstance(schema, dict):
        return results

    properties = schema.get("properties", {})
    required_list = schema.get("required", [])

    for prop_name, prop_def in properties.items():
        current_path = f"{parent_path}.{prop_name}" if parent_path else prop_name
        prop_type = prop_def.get("type", "any")
        is_req = prop_name in required_list

        if prop_type == "object" and "properties" in prop_def:
            # Recurse into object properties
            nested = _flatten_schema_properties(
                prop_def,
                parent_path=current_path,
                parent_required=prop_def.get("required", []),
            )
            results.update(nested)
        else:
            meta = PropertyMeta(
                path=current_path,
                name=prop_name,
                type=prop_type,
                description=prop_def.get("description", ""),
                required=is_req,
                parent_path=parent_path,
            )
            results[current_path] = meta

    return results


def diff_schemas(
    old_req: Dict[str, Any],
    new_req: Dict[str, Any],
    old_resp: Optional[Dict[str, Any]] = None,
    new_resp: Optional[Dict[str, Any]] = None,
    old_headers: Optional[Dict[str, str]] = None,
    new_headers: Optional[Dict[str, str]] = None,
) -> SchemaDiffResult:
    """Computes structural differences between old and new tool contracts."""
    old_props = _flatten_schema_properties(old_req)
    new_props = _flatten_schema_properties(new_req)

    added_paths = [p for p in new_props if p not in old_props]
    removed_paths = [p for p in old_props if p not in new_props]

    diff = SchemaDiffResult(
        old_properties=old_props,
        new_properties=new_props,
        added_paths=added_paths,
        removed_paths=removed_paths,
    )

    # Check for direct type changes if paths match
    for p in old_props:
        if p in new_props:
            if old_props[p].type != new_props[p].type:
                diff.type_changes.append({
                    "path": p,
                    "old_type": old_props[p].type,
                    "new_type": new_props[p].type,
                })

    # Detect nesting (e.g. user_id -> target.id or target.user_id)
    for rem in removed_paths:
        for add in added_paths:
            if "." in add:
                parts = add.split(".")
                last_part = parts[-1]
                # If name matches or suffix matches
                if last_part == rem or last_part == "id" and "id" in rem:
                    diff.nested_changes.append({
                        "source": rem,
                        "target": add,
                        "old_type": old_props[rem].type,
                        "new_type": new_props[add].type,
                    })

    # Response envelope detection (e.g. data wrapper)
    if old_resp and new_resp:
        new_resp_props = new_resp.get("properties", {})
        if "data" in new_resp_props and "data" not in old_resp.get("properties", {}):
            diff.envelope_added = True
            diff.envelope_key = "data"

    # Header diff
    old_h = old_headers or {}
    new_h = new_headers or {}
    diff.new_headers = {k: v for k, v in new_h.items() if k not in old_h or old_h[k] != v}

    return diff
