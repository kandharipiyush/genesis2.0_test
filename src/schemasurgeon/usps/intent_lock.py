"""USP 4: Intent Lock - Ensures request repair preserves user intent and constraints."""

from typing import Any, Dict, List, Optional, Tuple
from schemasurgeon.models import TaskIntent


class IntentLock:
    """Enforces that candidate transformations preserve original task intent and postconditions."""

    def __init__(self):
        pass

    def validate_request_intent(
        self,
        intent: Optional[TaskIntent],
        original_args: Dict[str, Any],
        transformed_args: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensures the repaired request still targets the same entity and operation.
        """
        if not intent:
            return True, None

        constraints = intent.constraints

        # 1. Entity identifier preservation check
        if "user_id" in constraints:
            orig_id = str(constraints["user_id"])

            # Check if orig_id exists anywhere in transformed arguments
            found = False

            def _search_val(d: Any) -> bool:
                if isinstance(d, dict):
                    return any(_search_val(v) for v in d.values())
                elif isinstance(d, list):
                    return any(_search_val(v) for v in d)
                else:
                    return str(d) == orig_id

            if not _search_val(transformed_args):
                return (
                    False,
                    f"Intent Lock violation: Target user_id '{orig_id}' was lost in transformed request",
                )

        return True, None

    def validate_response_intent(
        self,
        intent: Optional[TaskIntent],
        response_data: Any,
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensures the API response satisfies postconditions and entity constraints.
        A technically successful HTTP 200 with wrong entity MUST be rejected!
        """
        if not intent:
            return True, None

        constraints = intent.constraints
        if not isinstance(response_data, dict):
            return False, "Intent Lock violation: Response is not a structured dictionary"

        # Check entity ID in response
        if "user_id" in constraints:
            expected_id = str(constraints["user_id"])
            actual_id = response_data.get("id") or response_data.get("user_id")

            if actual_id is None:
                return (
                    False,
                    f"Intent Lock violation: Response missing expected entity identifier field",
                )

            if str(actual_id) != expected_id:
                return (
                    False,
                    f"Intent Lock violation: Requested entity '{expected_id}' but received '{actual_id}' (HTTP 200 wrong target rejected)",
                )

        # Check postconditions
        for postcond in intent.postconditions:
            if postcond == "plan_exists" and "plan" not in response_data:
                return False, "Intent Lock violation: Expected postcondition 'plan_exists' failed"

        return True, None
