# Copyright (c) 2025 GenOrca. All Rights Reserved.

# MCP Router for Blueprint Graph Tools

from typing import Annotated, Optional
from pydantic import Field
from fastmcp import FastMCP

from unreal_mcp.core import send_unreal_action

BP_ACTIONS_MODULE = "UnrealMCPython.blueprint_actions"

blueprint_mcp = FastMCP(
    name="BlueprintMCP",
    instructions="Tools for reading and writing Blueprint graphs in Unreal Engine.",
)

# ─── Read Tools ───────────────────────────────────────────────────────────────

@blueprint_mcp.tool(
    name="get_selected_bp_nodes",
    description="Gets information about currently selected blueprint nodes in the editor.",
    tags={"unreal", "blueprint", "selection", "nodes", "read"}
)
async def get_selected_bp_nodes() -> dict:
    """Gets information about currently selected blueprint nodes in the editor."""
    return await send_unreal_action(BP_ACTIONS_MODULE, {})


@blueprint_mcp.tool(
    name="get_selected_bp_node_infos",
    description="Gets detailed info (including pin connections) about currently selected blueprint nodes. "
                "Optimized for LLM/external tools with compact output format.",
    tags={"unreal", "blueprint", "selection", "nodes", "connections", "read"}
)
async def get_selected_bp_node_infos() -> dict:
    """Gets detailed info about currently selected blueprint nodes."""
    return await send_unreal_action(BP_ACTIONS_MODULE, {})


@blueprint_mcp.tool(
    name="get_blueprint_graph_info",
    description="Returns the full graph structure of a Blueprint (all nodes, pins, and connections). "
                "Use this to understand the current state of a Blueprint's event graph or function graph.",
    tags={"unreal", "blueprint", "graph", "read", "structure"}
)
async def get_blueprint_graph_info(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset (e.g., '/Game/Blueprints/BP_MyActor').")],
    graph_name: Annotated[str, Field(description="Name of the graph to read. Usually 'EventGraph'.")] = "EventGraph"
) -> dict:
    """Returns the full graph info for a Blueprint graph."""
    params = {"asset_path": asset_path, "graph_name": graph_name}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="list_callable_functions",
    description="Lists functions callable from a Blueprint context. "
                "Useful for discovering valid function_name values for add_blueprint_node with type=CallFunction. "
                "Optionally filter by keyword.",
    tags={"unreal", "blueprint", "functions", "list", "read"}
)
async def list_callable_functions(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")],
    filter: Annotated[str, Field(description="Optional keyword filter for function/class names.")] = ""
) -> dict:
    """Lists callable functions available in a Blueprint context."""
    params = {"asset_path": asset_path, "filter": filter}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="list_blueprint_variables",
    description="Lists all variables defined in a Blueprint, including their types and default values.",
    tags={"unreal", "blueprint", "variables", "list", "read"}
)
async def list_blueprint_variables(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")]
) -> dict:
    """Lists all variables defined in a Blueprint."""
    params = {"asset_path": asset_path}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


# ─── Write Tools ──────────────────────────────────────────────────────────────

