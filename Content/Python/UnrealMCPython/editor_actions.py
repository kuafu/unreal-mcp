# Copyright (c) 2025 GenOrca. All Rights Reserved.

import warnings

import unreal
import json
import traceback
from typing import List, Dict, Any

# Suppress DeprecationWarning for EditorLevelLibrary functions that have no
# subsystem equivalent yet (replace_mesh_*, replace_selected_actors, refresh_all_level_editors).
warnings.filterwarnings("ignore", message=".*EditorLevelLibrary.*deprecated.*", category=DeprecationWarning)


# ---------------------------------------------------------------------------
# Helpers — asset loading
# ---------------------------------------------------------------------------

def _load_material_interface(material_path: str):
    """Load and validate a MaterialInterface (Material or MaterialInstance)."""
    material = unreal.EditorAssetLibrary.load_asset(material_path)
    if not material:
        raise FileNotFoundError(f"Material asset not found at path: {material_path}")
    if not isinstance(material, unreal.MaterialInterface):
        raise TypeError(f"Asset at {material_path} is not a MaterialInterface, but {type(material).__name__}")
    return material


def _load_static_mesh(mesh_path: str):
    """Load and validate a StaticMesh asset."""
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
    if not mesh:
        raise FileNotFoundError(f"StaticMesh asset not found at path: {mesh_path}")
    if not isinstance(mesh, unreal.StaticMesh):
        raise TypeError(f"Asset at {mesh_path} is not a StaticMesh, but {type(mesh).__name__}")
    return mesh


# ---------------------------------------------------------------------------
# Helpers — actor / component introspection
# ---------------------------------------------------------------------------

def _get_actors_by_paths(actor_paths: List[str]) -> List[unreal.Actor]:
    """Resolve a list of actor path strings to actor objects."""
    all_level_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    actors = []
    for path in actor_paths:
        actor = next((a for a in all_level_actors if a.get_path_name() == path), None)
        if actor:
            actors.append(actor)
        else:
            unreal.log_warning(f"MCP: Actor not found at path: {path}")
    return actors


def _get_component_material_paths(component: unreal.MeshComponent) -> List[str]:
    """Return ordered list of material paths for every slot on a mesh component."""
    if not component:
        return []
    return [
        material.get_path_name() if material else ""
        for i in range(component.get_num_materials())
        for material in [component.get_material(i)]
    ]


def _get_asset_map_for_actors(actors: List[unreal.Actor], component_class, asset_getter) -> Dict[str, List[str]]:
    """
    Build a map of {actor_path: [asset_paths]} for a given component class.
    ``asset_getter(component) -> str|None`` extracts the asset path from a component.
    """
    result = {}
    for actor in actors:
        if not actor:
            continue
        paths = set()
        for comp in actor.get_components_by_class(component_class):
            path = asset_getter(comp)
            if path:
                paths.add(path)
        result[actor.get_path_name()] = sorted(paths)
    return result


def _get_materials_map_for_actors(actors: List[unreal.Actor]) -> Dict[str, List[str]]:
    def _getter(comp):
        paths = set()
        for i in range(comp.get_num_materials()):
            mat = comp.get_material(i)
            if mat:
                paths.add(mat.get_path_name())
        return paths
    result = {}
    for actor in actors:
        if not actor:
            continue
        actor_paths = set()
        for comp in actor.get_components_by_class(unreal.MeshComponent.static_class()):
            if comp:
                actor_paths.update(_getter(comp))
        result[actor.get_path_name()] = sorted(actor_paths)
    return result


def _get_meshes_map_for_actors(actors: List[unreal.Actor]) -> Dict[str, List[str]]:
    return _get_asset_map_for_actors(
        actors,
        unreal.StaticMeshComponent.static_class(),
        lambda comp: comp.static_mesh.get_path_name() if comp and hasattr(comp, 'static_mesh') and comp.static_mesh else None,
    )


