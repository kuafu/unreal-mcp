# Copyright (c) 2025 GenOrca. All Rights Reserved.
# MCP Router for UserWidget Blueprint editing tools

from typing import Annotated, Optional
from pydantic import Field
from fastmcp import FastMCP

from unreal_mcp.core import send_unreal_action

WIDGET_ACTIONS_MODULE = "UnrealMCPython.widget_actions"

widget_mcp = FastMCP(
    name="WidgetMCP",
    description="Tools for reading and editing UserWidget Blueprint UI elements in Unreal Engine UMG."
)

# ─── Read Tools ───────────────────────────────────────────────────────────────

@widget_mcp.tool(
    name="widget_get_tree",
    description=(
        "Gets the full widget hierarchy of a UserWidget Blueprint as a JSON tree. "
        "Returns all widget elements with their names, types, parent relationships, "
        "and key properties. Use this to understand the current UI structure before making edits."
    ),
    tags={"unreal", "widget", "umg", "hierarchy", "read"}
)
async def widget_get_tree(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset (e.g., '/Game/UI/WBP_HUD').")]
) -> dict:
    """Gets the full widget hierarchy of a UserWidget Blueprint."""
    params = {"asset_path": asset_path}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_get_properties",
    description=(
        "Gets all properties of a specific widget element within a UserWidget Blueprint. "
        "Returns the widget's own properties and its slot properties (position, size, anchors, etc.). "
        "Use widget_get_tree first to find valid widget names."
    ),
    tags={"unreal", "widget", "umg", "properties", "read"}
)
async def widget_get_properties(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")],
    widget_name: Annotated[str, Field(description="Name of the widget element to inspect.")]
) -> dict:
    """Gets properties of a specific widget element."""
    params = {"asset_path": asset_path, "widget_name": widget_name}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


# ─── Write Tools ──────────────────────────────────────────────────────────────

