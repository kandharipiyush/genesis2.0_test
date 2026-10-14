"""Schemas and dynamic OpenAPI generation for Mock API."""

from typing import Any, Dict


def get_v1_request_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "title": "GetUserRequestV1",
        "properties": {
            "user_id": {
                "type": "string",
                "title": "User ID",
                "description": "Unique identifier of the user",
            }
        },
        "required": ["user_id"],
        "additionalProperties": False,
    }


def get_v1_response_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "title": "GetUserResponseV1",
        "properties": {
            "id": {
                "type": "integer",
                "title": "ID",
                "description": "User identifier",
            },
            "plan": {
                "type": "string",
                "title": "Plan",
                "description": "User subscription plan tier",
            },
        },
        "required": ["id", "plan"],
        "additionalProperties": False,
    }


def generate_dynamic_request_schema(
    rename: bool = False,
    type_int: bool = False,
    nest_target: bool = False,
) -> Dict[str, Any]:
    """Generates the JSON schema for request based on active mutations."""
    id_type = "integer" if type_int else "string"
    id_desc = "User identifier (integer)" if type_int else "Unique identifier of the user (string)"
    id_example = 123 if type_int else "123"

    if nest_target:
        return {
            "type": "object",
            "title": "GetUserRequestMutated",
            "properties": {
                "target": {
                    "type": "object",
                    "title": "TargetIdentifier",
                    "description": "Target entity container",
                    "properties": {
                        "id": {
                            "type": id_type,
                            "title": "Target ID",
                            "description": id_desc,
                            "example": id_example,
                        }
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        }
    elif rename:
        return {
            "type": "object",
            "title": "GetUserRequestMutated",
            "properties": {
                "id": {
                    "type": id_type,
                    "title": "User ID",
                    "description": id_desc,
                    "example": id_example,
                }
            },
            "required": ["id"],
            "additionalProperties": False,
        }
    else:
        return {
            "type": "object",
            "title": "GetUserRequestMutated",
            "properties": {
                "user_id": {
                    "type": id_type,
                    "title": "User ID",
                    "description": id_desc,
                    "example": id_example,
                }
            },
            "required": ["user_id"],
            "additionalProperties": False,
        }


def generate_dynamic_response_schema(wrap_envelope: bool = False) -> Dict[str, Any]:
    """Generates response JSON schema based on envelope mutation."""
    base_user = {
        "type": "object",
        "title": "UserRecord",
        "properties": {
            "id": {"type": "integer", "title": "ID", "example": 123},
            "plan": {"type": "string", "title": "Plan", "example": "basic"},
        },
        "required": ["id", "plan"],
        "additionalProperties": False,
    }

    if wrap_envelope:
        return {
            "type": "object",
            "title": "GetUserResponseEnvelope",
            "properties": {
                "data": base_user,
            },
            "required": ["data"],
            "additionalProperties": False,
        }
    return base_user