def _get_skeletal_meshes_map_for_actors(actors: List[unreal.Actor]) -> Dict[str, List[str]]:
    return _get_asset_map_for_actors(
        actors,
        unreal.SkeletalMeshComponent.static_class(),
        lambda comp: comp.skeletal_mesh.get_path_name() if comp and hasattr(comp, 'skeletal_mesh') and comp.skeletal_mesh else None,
    )


# ---------------------------------------------------------------------------
# Helpers — material replacement change detection
# ---------------------------------------------------------------------------

def _detect_material_changes(
    mesh_components: list,
    initial_materials_map: Dict[str, List[str]],
    old_material_path: str,
    new_material_path: str,
) -> tuple:
    """
    Compare before/after material slots and return (count, affected_paths).
    """
    count = 0
    affected = []
    for comp in mesh_components:
        current = _get_component_material_paths(comp)
        original = initial_materials_map.get(comp.get_path_name(), [])
        for idx, orig_path in enumerate(original):
            if orig_path == old_material_path:
                if idx < len(current) and current[idx] == new_material_path:
                    count += 1
                    affected.append(comp.get_path_name())
                    break
    return count, affected


# ---------------------------------------------------------------------------
# Helpers — mesh replacement
# ---------------------------------------------------------------------------

def _collect_mesh_components(actors: list) -> list:
    """Gather all StaticMeshComponent instances from a list of actors."""
    components = []
    for actor in actors:
        comps = actor.get_components_by_class(unreal.StaticMeshComponent.static_class())
        components.extend(c for c in comps if c)
    return components


def _is_empty_mesh_path(path: str) -> bool:
    return not path or path.lower() in ("", "none", "any")


def _replace_meshes_on_components(actors, mesh_to_replace, new_mesh, all_mesh_components):
    """
    Try the batch API first, fall back to manual per-component replacement.
    """
    if hasattr(unreal.EditorLevelLibrary, "replace_mesh_components_meshes_on_actors"):
        unreal.EditorLevelLibrary.replace_mesh_components_meshes_on_actors(actors, mesh_to_replace, new_mesh)
    else:
        for comp in all_mesh_components:
            current = comp.static_mesh
            should_replace = False
            if not mesh_to_replace:
                should_replace = current != new_mesh
            elif current and current.get_path_name() == mesh_to_replace.get_path_name():
                should_replace = current.get_path_name() != new_mesh.get_path_name()
            elif not current and not mesh_to_replace:
                should_replace = True
            if should_replace:
                comp.set_static_mesh(new_mesh)


def _detect_mesh_changes(all_mesh_components, initial_meshes_map, mesh_to_replace, new_mesh):
    """
    Compare before/after meshes and return (count, affected_paths, unchanged_info).
    """
    changed_count = 0
    affected_paths = []
    unchanged_info = []
    new_mesh_path = new_mesh.get_path_name()
    replace_path = mesh_to_replace.get_path_name() if mesh_to_replace else None

    for comp in all_mesh_components:
        before = initial_meshes_map.get(comp.get_path_name(), "")
        after = comp.static_mesh.get_path_name() if comp.static_mesh else ""
        owner = comp.get_owner()
        owner_name = owner.get_name() if owner else "Unknown"

        if replace_path:
            if before == replace_path and after == new_mesh_path:
                changed_count += 1
                affected_paths.append(comp.get_path_name())
            else:
                is_candidate = before == replace_path
                unchanged_info.append({
                    "component_path": comp.get_path_name(),
                    "component_name": comp.get_name(),
                    "actor_name": owner_name,
                    "current_mesh": before,
                    "is_candidate": is_candidate,
                    "reason": (
                        "Component is a candidate but was not changed" if is_candidate
                        else "Current mesh doesn't match the mesh to be replaced"
                    ),
                })
        else:
            if before != after and after == new_mesh_path:
                changed_count += 1
                affected_paths.append(comp.get_path_name())
            else:
                unchanged_info.append({
                    "component_path": comp.get_path_name(),
                    "component_name": comp.get_name(),
                    "actor_name": owner_name,
                    "current_mesh": before,
                    "is_candidate": False,
                    "reason": (
                        "Component already has the target mesh" if before == new_mesh_path
                        else "Failed to set new mesh"
                    ),
                })

    return changed_count, affected_paths, unchanged_info


