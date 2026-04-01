# Copyright (c) 2025 GenOrca. All Rights Reserved.

import socket
import json
import sys


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ToolInputError(Exception):
    pass


class UnrealExecutionError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


# ---------------------------------------------------------------------------
# Low-level socket transport
# ---------------------------------------------------------------------------

HOST = '127.0.0.1'
PORT = 12029


def _send_command(command: dict, timeout: int = 30) -> dict:
    """
    Sends a JSON command to the Unreal TCP server and returns the parsed response.

    Raises:
        UnrealExecutionError: on any communication or response-parsing failure.
    """
    response_str = ""
    try:
        message_bytes = json.dumps(command, ensure_ascii=False).encode('utf-8')

        with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
            sock.sendall(message_bytes)
            chunks = []
            while True:
                chunk = sock.recv(16384)
                if not chunk:
                    break
                chunks.append(chunk)

            if not chunks:
                raise UnrealExecutionError(
                    "No response received from Unreal.",
                    details={"host": HOST, "port": PORT},
                )

            response_str = b''.join(chunks).decode('utf-8')
            return json.loads(response_str)

    except socket.timeout:
        raise UnrealExecutionError(
            f"Socket timeout ({HOST}:{PORT}): No response within {timeout}s.",
            details={"host": HOST, "port": PORT},
        )
    except ConnectionRefusedError:
        raise UnrealExecutionError(
            f"Connection refused ({HOST}:{PORT}). Ensure Unreal MCPython TCP server is active.",
            details={"host": HOST, "port": PORT},
        )
    except json.JSONDecodeError as exc:
        raise UnrealExecutionError(
            f"Failed to decode JSON response: {exc}. Raw: '{response_str}'",
            details={"host": HOST, "port": PORT, "raw_response": response_str},
        )
    except UnrealExecutionError:
        raise
    except Exception as exc:
        raise UnrealExecutionError(
            f"Unexpected error ({HOST}:{PORT}): {type(exc).__name__} - {exc}",
            details={"host": HOST, "port": PORT, "error_type": type(exc).__name__},
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def send_unreal_action(action_module: str, params: dict) -> dict:
    """
    Convention-based wrapper: auto-derives the action name from the caller.
    Caller ``foo_bar`` → Unreal function ``ue_foo_bar``.
    """
    caller_name = sys._getframe(1).f_code.co_name
    action_name = f"ue_{caller_name}"
    try:
        response = _send_command({
            "type": "python_call",
            "module": action_module,
            "function": action_name,
            "args": params,
        })
        if isinstance(response, dict) and response.get("success") is False:
            raise UnrealExecutionError(
                response.get("message", "Unknown error from Unreal action."),
                details=response.get("details"),
            )
        return response
    except UnrealExecutionError as exc:
        return {"success": False, "message": str(exc), "details": exc.details}
    except Exception as exc:
        return {"success": False, "message": f"An unexpected error occurred: {exc}"}


async def send_python_exec(code: str) -> dict:
    """Sends raw Python code to Unreal for execution. Captures print() output."""
    return _send_command({"type": "python", "code": code}, timeout=30)


async def send_livecoding_compile() -> dict:
    """Triggers LiveCoding C++ hot-reload. May take up to 3 minutes."""
    response = _send_command({"type": "livecoding_compile"}, timeout=180)
    if isinstance(response, dict) and response.get("success") is False:
        raise UnrealExecutionError(
            response.get("message", "LiveCoding compile failed."),
            details=response,
        )
    return response
