# Copyright (c) 2025 GenOrca. All Rights Reserved.

# MCP Router for Editor Tools

from typing import Annotated, List

from fastmcp import FastMCP
from pydantic import Field

from unreal_mcp.core import send_unreal_action

EDITOR_ACTIONS_MODULE = "UnrealMCPython.editor_actions"

editor_mcp = FastMCP(
    name="EditorMCP",
    instructions="Tools for managing and querying Unreal Engine editor functionalities.",
)


@editor_mcp.tool(
    name="get_selected_assets",
    description="Gets the set of currently selected assets.",
    tags={"unreal", "editor", "asset", "selection", "assets"},
)
async def get_selected_assets() -> dict:
    """Gets the set of currently selected assets."""
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, {})


@editor_mcp.tool(
    name="replace_mtl_on_selected",
    description="Replaces a specified material with a new material on all mesh components of the currently selected actors.",
    tags={"unreal", "editor", "actor", "material", "replace", "selected"},
)
async def replace_mtl_on_selected(
    material_to_be_replaced_path: Annotated[str, Field(description="Path to the material to be replaced.")],
    new_material_path: Annotated[str, Field(description="Path to the new material.")],
) -> dict:
    """Replaces materials on mesh components of selected actors."""
    params = {
        "material_to_be_replaced_path": material_to_be_replaced_path,
        "new_material_path": new_material_path,
    }
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, params)


@editor_mcp.tool(
    name="replace_mtl_on_specified",
    description="Replaces a specified material with a new material on all mesh components of actors specified by their paths.",
    tags={"unreal", "editor", "actor", "material", "replace", "specified"},
)
async def replace_mtl_on_specified(
    actor_paths: Annotated[List[str], Field(description="List of actor paths to process.")],
    material_to_be_replaced_path: Annotated[str, Field(description="Path to the material to be replaced.")],
    new_material_path: Annotated[str, Field(description="Path to the new material.")],
) -> dict:
    """Replaces materials on mesh components of specified actors."""
    params = {
        "actor_paths": actor_paths,
        "material_to_be_replaced_path": material_to_be_replaced_path,
        "new_material_path": new_material_path,
    }
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, params)


@editor_mcp.tool(
    name="replace_mesh_on_selected",
    description="Replaces a specified static mesh with a new static mesh on all static mesh components of the currently selected actors.",
    tags={"unreal", "editor", "actor", "mesh", "staticmesh", "replace", "selected"},
)
async def replace_mesh_on_selected(
    mesh_to_be_replaced_path: Annotated[str, Field(description="Path to the static mesh to be replaced.")],
    new_mesh_path: Annotated[str, Field(description="Path to the new static mesh.")],
) -> dict:
    """Replaces static meshes on components of selected actors."""
    params = {
        "mesh_to_be_replaced_path": mesh_to_be_replaced_path,
        "new_mesh_path": new_mesh_path,
    }
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, params)


@editor_mcp.tool(
    name="replace_mesh_on_specified",
    description="Replaces a specified static mesh with a new static mesh on all static mesh components of actors specified by their paths.",
    tags={"unreal", "editor", "actor", "mesh", "staticmesh", "replace", "specified"},
)
async def replace_mesh_on_specified(
    actor_paths: Annotated[List[str], Field(description="List of actor paths to process.")],
    mesh_to_be_replaced_path: Annotated[str, Field(description="Path to the static mesh to be replaced.")],
    new_mesh_path: Annotated[str, Field(description="Path to the new static mesh.")],
) -> dict:
    """Replaces static meshes on components of specified actors."""
    params = {
        "actor_paths": actor_paths,
        "mesh_to_be_replaced_path": mesh_to_be_replaced_path,
        "new_mesh_path": new_mesh_path,
    }
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, params)


@editor_mcp.tool(
    name="replace_selected_with_bp",
    description="Replaces the currently selected actors with new actors spawned from a specified Blueprint asset path.",
    tags={"unreal", "editor", "actor", "blueprint", "replace", "spawn", "selected"},
)
async def replace_selected_with_bp(
    blueprint_asset_path: Annotated[str, Field(description="Path to the Blueprint asset to spawn.")],
) -> dict:
    """Replaces selected actors with instances of a Blueprint."""
    params = {"blueprint_asset_path": blueprint_asset_path}
    return await send_unreal_action(EDITOR_ACTIONS_MODULE, params)
