"""Minimal JSON-RPC 2.0 server over stdio implementing the MCP subset.

Implements just enough of the MCP protocol for a client to discover and
call the locidx tools, with zero dependencies:

* ``initialize`` — capability negotiation
* ``notifications/initialized`` — no-op
* ``tools/list`` — return the tool schemas
* ``tools/call`` — dispatch and stream the result

Every request receives exactly one ``{jsonrpc, id, result}`` response; the
only time a request gets ``null`` back is a notification, which has no id.
"""

import json
import sys

from .tools import TOOLS, dispatch

PROTOCOL_VERSION = "2024-11-05"
_IMPLEMENTATION = {"name": "locidx", "version": "0.1.0"}


def _rpc_error(code, message, req_id=None):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _handle(message):
    """Return the response for a single parsed message, or None."""
    if not isinstance(message, dict):
        return _rpc_error(-32600, "invalid request")
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        client = params.get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": client or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": _IMPLEMENTATION,
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": list(TOOLS.values())},
        }

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = dispatch(name, arguments)
        except KeyError as exc:
            return _rpc_error(-32602, str(exc), msg_id)
        except TypeError as exc:
            return _rpc_error(-32602, "invalid arguments: %s" % exc, msg_id)
        except Exception as exc:  # surface tool failures without killing the stream
            return _rpc_error(-32000, "tool failed: %s" % exc, msg_id)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2, ensure_ascii=False),
                    }
                ],
                "isError": False,
            },
        }

    return _rpc_error(-32601, "method not found: %s" % method, msg_id)


def _read_message():
    """Read one newline-delimited JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return _read_message()
    try:
        return json.loads(line)
    except ValueError:
        return _rpc_error(-32700, "parse error")


def main():
    while True:
        message = _read_message()
        if message is None:
            break
        response = _handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0
