"""Baseline Agent without SchemaSurgeon self-healing or hot-patching."""

import time
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel, Field


class BaselineOutcome(BaseModel):
    task: str
    success: bool
    status_code: Optional[int] = None
    response: Optional[Any] = None
    retries_used: int = 0
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    tokens_used: int = 0


class BaselineAgent:
    """
    Standard agent that executes API tools directly with conventional retry logic.
    Does NOT possess schema diagnosis, deterministic request repair, or hot-patching.
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8001", max_retries: int = 1):
        self.server_url = server_url.rstrip("/")
        self.max_retries = max_retries

    async def execute_task(
        self,
        endpoint: str = "/get_user",
        arguments: Optional[Dict[str, Any]] = None,
        expected_user_id: int = 123,
    ) -> BaselineOutcome:
        """Executes task with standard static payload and standard retry."""
        start_time = time.time()
        args = arguments or {"user_id": "123"}
        url = f"{self.server_url}{endpoint}"
        retries = 0
        last_status = None
        last_resp = None
        last_err = None

        # Simulated standard prompt tokens for LLM tool call
        tokens_used = 150

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                retries += 1
                tokens_used += 120  # Additional tokens consumed on re-prompting model

            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(url, json=args)
                    last_status = resp.status_code
                    try:
                        last_resp = resp.json()
                    except Exception:
                        last_resp = resp.text

                    if resp.status_code == 200 and isinstance(last_resp, dict):
                        # Task verification
                        user_id = last_resp.get("id")
                        if user_id == expected_user_id:
                            dur_ms = (time.time() - start_time) * 1000.0
                            return BaselineOutcome(
                                task="get_user",
                                success=True,
                                status_code=200,
                                response=last_resp,
                                retries_used=retries,
                                duration_ms=dur_ms,
                                tokens_used=tokens_used,
                            )
            except Exception as e:
                last_err = str(e)

        dur_ms = (time.time() - start_time) * 1000.0
        return BaselineOutcome(
            task="get_user",
            success=False,
            status_code=last_status,
            response=last_resp,
            retries_used=retries,
            duration_ms=dur_ms,
            error_message=last_err or f"Failed with HTTP {last_status}",
            tokens_used=tokens_used,
        )
