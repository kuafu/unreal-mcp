# Copyright (c) 2025 GenOrca. All Rights Reserved.
# UserWidget Blueprint editing actions for Unreal MCP

import unreal  # type: ignore
import json
import traceback


def _load_widget_bp(asset_path):
    """Load a WidgetBlueprint asset. Returns (widget_bp, error_json_str)."""
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        return None, json.dumps({
            "success": False,
            "message": f"Asset not found or failed to load: {asset_path}"
        })
    if not isinstance(asset, unreal.WidgetBlueprint):
        return None, json.dumps({
            "success": False,
            "message": f"Asset at '{asset_path}' is {type(asset).__name__}, expected WidgetBlueprint."
        })
    return asset, None


# ─── Read Actions ─────────────────────────────────────────────────────────────

def ue_widget_get_tree(asset_path: str = None) -> str:
    """Get the full widget hierarchy of a UserWidget Blueprint as JSON."""
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        result_json = unreal.MCPythonHelper.get_widget_tree(widget_bp)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_get_properties(asset_path: str = None, widget_name: str = None) -> str:
    """Get properties of a specific widget element in a UserWidget Blueprint."""
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    if widget_name is None:
        return json.dumps({"success": False, "message": "Required parameter 'widget_name' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        result_json = unreal.MCPythonHelper.get_widget_properties(widget_bp, widget_name)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


# ─── Write Actions ────────────────────────────────────────────────────────────

def ue_widget_create_blueprint(asset_name: str = None, asset_path: str = "/Game/UI") -> str:
    """Create a new UserWidget Blueprint asset with a CanvasPanel root."""
    if asset_name is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_name' is missing."})
    try:
        result_json = unreal.MCPythonHelper.create_widget_blueprint(asset_name, asset_path)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_add_element(asset_path: str = None, element_type: str = None,
                          element_name: str = None, parent_name: str = "",
                          slot_props: dict = None) -> str:
    """Add a widget element to the hierarchy of a UserWidget Blueprint.

    element_type: CanvasPanel | TextBlock | Button | Image | Border |
                  HorizontalBox | VerticalBox | SizeBox | Overlay |
                  ScrollBox | ProgressBar | Slider | EditableTextBox |
                  CheckBox | RichTextBlock | Spacer | NamedSlot
    slot_props: For CanvasPanel slots: {position:[x,y], size:[w,h],
                anchors:{min_x,min_y,max_x,max_y}, alignment:[x,y], z_order:int}
    """
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    if element_type is None:
        return json.dumps({"success": False, "message": "Required parameter 'element_type' is missing."})
    if element_name is None:
        return json.dumps({"success": False, "message": "Required parameter 'element_name' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        slot_props_json = json.dumps(slot_props) if slot_props else "{}"
        result_json = unreal.MCPythonHelper.add_widget_element(
            widget_bp, element_type, element_name, parent_name, slot_props_json)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_remove_element(asset_path: str = None, widget_name: str = None) -> str:
    """Remove a widget element from a UserWidget Blueprint hierarchy."""
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    if widget_name is None:
        return json.dumps({"success": False, "message": "Required parameter 'widget_name' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        result_json = unreal.MCPythonHelper.remove_widget_element(widget_bp, widget_name)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_set_properties(asset_path: str = None, widget_name: str = None,
                              properties: dict = None) -> str:
    """Set properties on a widget element. Supports both widget props and slot props.

    Common properties:
      TextBlock:   text, font_size, color_and_opacity, justification, visibility
      Button:      background_color, visibility, is_enabled
      Image:       brush (asset path string), color_and_opacity, visibility
      Border:      background, content_color_and_opacity, visibility
      CanvasPanel: visibility
    Slot properties (prefixed with 'slot_'):
      slot_position: [x, y]    -- CanvasPanel position
      slot_size: [w, h]         -- CanvasPanel size
      slot_anchors: {min_x, min_y, max_x, max_y}
      slot_alignment: [x, y]   -- pivot point (0-1)
      slot_z_order: int
    Color format: [r, g, b, a] all 0.0-1.0
    """
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    if widget_name is None:
        return json.dumps({"success": False, "message": "Required parameter 'widget_name' is missing."})
    if properties is None:
        return json.dumps({"success": False, "message": "Required parameter 'properties' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        props_json = json.dumps(properties)
        result_json = unreal.MCPythonHelper.set_widget_properties(widget_bp, widget_name, props_json)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_compile(asset_path: str = None) -> str:
    """Compile a UserWidget Blueprint and return the result."""
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    try:
        widget_bp, err = _load_widget_bp(asset_path)
        if err:
            return err
        # Reuse the existing compile_blueprint helper (works for all Blueprint subclasses)
        result_json = unreal.MCPythonHelper.compile_blueprint(widget_bp)
        return result_json
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_widget_save(asset_path: str = None) -> str:
    """Save a UserWidget Blueprint asset to disk."""
    if asset_path is None:
        return json.dumps({"success": False, "message": "Required parameter 'asset_path' is missing."})
    try:
        success = unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
        if success:
            return json.dumps({"success": True, "message": f"Widget Blueprint saved: {asset_path}"})
        else:
            return json.dumps({"success": False, "message": f"Failed to save asset: {asset_path}"})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})
