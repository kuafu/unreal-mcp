# Unreal MCP - Architecture & Working Principles

## 1. Project Overview

Unreal MCP connects AI assistants (Claude, Cursor, VS Code Copilot) to the Unreal Engine 5.6+ editor through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It provides **62 tools** across 8 categories, enabling natural language control of editor operations — from spawning actors to building entire Blueprint graphs.

## 2. System Architecture

The system follows a **three-layer architecture**, where each layer communicates through a well-defined protocol boundary:

```
┌─────────────────────┐
│   AI Assistant       │  Claude / Cursor / VS Code Copilot
│   (MCP Client)       │
└────────┬────────────┘
         │  MCP Protocol (JSON-RPC over stdio)
         │
┌────────▼────────────┐
│   MCP Server         │  Python process (fastmcp)
│   (mcp-server/)      │  Runs as a subprocess of the AI client
└────────┬────────────┘
         │  TCP Socket (JSON over localhost:12029)
         │
┌────────▼────────────┐
│   Unreal Editor      │  C++ plugin + Python scripts
│   (UnrealMCPython)   │  Runs inside the UE editor process
└─────────────────────┘
```

### Layer 1: AI Assistant (MCP Client)

The AI assistant (e.g. Claude Desktop, Cursor) acts as an MCP client. It discovers the tools the MCP server exposes, then invokes them based on the user's natural language requests. The assistant sends tool calls over **stdio** using the MCP JSON-RPC protocol.

### Layer 2: MCP Server (Python)

