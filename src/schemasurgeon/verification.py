"""Task verification engine for read and write operations."""

from typing import Any, Dict, List, Optional, Tuple
import httpx
from schemasurgeon.models import TaskIntent


class VerificationEngine:
    """Verifies that an API execution fulfilled the user's intent and postconditions."""

    def verify_read_operation(
        self,
        requested_user_id: Any,
        response_data: Any,
        expected_fields: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies read result:
        - Response contains expected entity ID.
        - Wrong entity with HTTP 200 is REJECTED!
        - Expected fields exist.
        """
        if not isinstance(response_data, dict):
            return False, "Response payload is not a dictionary"

        # Entity ID check
        resp_id = response_data.get("id")
        if resp_id is None:
            return False, "Missing 'id' in response payload"

        try:
            req_id_int = int(requested_user_id)
            resp_id_int = int(resp_id)
            if req_id_int != resp_id_int:
                return (
                    False,
                    f"Entity ID mismatch: requested {req_id_int} but response contained {resp_id_int}",
                )
        except (ValueError, TypeError):
            if str(requested_user_id) != str(resp_id):
                return (
                    False,
                    f"Entity ID mismatch: requested '{requested_user_id}' but response contained '{resp_id}'",
                )

        # Expected fields check
        fields_to_check = expected_fields or ["plan"]
        for f in fields_to_check:
            if f not in response_data:
                return False, f"Required field '{f}' missing from verified response"

        return True, None

    async def verify_write_operation(
        self,
        server_url: str,
        user_id: Any,
        expected_plan: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies write result by performing a fresh read against the state endpoint.
        Confirming the state actually changed.
        """
        verify_url = f"{server_url.rstrip('/')}/users/{user_id}"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(verify_url)
                if resp.status_code != 200:
                    return False, f"State verification read failed with HTTP {resp.status_code}"

                data = resp.json()
                actual_plan = data.get("plan")
                if actual_plan != expected_plan:
                    return (
                        False,
                        f"State verification failed: expected plan '{expected_plan}' but actual plan is '{actual_plan}'",
                    )

                return True, None
        except Exception as e:
            return False, f"State verification request failed: {str(e)}"
