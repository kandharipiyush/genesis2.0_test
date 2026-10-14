"""Schema validation utilities using jsonschema."""

from typing import Any, Dict, List, Tuple
import jsonschema


def validate_payload(
    payload: Any,
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validates payload against JSON schema.
    Returns: (is_valid, list_of_error_messages)
    """
    if not schema:
        return True, []

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(payload))
    if not errors:
        return True, []

    formatted_errors = []
    for err in errors:
        path = ".".join(str(p) for p in err.path) or "<root>"
        formatted_errors.append(f"At '{path}': {err.message} (validator: {err.validator})")

    return False, formatted_errors