A standalone Python process built on [FastMCP](https://github.com/jlowin/fastmcp). It:

- Exposes 62 tools to the AI assistant via the MCP protocol
- Translates tool calls into TCP commands for Unreal
- Runs as a subprocess spawned by the AI client (transport: `stdio`)

### Layer 3: Unreal Editor Plugin (C++ + Python)

An editor-only plugin (`UnrealMCPython`) that:

- Listens on a TCP socket (`127.0.0.1:12029`) for commands
- Dispatches commands to Python action functions running inside the editor
- Provides a C++ helper library (`UMCPythonHelper`) for operations that cannot be done in Python alone (Blueprint graph manipulation, Behavior Tree building, etc.)

## 3. Detailed Data Flow

A complete request-response cycle goes through 7 steps:

```
User: "Spawn a cube at (0, 0, 100)"

  1. AI Assistant → MCP Server
     JSON-RPC call: tool="actor__spawn_from_object",
     args={asset_path="/Engine/BasicShapes/Cube.Cube", location=[0,0,100]}

  2. MCP Server: Router function `spawn_from_object()` in actor_router.py
     Calls `send_unreal_action("UnrealMCPython.actor_actions", params)`

  3. core.py: Auto-derives action name `ue_spawn_from_object` from caller
     Builds JSON command:
     {
       "type": "python_call",
       "module": "UnrealMCPython.actor_actions",
       "function": "ue_spawn_from_object",
       "args": {"asset_path": "...", "location": [0, 0, 100]}
     }

  4. core.py → TCP → C++ TCP Server (MCPythonTcpServer.cpp)
     The C++ server receives the JSON on a background thread,
     then dispatches to the Game Thread for processing.

  5. C++ Server: Generates a Python one-liner and executes it:
     from UnrealMCPython import mcp_unreal_actions;
     print(mcp_unreal_actions.execute_action(
       'UnrealMCPython.actor_actions', 'ue_spawn_from_object',
       {'asset_path': '...', 'location': [0, 0, 100]}
     ));

  6. Python (inside UE): mcp_unreal_actions.execute_action()
     - Dynamically imports & reloads `UnrealMCPython.actor_actions`
     - Calls `ue_spawn_from_object(asset_path=..., location=...)`
     - The function uses the `unreal` module to spawn the actor
     - Returns JSON string: {"success": true, "actor_label": "Cube"}

  7. Response flows back:
     Python stdout → C++ captures via FPythonLogCapture
     → TCP response → core.py parses JSON → Router returns to AI
```

## 4. Module Details

### 4.1 MCP Server (`mcp-server/src/unreal_mcp/`)

```
main.py              Entry point; called via `unrealmcp` CLI command
server.py            Creates main FastMCP instance, mounts 8 sub-servers
core.py              TCP transport layer:
                       _send_command()        — low-level socket send/receive
                       send_unreal_action()   — convention-based tool dispatch
                       send_python_exec()     — raw Python code execution
                       send_livecoding_compile() — C++ hot-reload trigger
tool_routers/
  actor_router.py       17 tools — spawn, transform, select, delete, raycast, properties
  asset_router.py        2 tools — find assets, mesh details
  material_router.py    11 tools — expressions, material instance parameters
  blueprint_router.py   10 tools — add/connect/remove nodes, build graphs, compile
  behavior_tree_router.py 12 tools — BT/Blackboard CRUD, build tree from JSON
  editor_router.py       6 tools — asset selection, material/mesh replacement
  game_router.py         3 tools — GameMode, Enhanced Input actions/mappings
  util_router.py         1 tool  — output log, execute_python, livecoding_compile
```

**Key Design: Convention-based Dispatch**

Every router tool function auto-maps to its Unreal counterpart:

```
Router function:  spawn_from_object()
                       ↓ sys._getframe(1).f_code.co_name
Action function:  ue_spawn_from_object()
```

This is enforced by CI via `validate_tools.py`.

### 4.2 Unreal Plugin — C++ Layer (`Source/UnrealMCPython/`)

| File | Responsibility |
|------|----------------|
| `UnrealMCPython.cpp` | Module startup/shutdown; creates TCP server on port 12029 |
| `MCPythonTcpServer.cpp` | TCP listener; JSON parsing; command dispatch |
| `MCPythonHelper.cpp` | Complex editor operations exposed as UFUNCTIONs |

**TCP Server Processing Pipeline** (`MCPythonTcpServer.cpp`):

```
HandleIncomingConnection()       ← Background thread: receives raw bytes
  └→ ProcessDataOnGameThread()   ← Game thread: parses JSON, dispatches
       ├─ type="python"          → Execute raw Python code via IPythonScriptPlugin
       ├─ type="python_call"     → Generate execute_action() call, run via Python
       └─ type="livecoding_compile" → Native handler via ILiveCodingModule
```

The `python_call` dispatch is the primary path. It:

1. Extracts `module`, `function`, and `args` from the JSON
2. Converts the `args` JSON object to a Python dict literal string using `ConvertJsonValueToPythonLiteral()`
3. Generates a Python one-liner: `from UnrealMCPython import mcp_unreal_actions; print(mcp_unreal_actions.execute_action(...))`
4. Executes via `IPythonScriptPlugin::ExecPythonCommandEx()`
5. Captures `print()` output via `FPythonLogCapture` (intercepts `LogPython` category)
6. Returns the captured output as a JSON TCP response

**C++ Helper (`UMCPythonHelper`)** provides operations not accessible from Python:

- **Blueprint Graph**: `AddBlueprintNode`, `ConnectBlueprintPins`, `RemoveBlueprintNode`, `BuildBlueprintGraph`, `CompileBlueprint`, `GetBlueprintGraphInfo`, `ListCallableFunctions`, `ListBlueprintVariables`
- **Behavior Tree**: `BuildBehaviorTree`, `GetBehaviorTreeStructure`, `SetBehaviorTreeBlackboard`, `GetBehaviorTreeNodeDetails`, `GetSelectedBTNodes`, `ListBTNodeClasses`

### 4.3 Unreal Plugin — Python Layer (`Content/Python/UnrealMCPython/`)

```
mcp_unreal_actions.py    Core dispatcher: dynamically imports, reloads, and
                         calls target functions. Validates JSON return format.
actor_actions.py         17 ue_* functions for actor manipulation
asset_actions.py          2 ue_* functions for asset queries
material_actions.py      11 ue_* functions for material editing
blueprint_actions.py     10 ue_* functions (delegates to UMCPythonHelper)
behavior_tree_actions.py 12 ue_* functions (delegates to UMCPythonHelper)
editor_actions.py         6 ue_* functions for editor operations
game_actions.py           3 ue_* functions for game settings
util_actions.py           2 ue_* functions for logging/diagnostics
```

**Common Patterns:**

- All `ue_*` functions accept keyword arguments and return `json.dumps(...)` strings
- Write operations are wrapped in `unreal.ScopedEditorTransaction` for undo support
- Modules are reloaded on every call (`importlib.reload`) for live development
- Functions interact with UE via subsystems: `EditorActorSubsystem`, `EditorAssetLibrary`, `MaterialEditingLibrary`, etc.

## 5. Communication Protocol

### MCP Layer (AI ↔ MCP Server)

Standard MCP JSON-RPC over **stdio**. Tools are registered with:
- `name`: Tool identifier (e.g., `actor__spawn_from_object`)
- `description`: Natural language description for the AI
- `tags`: Categorization tags
- Parameter types: Pydantic `Annotated[type, Field(description=...)]`

### TCP Layer (MCP Server ↔ Unreal)

Plain TCP on `127.0.0.1:12029`. Each request is a single JSON message; each response is a single JSON message. Connection is opened and closed per request.

**Request format:**
```json
{"type": "python_call", "module": "...", "function": "...", "args": {...}}
{"type": "python", "code": "..."}
{"type": "livecoding_compile"}
```

**Response format:**
```json
{"success": true, "message": "...", ...}
{"success": false, "message": "error description", "traceback": "..."}
```

**Timeouts:**
- Standard actions: 30 seconds
- LiveCoding compile: 180 seconds (MCP server) / 120 seconds (C++ poller)

## 6. Thread Model

```
MCP Server Process
  └─ Single Python process, async (FastMCP + asyncio)
     └─ Blocking socket calls run in thread pool (FastMCP manages this)

Unreal Editor Process
  ├─ TCP Listener thread (FTcpListener)
  ├─ Background thread (AsyncTask): receives socket data
  └─ Game Thread (AsyncTask): processes commands, runs Python
       └─ IPythonScriptPlugin executes Python on the Game Thread
```

All Unreal Python code and editor operations run on the **Game Thread**. The C++ TCP server receives data on a background thread, then dispatches to the Game Thread via `AsyncTask(ENamedThreads::GameThread, ...)`.

## 7. Tool Categories (62 tools)

| Category | Count | Module | Description |
|----------|-------|--------|-------------|
| Actor | 17 | `actor_router` / `actor_actions` | Spawn, transform, select, delete, duplicate, raycast, properties |
| Behavior Tree | 12 | `behavior_tree_router` / `behavior_tree_actions` | Create/read/build BT and Blackboard assets |
| Material | 11 | `material_router` / `material_actions` | Create expressions, connect nodes, material instance parameters |
| Blueprint | 10 | `blueprint_router` / `blueprint_actions` | Add/connect/remove nodes, build graphs, compile |
| Editor | 6 | `editor_router` / `editor_actions` | Asset selection, material/mesh replacement |
| Game | 3 | `game_router` / `game_actions` | GameMode, Enhanced Input actions/mappings |
| Asset | 2 | `asset_router` / `asset_actions` | Find assets, static mesh details |
| Utility | 1+2 | `util_router` / `util_actions` | Output log + execute_python + livecoding_compile |

## 8. Adding a New Tool

1. **Choose the router** — pick the appropriate `*_router.py` or create a new one.

2. **Add the router function:**
```python
@router.tool(
    name="my_new_tool",
    description="What this tool does.",
    tags={"unreal", "category"},
)
async def my_new_tool(
    param: Annotated[str, Field(description="...")],
) -> dict:
    params = {"param": param}
    return await send_unreal_action(MODULE_CONSTANT, params)
```

3. **Add the action function** in the matching `*_actions.py`:
```python
def ue_my_new_tool(param: str = None) -> str:
    if param is None:
        return json.dumps({"success": False, "message": "Missing 'param'."})
    try:
        # Use the `unreal` module to do work
        with unreal.ScopedEditorTransaction("MCP: My New Tool"):
            # ... editor operations ...
            pass
        return json.dumps({"success": True, "message": "Done."})
    except Exception as e:
        return json.dumps({"success": False, "message": str(e), "traceback": traceback.format_exc()})
```

4. **If new router**, mount it in `server.py`:
```python
from unreal_mcp.tool_routers.my_router import my_mcp
main_mcp.mount("my_category", my_mcp)
```

5. **Validate:**
```bash
python mcp-server/validate_tools.py
```

## 9. Build & Dependencies

### MCP Server (Python)

| Item | Value |
|------|-------|
| Python | >= 3.11 |
| Primary dependency | `fastmcp` (v3+) |
| Dev dependency | `pytest` |
| Package manager | `uv` (lock file committed) |
| Entry point | `unrealmcp` CLI or `python -m unreal_mcp.main` |

### Unreal Plugin (C++)

| Item | Value |
|------|-------|
| Engine | Unreal Engine 5.6+ (descriptor targets 5.7.0) |
| Platform | Win64 only |
| Module type | Editor (LoadingPhase: PostEngineInit) |
| Required plugin | PythonScriptPlugin |
| Public deps | Core, CoreUObject, Engine, InputCore, Sockets, Networking, Json, JsonUtilities, PythonScriptPlugin |
| Private deps | UnrealEd, EditorSubsystem, AssetTools, BlueprintGraph, Kismet, AIModule, GameplayTasks, AIGraph, BehaviorTreeEditor, LiveCoding |

## 10. CI/CD

The release workflow (`.github/workflows/release.yml`) runs on version tag pushes (`v*`):

1. **Version consistency check** — ensures `UnrealMCPython.uplugin`, `mcp-server/pyproject.toml`, and the git tag all match.
2. **Tool validation** — runs `validate_tools.py` to confirm all 62 router↔action mappings are correct.
3. **Packaging** — creates a zip with Source, Content, Config, Resources, Docs, mcp-server, and root files.
4. **Release** — uploads the zip to GitHub Releases.

## 11. Key Design Decisions

- **Convention over configuration**: The `foo_bar` → `ue_foo_bar` naming convention eliminates boilerplate routing code and is enforced by CI.
- **Module hot-reload**: `importlib.reload()` on every call enables live Python development without restarting the editor.
- **Game Thread execution**: All UE API calls run on the Game Thread via `AsyncTask`, ensuring thread safety.
- **JSON-in / JSON-out**: Every layer communicates via JSON, making the protocol debuggable and language-agnostic.
- **Undo support**: Write operations use `ScopedEditorTransaction`, integrating naturally with the editor's undo system.
- **C++/Python split**: Complex graph operations (Blueprint, Behavior Tree) are implemented in C++ for access to internal APIs, exposed to Python via UFUNCTIONs.
