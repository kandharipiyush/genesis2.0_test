"""Pytest fixtures for SchemaSurgeon test suite."""

import asyncio
import os
import tempfile
from typing import AsyncGenerator
import pytest
import pytest_asyncio
import httpx
from schemasurgeon.config import settings
from schemasurgeon.models import ToolContract
from schemasurgeon.registry import ToolRegistry
from schemasurgeon.audit import AuditLogger
from schemasurgeon.usps.drift_memory import DriftMemory
from schemasurgeon.gateway import SchemaSurgeonGateway
from mock_api.app import mock_app
from mock_api.mutations import active_mutations
from mock_api.schemas import get_v1_request_schema, get_v1_response_schema


@pytest.fixture(autouse=True)
def reset_global_state():
    """Resets mock mutations and global state before every test."""
    active_mutations.reset()
    yield
    active_mutations.reset()


@pytest.fixture
def temp_audit_logger():
    """Creates a temporary audit logger writing to a scratch file."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        temp_path = f.name
    logger = AuditLogger(log_path=temp_path)
    yield logger
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def fresh_registry():
    """Creates a fresh, isolated ToolRegistry populated with v1 get_user."""
    reg = ToolRegistry()
    v1_contract = ToolContract(
        tool_name="get_user",
        version=1,
        method="POST",
        path="/get_user",
        request_schema=get_v1_request_schema(),
        response_schema=get_v1_response_schema(),
        server_url="http://127.0.0.1:8001",
        required_headers={},
    )
    reg.register(v1_contract)
    return reg


@pytest.fixture
def fresh_drift_memory():
    """Creates an isolated DriftMemory instance."""
    return DriftMemory()


@pytest_asyncio.fixture
async def mock_api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """In-memory ASGI client for the mock API."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app),
        base_url="http://127.0.0.1:8001",
    ) as client:
        yield client


@pytest.fixture
def isolated_gateway(fresh_registry, temp_audit_logger, fresh_drift_memory):
    """Creates an isolated SchemaSurgeonGateway with local dependencies."""
    gw = SchemaSurgeonGateway(
        registry=fresh_registry,
        audit_logger=temp_audit_logger,
        drift_memory=fresh_drift_memory,
    )
    return gw
