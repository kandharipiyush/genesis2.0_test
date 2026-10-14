"""LangChain and LangGraph integration with live runtime tool rebinding."""

from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, create_model, Field
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END

from schemasurgeon.models import ToolContract, TaskIntent
from schemasurgeon.registry import ToolRegistry, registry as default_registry
from schemasurgeon.gateway import SchemaSurgeonGateway


def pydantic_model_from_json_schema(
    schema: Dict[str, Any],
    model_name: str = "DynamicToolArgs",
) -> Type[BaseModel]:
    """Generates a dynamic Pydantic model from a JSON Schema."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: Dict[str, Any] = {}

    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }

    for prop_name, prop_def in properties.items():
        prop_type_str = prop_def.get("type", "string")

        if prop_type_str == "object" and "properties" in prop_def:
            # Sub-model for nested properties (e.g. target: {id: int})
            sub_model = pydantic_model_from_json_schema(
                prop_def, model_name=f"{model_name}_{prop_name.capitalize()}"
            )
            is_req = prop_name in required
            fields[prop_name] = (sub_model, ... if is_req else None)
        else:
            py_type = type_mapping.get(prop_type_str, str)
            is_req = prop_name in required
            desc = prop_def.get("description", "")
            fields[prop_name] = (
                py_type,
                Field(default=... if is_req else None, description=desc),
            )

    return create_model(model_name, **fields)


def build_langchain_tool(
    contract: ToolContract,
    gateway: SchemaSurgeonGateway,
    intent: Optional[TaskIntent] = None,
) -> StructuredTool:
    """Builds a LangChain StructuredTool dynamically from a ToolContract."""
    args_schema = pydantic_model_from_json_schema(
        contract.request_schema, model_name=f"{contract.tool_name}_Args_v{contract.version}"
    )

    async def _tool_executor(**kwargs) -> Dict[str, Any]:
        cleaned = {}
        for k, v in kwargs.items():
            if hasattr(v, "model_dump"):
                cleaned[k] = v.model_dump()
            elif hasattr(v, "dict"):
                cleaned[k] = v.dict()
            else:
                cleaned[k] = v

        outcome = await gateway.execute_tool(
            tool_name=contract.tool_name,
            arguments=cleaned,
            intent=intent,
        )
        return outcome.model_dump()

    return StructuredTool(
        name=contract.tool_name,
        description=f"Tool for {contract.tool_name} (version {contract.version})",
        args_schema=args_schema,
        coroutine=_tool_executor,
    )


class AgentState(BaseModel):
    task: str
    step: int = 0
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    tool_result: Optional[Dict[str, Any]] = None
    step_schemas: List[Dict[str, Any]] = Field(default_factory=list)
    active_versions_seen: List[int] = Field(default_factory=list)
    status: str = "running"


class HealingAgent:
    """
    LangGraph-based AI agent that dynamically discovers and re-binds active tools
    at each model step without requiring process restart.
    """

    def __init__(
        self,
        gateway: SchemaSurgeonGateway,
        registry: Optional[ToolRegistry] = None,
        tool_name: str = "get_user",
    ):
        self.gateway = gateway
        self.registry = registry or default_registry
        self.tool_name = tool_name
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        async def model_node(state: AgentState) -> Dict[str, Any]:
            # Step dynamic binding: lookup active tool from registry on every step
            contract = self.registry.get_active(self.tool_name)
            if not contract:
                return {"status": "error", "step": state.step + 1}

            # Build tool and inspect its bound schema
            tool = build_langchain_tool(contract, self.gateway)
            bound_schema = tool.args_schema.model_json_schema()

            step = state.step + 1
            new_schemas = list(state.step_schemas)
            new_schemas.append({
                "step": step,
                "version": contract.version,
                "schema": bound_schema,
            })
            new_versions = list(state.active_versions_seen)
            new_versions.append(contract.version)

            return {
                "step": step,
                "step_schemas": new_schemas,
                "active_versions_seen": new_versions,
            }

        async def tool_node(state: AgentState) -> Dict[str, Any]:
            contract = self.registry.get_active(self.tool_name)
            if not contract:
                return {"status": "error"}

            tool = build_langchain_tool(contract, self.gateway)
            result = await tool.ainvoke(state.tool_args)
            return {"tool_result": result, "status": "completed"}

        builder.add_node("model_step", model_node)
        builder.add_node("tool_step", tool_node)

        builder.set_entry_point("model_step")
        builder.add_edge("model_step", "tool_step")
        builder.add_edge("tool_step", END)

        return builder.compile()

    async def run_step(self, tool_args: Dict[str, Any], initial_state: Optional[AgentState] = None) -> AgentState:
        """Executes a single model+tool step in the graph."""
        state = initial_state or AgentState(task="retrieve_user")
        state.tool_args = tool_args
        raw_result = await self.graph.ainvoke(state.model_dump())
        return AgentState(**raw_result)