# ---------------------------------------------------------------------------
# Public actions — asset selection
# ---------------------------------------------------------------------------

def ue_get_selected_assets() -> str:
    """Gets the set of currently selected assets."""
    try:
        selected = unreal.EditorUtilityLibrary.get_selected_assets()
        assets = [
            {
                "asset_name": a.get_name(),
                "asset_path": a.get_path_name(),
                "asset_class": a.get_class().get_name(),
            }
            for a in selected
        ]
        return json.dumps({"success": True, "selected_assets": assets})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e)})


# ---------------------------------------------------------------------------
# Public actions — material replacement
# ---------------------------------------------------------------------------

def _replace_materials_on_actors(actors, material_to_be_replaced_path, new_material_path, use_batch_api):
    """
    Shared logic for material replacement on a list of actors.
    ``use_batch_api`` selects between the selected-actors and specified-actors UE APIs.
    """
    material_to_replace = _load_material_interface(material_to_be_replaced_path)
    new_material = _load_material_interface(new_material_path)

    mesh_components = []
    for actor in actors:
        comps = actor.get_components_by_class(unreal.MeshComponent.static_class())
        mesh_components.extend(c for c in comps if c)

    if not mesh_components:
        return json.dumps({"success": False, "message": "No mesh components found on the target actors."})

    initial_map = {comp.get_path_name(): _get_component_material_paths(comp) for comp in mesh_components}

    if use_batch_api:
        unreal.EditorLevelLibrary.replace_mesh_components_materials_on_actors(actors, material_to_replace, new_material)
    else:
        unreal.EditorLevelLibrary.replace_mesh_components_materials(mesh_components, material_to_replace, new_material)

    count, affected = _detect_material_changes(mesh_components, initial_map, material_to_replace.get_path_name(), new_material.get_path_name())

    if count > 0:
        return json.dumps({
            "success": True,
            "message": f"Replaced material '{material_to_be_replaced_path}' with '{new_material_path}' on {count} component(s) across {len(actors)} actor(s).",
            "affected_actors_count": len(actors),
            "affected_components_count": count,
            "affected_component_paths": affected,
        })
    return json.dumps({
        "success": False,
        "message": f"Target material '{material_to_be_replaced_path}' not found or not replaced on any mesh components.",
    })


def ue_replace_mtl_on_selected(material_to_be_replaced_path: str, new_material_path: str) -> str:
    try:
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
        if not actors:
            return json.dumps({"success": False, "message": "No actors selected."})
        return _replace_materials_on_actors(actors, material_to_be_replaced_path, new_material_path, use_batch_api=False)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_replace_mtl_on_specified(actor_paths: List[str], material_to_be_replaced_path: str, new_material_path: str) -> str:
    try:
        actors = _get_actors_by_paths(actor_paths)
        if not actors:
            return json.dumps({"success": False, "message": "No valid actors found from the provided paths."})
        return _replace_materials_on_actors(actors, material_to_be_replaced_path, new_material_path, use_batch_api=True)
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


# ---------------------------------------------------------------------------
# Public actions — mesh replacement
# ---------------------------------------------------------------------------

