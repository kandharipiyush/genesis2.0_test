"""FastAPI Mock API Application for SchemaSurgeon."""

from typing import Any, Dict
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
import jsonschema

from fastapi.openapi.docs import get_swagger_ui_html

from mock_api.mutations import active_mutations, MutationState
from mock_api.schemas import (
    generate_dynamic_request_schema,
    generate_dynamic_response_schema,
)

mock_app = FastAPI(
    title="Mock Target API",
    version="1.0.0",
    docs_url=None,
    openapi_url=None,
)

# Simulated in-memory database
USERS_DB: Dict[int, Dict[str, Any]] = {
    123: {"id": 123, "plan": "basic"},
    456: {"id": 456, "plan": "pro"},
    789: {"id": 789, "plan": "enterprise"},
}


@mock_app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Mock Target API",
        "status": "online",
        "endpoints": {
            "swagger_docs": "/docs",
            "openapi_schema": "/openapi.json",
            "get_user": "/get_user",
            "health": "/health",
            "admin_state": "/admin/state",
        },
    }


@mock_app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Mock Target API - Swagger UI",
    )


@mock_app.get("/health")
async def health():
    return {"status": "ok", "service": "mock_api"}


@mock_app.get("/admin/state")
async def get_mutation_state():
    return {
        "status": "ok",
        "mutations": active_mutations.model_dump(),
        "is_v1": active_mutations.is_v1(),
    }


@mock_app.post("/admin/mutate")
async def apply_mutation(mutations: MutationState):
    active_mutations.rename = mutations.rename
    active_mutations.type_int = mutations.type_int
    active_mutations.nest_target = mutations.nest_target
    active_mutations.require_header = mutations.require_header
    active_mutations.wrap_envelope = mutations.wrap_envelope
    return {
        "status": "mutated",
        "mutations": active_mutations.model_dump(),
        "is_v1": active_mutations.is_v1(),
    }


@mock_app.post("/admin/reset")
async def reset_mock_api():
    active_mutations.reset()
    global USERS_DB
    USERS_DB = {
        123: {"id": 123, "plan": "basic"},
        456: {"id": 456, "plan": "pro"},
        789: {"id": 789, "plan": "enterprise"},
    }
    return {
        "status": "reset",
        "mutations": active_mutations.model_dump(),
        "is_v1": True,
    }


@mock_app.get("/openapi.json")
async def dynamic_openapi():
    """Generates an accurate, dynamic OpenAPI document matching active mutations."""
    req_schema = generate_dynamic_request_schema(
        rename=active_mutations.rename,
        type_int=active_mutations.type_int,
        nest_target=active_mutations.nest_target,
    )
    resp_schema = generate_dynamic_response_schema(
        wrap_envelope=active_mutations.wrap_envelope
    )

    parameters = []
    if active_mutations.require_header:
        parameters.append({
            "name": "X-Client-Version",
            "in": "header",
            "required": True,
            "schema": {"type": "string", "enum": ["2"], "default": "2"},
            "description": "Required client version header for v2 contract",
        })

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Mock Target API",
            "version": "2.0.0" if not active_mutations.is_v1() else "1.0.0",
            "description": "Dynamic target API contract with runtime schema mutations.",
        },
        "paths": {
            "/get_user": {
                "post": {
                    "summary": "Get User Details",
                    "operationId": "get_user",
                    "parameters": parameters,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": req_schema,
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful retrieval",
                            "content": {
                                "application/json": {
                                    "schema": resp_schema,
                                }
                            },
                        },
                        "422": {
                            "description": "Validation Error (Schema mismatch)",
                        },
                    },
                }
            },
            "/users/{user_id}": {
                "get": {
                    "summary": "Read User by ID",
                    "operationId": "read_user",
                    "parameters": [
                        {
                            "name": "user_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User found",
                        },
                        "404": {
                            "description": "User not found",
                        },
                    },
                }
            },
        },
    }


@mock_app.post("/get_user")
async def get_user(request: Request):
    """Enforces active schema mutations strictly."""
    # 1. Header validation
    if active_mutations.require_header:
        client_version = request.headers.get("x-client-version")
        if client_version != "2":
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error_class": "schema_validation",
                    "detail": [
                        {
                            "loc": ["header", "x-client-version"],
                            "msg": "Missing or invalid required header: X-Client-Version must be '2'",
                            "type": "missing_header",
                        }
                    ],
                },
            )

    # 2. JSON Body parsing
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_class": "schema_validation",
                "detail": [{"loc": ["body"], "msg": "Invalid JSON payload", "type": "value_error.jsondecode"}],
            },
        )

    # 3. JSON Schema Validation against active mutation contract
    current_schema = generate_dynamic_request_schema(
        rename=active_mutations.rename,
        type_int=active_mutations.type_int,
        nest_target=active_mutations.nest_target,
    )

    validator = jsonschema.Draft7Validator(current_schema)
    errors = list(validator.iter_errors(body))
    if errors:
        error_details = []
        for err in errors:
            error_details.append({
                "loc": ["body"] + list(err.path),
                "msg": err.message,
                "type": f"schema_error.{err.validator}",
                "schema_path": list(err.schema_path),
            })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_class": "schema_validation",
                "detail": error_details,
            },
        )

    # 4. Extract user ID from validated structure
    if active_mutations.nest_target:
        user_id_val = body["target"]["id"]
    elif active_mutations.rename:
        user_id_val = body["id"]
    else:
        user_id_val = body["user_id"]

    try:
        user_id_int = int(user_id_val)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "User ID must be integer parseable"},
        )

    user = USERS_DB.get(user_id_int)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"User {user_id_int} not found"},
        )

    response_payload = {"id": user["id"], "plan": user["plan"]}

    # 5. Envelope wrapping if active
    if active_mutations.wrap_envelope:
        return {"data": response_payload}
    return response_payload


@mock_app.get("/users/{user_id}")
async def read_user(user_id: int):
    """Direct read endpoint for state verification."""
    user = USERS_DB.get(user_id)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"User {user_id} not found"},
        )
    return user


@mock_app.post("/update_plan")
async def update_plan(request: Request):
    """Write operation for verifying actual state change."""
    if active_mutations.require_header:
        client_version = request.headers.get("x-client-version")
        if client_version != "2":
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"error_class": "schema_validation", "detail": "Missing X-Client-Version header"},
            )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=422, content={"detail": "Invalid JSON"})

    # Extract user_id and plan
    if active_mutations.nest_target:
        target = body.get("target", {})
        user_id = target.get("id")
    elif active_mutations.rename:
        user_id = body.get("id")
    else:
        user_id = body.get("user_id")

    plan = body.get("plan")

    if user_id is None or plan is None:
        return JSONResponse(status_code=422, content={"detail": "Missing user_id or plan"})

    try:
        user_id_int = int(user_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": "Invalid user_id"})

    if user_id_int not in USERS_DB:
        return JSONResponse(status_code=404, content={"detail": "User not found"})

    # Side effect: mutate database
    USERS_DB[user_id_int]["plan"] = plan

    result = {"id": user_id_int, "plan": plan}
    if active_mutations.wrap_envelope:
        return {"data": result}
    return result
