# CLAUDE.md

## Project Overview

Unreal MCP is a bridge connecting AI assistants (Claude, Cursor, VS Code Copilot) to the Unreal Engine 5.6+ editor via the Model Context Protocol (MCP). It provides 62 tools across 8 categories for natural language control of editor tasks.

**Architecture (3 layers):**
```
AI Assistant → MCP Server (Python/FastMCP, stdio) → Unreal Editor (C++ plugin + Python, TCP localhost:12029)
```

## Repository Structure

```
Source/UnrealMCPython/         # C++ Unreal plugin (TCP server, Blueprint helpers)
  Public/                      # Header files
  Private/                     # Implementation files
Content/Python/UnrealMCPython/ # Python action modules executed inside Unreal
mcp-server/                    # MCP server (Python package)
  src/unreal_mcp/
    main.py                    # Entry point
    server.py                  # FastMCP setup, mounts 8 sub-servers
    core.py                    # Socket communication with Unreal (send_unreal_action, etc.)
    tool_routers/              # 8 routers: actor, asset, material, blueprint, behavior_tree, editor, game, util
  validate_tools.py            # CI tool: validates router↔action name mappings
  pyproject.toml               # Python package config (requires-python >=3.11)
Config/                        # Unreal plugin configuration
Docs/                          # Documentation
.github/workflows/release.yml  # Release CI (version check, tool validation, packaging)
UnrealMCPython.uplugin         # Plugin descriptor (current: v1.3.1)
```

## Key Conventions

### Naming Convention (Critical)

Router functions and plugin action functions follow a strict naming convention enforced by CI:

- Router function `foo_bar` in `mcp-server/src/unreal_mcp/tool_routers/` automatically calls `ue_foo_bar` in `Content/Python/UnrealMCPython/`
- This mapping is derived at runtime via `sys._getframe(1).f_code.co_name` in `core.py:send_unreal_action()`
- Validated by `mcp-server/validate_tools.py` during releases

**When adding a new tool:**
1. Add `async def my_tool(...)` to the appropriate `*_router.py`
2. Add `def ue_my_tool(...)` to the matching `*_actions.py` in `Content/Python/UnrealMCPython/`
3. Run `python mcp-server/validate_tools.py` to verify the mapping

### Router-to-Action Module Mapping

Each router file defines a `*_ACTIONS_MODULE` constant pointing to its corresponding plugin module:
- `actor_router.py` → `actor_actions.py`
- `asset_router.py` → `asset_actions.py`
- `material_router.py` → `material_actions.py`
- `blueprint_router.py` → `blueprint_actions.py`
- `behavior_tree_router.py` → `behavior_tree_actions.py`
- `editor_router.py` → `editor_actions.py`
- `game_router.py` → `game_actions.py`
- `util_router.py` → `util_actions.py`

### Tool Registration Pattern

```python
@router.tool(
    name="tool_name",
    description="...",
    tags={"category", "tags"}
)
async def tool_name(param: Annotated[type, Field(description="...")]) -> dict:
    params = {"param": param}
    return await send_unreal_action(MODULE_CONSTANT, params)
```

### Action Function Pattern (Plugin Side)

```python
def ue_tool_name(params):
    # Extract and validate params
    # Perform Unreal operations via unreal module
    # Return JSON string: json.dumps({"success": True/False, "message": "..."})
```

### Copyright Header

All source files must include:
```python
# Copyright (c) 2025 GenOrca. All Rights Reserved.
```

## Version Management

Three files must stay in sync (enforced by CI):
- `UnrealMCPython.uplugin` → `VersionName`
- `mcp-server/pyproject.toml` → `version`
- Git tag → `v<version>`

## Development Commands

```bash
# Validate tool name mappings (run from repo root)
python mcp-server/validate_tools.py

# Install MCP server for development
cd mcp-server && pip install -e ".[dev]"

# Run MCP server locally
unrealmcp
# or: python -m unreal_mcp.main

# Run tests
cd mcp-server && pytest
```

## Communication Protocol

- MCP server ↔ Unreal: TCP socket on `127.0.0.1:12029`
- Commands are JSON with `type` field: `python_call`, `python`, or `livecoding_compile`
- Standard timeout: 30s for actions, 180s for LiveCoding compilation
- Responses follow `{"success": bool, "message": str, ...}` format

## Error Handling

- `ToolInputError`: Client-side input validation errors
- `UnrealExecutionError`: Errors from socket communication or Unreal execution
- All action functions return JSON with `success` and `message` fields

## Platform

- Unreal Engine 5.6+ (plugin descriptor targets 5.7.0)
- Win64 only for the C++ plugin module
- Python 3.11+ for the MCP server
- Primary dependency: `fastmcp` (v3+; uses `instructions=` not `description=` in `FastMCP()`)
- License: Apache-2.0