def _replace_meshes_on_actors(actors, mesh_to_be_replaced_path: str, new_mesh_path: str, include_diagnostics: bool = False) -> str:
    """
    Shared logic for static mesh replacement on a list of actors.
    When ``include_diagnostics`` is True, failure responses include extra asset maps.
    """
    # Validate replacement mesh exists
    if not _is_empty_mesh_path(mesh_to_be_replaced_path):
        try:
            _load_static_mesh(mesh_to_be_replaced_path)
        except FileNotFoundError:
            return json.dumps({
                "success": False,
                "message": f"The mesh_to_be_replaced_path '{mesh_to_be_replaced_path}' does not exist as a StaticMesh asset.",
                "error_type": "MeshToReplaceNotFound",
            })

    mesh_to_replace = None
    if not _is_empty_mesh_path(mesh_to_be_replaced_path):
        mesh_to_replace = _load_static_mesh(mesh_to_be_replaced_path)
    new_mesh = _load_static_mesh(new_mesh_path)

    all_components = _collect_mesh_components(actors)
    if not all_components:
        result = {"success": False, "message": "No static mesh components found on target actors."}
        if include_diagnostics:
            result["specified_actors_info"] = [{"name": a.get_name(), "class": a.get_class().get_name()} for a in actors]
            result["current_materials"] = _get_materials_map_for_actors(actors)
            result["current_meshes"] = _get_meshes_map_for_actors(actors)
            result["current_skeletal_meshes"] = _get_skeletal_meshes_map_for_actors(actors)
        return json.dumps(result)

    initial_map = {
        comp.get_path_name(): comp.static_mesh.get_path_name() if comp.static_mesh else ""
        for comp in all_components
    }

    _replace_meshes_on_components(actors, mesh_to_replace, new_mesh, all_components)

    changed_count, affected_paths, unchanged_info = _detect_mesh_changes(all_components, initial_map, mesh_to_replace, new_mesh)

    if changed_count > 0:
        result = {
            "success": True,
            "message": f"Replaced mesh on {changed_count} component(s) across {len(actors)} actor(s).",
            "affected_actors_count": len(actors),
            "affected_components_count": changed_count,
            "affected_component_paths": affected_paths,
        }
        if include_diagnostics and unchanged_info:
            result["unchanged_components"] = unchanged_info
        return json.dumps(result)

    result = {
        "success": False,
        "message": f"Target mesh '{mesh_to_be_replaced_path}' not found or not replaced on any static mesh components.",
    }
    if include_diagnostics:
        result["current_materials"] = _get_materials_map_for_actors(actors)
        result["current_meshes"] = _get_meshes_map_for_actors(actors)
        result["current_skeletal_meshes"] = _get_skeletal_meshes_map_for_actors(actors)
        result["unchanged_components"] = unchanged_info
    return json.dumps(result)


def ue_replace_mesh_on_selected(mesh_to_be_replaced_path: str, new_mesh_path: str) -> str:
    """Replaces static meshes on components of selected actors."""
    try:
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
        if not actors:
            return json.dumps({"success": True, "message": "No actors selected.", "changed_actors_count": 0, "changed_components_count": 0})
        return _replace_meshes_on_actors(actors, mesh_to_be_replaced_path, new_mesh_path)
    except Exception as e:
        unreal.log_error(f"MCP: Error in ue_replace_mesh_on_selected: {e}\n{traceback.format_exc()}")
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


def ue_replace_mesh_on_specified(actor_paths: List[str], mesh_to_be_replaced_path: str, new_mesh_path: str) -> str:
    """Replaces static meshes on components of specified actors."""
    try:
        actors = _get_actors_by_paths(actor_paths)
        if not actors:
            return json.dumps({"success": False, "message": "No valid actors found from the provided paths."})
        return _replace_meshes_on_actors(actors, mesh_to_be_replaced_path, new_mesh_path, include_diagnostics=True)
    except Exception as e:
        unreal.log_error(f"MCP: Error in ue_replace_mesh_on_specified: {e}\n{traceback.format_exc()}")
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})


# ---------------------------------------------------------------------------
# Public actions — actor replacement
# ---------------------------------------------------------------------------

def ue_replace_selected_with_bp(blueprint_asset_path: str) -> str:
    """Replaces selected actors with new actors spawned from a Blueprint asset."""
    try:
        selected = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
        if not selected:
            return json.dumps({"success": False, "message": "No actors selected."})

        blueprint = unreal.EditorAssetLibrary.load_asset(blueprint_asset_path)
        if not blueprint:
            return json.dumps({"success": False, "message": f"Blueprint asset not found at path: {blueprint_asset_path}"})

        unreal.EditorLevelLibrary.replace_selected_actors(blueprint_asset_path)
        return json.dumps({
            "success": True,
            "message": f"Replaced {len(selected)} actors with Blueprint '{blueprint_asset_path}'.",
            "replaced_actors_count": len(selected),
        })
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})