@blueprint_mcp.tool(
    name="add_blueprint_node",
    description=(
        "Adds a single node to a Blueprint graph. Returns the created node name and its pins for connecting. "
        "Supported node types: "
        "CallFunction (requires function_name, optional target class), "
        "Event (requires event_name like 'ReceiveBeginPlay'), "
        "CustomEvent (requires event_name), "
        "Branch (if/else), "
        "Sequence (execution sequence), "
        "VariableGet (requires variable_name), "
        "VariableSet (requires variable_name), "
        "MacroInstance (requires macro_name like 'ForEachLoop')."
    ),
    tags={"unreal", "blueprint", "node", "add", "write"}
)
async def add_blueprint_node(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")],
    graph_name: Annotated[str, Field(description="Name of the graph. Usually 'EventGraph'.")] = "EventGraph",
    node_type: Annotated[str, Field(description="Type of node: CallFunction, Event, CustomEvent, Branch, Sequence, VariableGet, VariableSet, MacroInstance.")] = "",
    node_config: Annotated[dict, Field(description=(
        "Node configuration. Include 'type' if not specified in node_type. "
        "For CallFunction: {function_name, target?, pin_defaults?}. "
        "For Event: {event_name}. "
        "For CustomEvent: {event_name}. "
        "For VariableGet/Set: {variable_name}. "
        "For MacroInstance: {macro_name}. "
        "Optional: pos_x, pos_y for positioning."
    ))] = {}
) -> dict:
    """Adds a single node to a Blueprint graph."""
    node_json = dict(node_config)
    if node_type and "type" not in node_json:
        node_json["type"] = node_type
    params = {"asset_path": asset_path, "graph_name": graph_name, "node_json": node_json}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="connect_blueprint_pins",
    description="Connects two pins in a Blueprint graph. Use node names from add_blueprint_node or get_blueprint_graph_info. "
                "Pin names can be found in the node's pin list (e.g., 'execute', 'then', 'ReturnValue').",
    tags={"unreal", "blueprint", "pin", "connect", "write"}
)
async def connect_blueprint_pins(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")],
    source_node: Annotated[str, Field(description="Name of the source node.")],
    source_pin: Annotated[str, Field(description="Name of the output pin on the source node.")],
    target_node: Annotated[str, Field(description="Name of the target node.")],
    target_pin: Annotated[str, Field(description="Name of the input pin on the target node.")],
    graph_name: Annotated[str, Field(description="Name of the graph. Usually 'EventGraph'.")] = "EventGraph"
) -> dict:
    """Connects two pins in a Blueprint graph."""
    params = {
        "asset_path": asset_path,
        "graph_name": graph_name,
        "source_node": source_node,
        "source_pin": source_pin,
        "target_node": target_node,
        "target_pin": target_pin
    }
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="remove_blueprint_node",
    description="Removes a node from a Blueprint graph by name. Breaks all pin connections before removal.",
    tags={"unreal", "blueprint", "node", "remove", "delete", "write"}
)
async def remove_blueprint_node(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")],
    node_name: Annotated[str, Field(description="Name of the node to remove.")],
    graph_name: Annotated[str, Field(description="Name of the graph. Usually 'EventGraph'.")] = "EventGraph"
) -> dict:
    """Removes a node from a Blueprint graph."""
    params = {"asset_path": asset_path, "graph_name": graph_name, "node_name": node_name}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="build_blueprint_graph",
    description=(
        "Builds a Blueprint graph from a JSON adjacency list. Removes existing non-event nodes and replaces "
        "them with the provided structure. Use get_blueprint_graph_info to read the current state first. "
        "JSON format: {nodes: [{id, type, ...}], connections: [{source_node, source_pin, target_node, target_pin}]}. "
        "Node types: CallFunction, Event, CustomEvent, Branch, Sequence, VariableGet, VariableSet, MacroInstance."
    ),
    tags={"unreal", "blueprint", "graph", "build", "write"}
)
async def build_blueprint_graph(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")],
    graph_structure: Annotated[dict, Field(description=(
        "JSON object with 'nodes' array and 'connections' array. "
        "Each node: {id, type, function_name?, event_name?, variable_name?, macro_name?, pin_defaults?, pos_x?, pos_y?}. "
        "Each connection: {source_node, source_pin, target_node, target_pin}."
    ))],
    graph_name: Annotated[str, Field(description="Name of the graph. Usually 'EventGraph'.")] = "EventGraph"
) -> dict:
    """Builds a Blueprint graph from JSON adjacency list."""
    params = {"asset_path": asset_path, "graph_name": graph_name, "graph_structure": graph_structure}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)


@blueprint_mcp.tool(
    name="compile_blueprint",
    description="Compiles a Blueprint and returns the compilation result (success/error). "
                "Use after making changes to verify the Blueprint is valid.",
    tags={"unreal", "blueprint", "compile", "write"}
)
async def compile_blueprint(
    asset_path: Annotated[str, Field(description="Path to the Blueprint asset.")]
) -> dict:
    """Compiles a Blueprint and returns the result."""
    params = {"asset_path": asset_path}
    return await send_unreal_action(BP_ACTIONS_MODULE, params)