@widget_mcp.tool(
    name="widget_create_blueprint",
    description=(
        "Creates a new UserWidget Blueprint asset with an empty CanvasPanel as the root widget. "
        "The asset will be saved at the specified path. "
        "After creation, use widget_add_element to populate the UI."
    ),
    tags={"unreal", "widget", "umg", "create", "write"}
)
async def widget_create_blueprint(
    asset_name: Annotated[str, Field(description="Name of the new Widget Blueprint (e.g., 'WBP_MyWidget').")],
    asset_path: Annotated[str, Field(description="Content browser path to create the asset in.")] = "/Game/UI"
) -> dict:
    """Creates a new UserWidget Blueprint with a CanvasPanel root."""
    params = {"asset_name": asset_name, "asset_path": asset_path}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_add_element",
    description=(
        "Adds a widget element to the hierarchy of an existing UserWidget Blueprint. "
        "The element is attached to the specified parent (or the root widget if parent_name is empty). "
        "Supported element types: CanvasPanel, TextBlock, Button, Image, Border, "
        "HorizontalBox, VerticalBox, SizeBox, Overlay, ScrollBox, ProgressBar, "
        "Slider, EditableTextBox, CheckBox, RichTextBlock, Spacer, NamedSlot. "
        "For CanvasPanel parents, use slot_props to set position and size."
    ),
    tags={"unreal", "widget", "umg", "add", "element", "write"}
)
async def widget_add_element(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")],
    element_type: Annotated[str, Field(description=(
        "Widget class to add. Examples: 'TextBlock', 'Button', 'Image', 'CanvasPanel', "
        "'Border', 'HorizontalBox', 'VerticalBox', 'SizeBox', 'Overlay', 'ScrollBox', "
        "'ProgressBar', 'Slider', 'EditableTextBox', 'CheckBox', 'RichTextBlock', 'Spacer'."
    ))],
    element_name: Annotated[str, Field(description="Unique name for the new widget element.")],
    parent_name: Annotated[str, Field(description=(
        "Name of the parent widget to attach to. Leave empty to attach to the root widget."
    ))] = "",
    slot_props: Annotated[dict, Field(description=(
        "Slot (layout) properties for the new element. "
        "For CanvasPanel slots: {position:[x,y], size:[w,h], "
        "anchors:{min_x:0,min_y:0,max_x:0,max_y:0}, alignment:[0,0], z_order:0}. "
        "For HorizontalBox/VerticalBox: {fill_type:'Auto'|'Fill', fill_value:1.0}."
    ))] = {}
) -> dict:
    """Adds a widget element to the hierarchy."""
    params = {
        "asset_path": asset_path,
        "element_type": element_type,
        "element_name": element_name,
        "parent_name": parent_name,
        "slot_props": slot_props
    }
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_remove_element",
    description=(
        "Removes a widget element from the UserWidget Blueprint hierarchy. "
        "Also removes all children of the removed widget. "
        "Cannot remove the root widget — use widget_set_properties to hide it instead."
    ),
    tags={"unreal", "widget", "umg", "remove", "delete", "write"}
)
async def widget_remove_element(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")],
    widget_name: Annotated[str, Field(description="Name of the widget element to remove.")]
) -> dict:
    """Removes a widget element from the hierarchy."""
    params = {"asset_path": asset_path, "widget_name": widget_name}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_set_properties",
    description=(
        "Sets properties on a widget element in a UserWidget Blueprint. "
        "Supports widget properties and slot properties (prefixed with 'slot_'). "
        "Common widget properties: "
        "text (string), font_size (int), color_and_opacity ([r,g,b,a]), "
        "background_color ([r,g,b,a]), visibility ('Visible'|'Hidden'|'Collapsed'), "
        "is_enabled (bool), brush (asset path string for Image), "
        "percent (float, for ProgressBar), value (float, for Slider). "
        "Slot properties (CanvasPanel): "
        "slot_position ([x,y]), slot_size ([w,h]), "
        "slot_anchors ({min_x,min_y,max_x,max_y}), "
        "slot_alignment ([x,y]), slot_z_order (int). "
        "Colors use [r,g,b,a] with values 0.0-1.0."
    ),
    tags={"unreal", "widget", "umg", "properties", "set", "write"}
)
async def widget_set_properties(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")],
    widget_name: Annotated[str, Field(description="Name of the widget element to modify.")],
    properties: Annotated[dict, Field(description=(
        "Dictionary of properties to set. "
        "Examples: {\"text\": \"Hello\", \"font_size\": 24, \"slot_position\": [100, 200], "
        "\"slot_size\": [300, 50], \"color_and_opacity\": [1.0, 0.5, 0.0, 1.0], "
        "\"visibility\": \"Visible\"}."
    ))]
) -> dict:
    """Sets properties on a widget element."""
    params = {"asset_path": asset_path, "widget_name": widget_name, "properties": properties}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_compile",
    description=(
        "Compiles a UserWidget Blueprint and returns the compilation result. "
        "Run this after making structural changes (adding/removing elements) "
        "to verify the widget is valid before saving."
    ),
    tags={"unreal", "widget", "umg", "compile", "write"}
)
async def widget_compile(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")]
) -> dict:
    """Compiles a UserWidget Blueprint."""
    params = {"asset_path": asset_path}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)


@widget_mcp.tool(
    name="widget_save",
    description=(
        "Saves a UserWidget Blueprint asset to disk. "
        "Call this after widget_compile succeeds to persist all changes."
    ),
    tags={"unreal", "widget", "umg", "save", "write"}
)
async def widget_save(
    asset_path: Annotated[str, Field(description="Path to the UserWidget Blueprint asset.")]
) -> dict:
    """Saves a UserWidget Blueprint to disk."""
    params = {"asset_path": asset_path}
    return await send_unreal_action(WIDGET_ACTIONS_MODULE, params)
