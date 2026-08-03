"""MCP server for locidx.

Exposes the index as tools an AI agent can call. ``mcp-server-locidx`` is a
thin launcher that reads the schema from ``index.py`` and runs the stdio
transport.

The implementation follows the MCP spec directly (JSON-RPC 2.0 over stdio)
with zero external dependencies:

* ``initialize`` with a fixed protocol version and capabilities
* ``tools/list`` returning the tool schema
* ``tools/call`` dispatching to the underlying functions

Agent-friendly wrappers live in ``tools.py`` (pure functions returning
structured dicts), and the JSON-RPC dispatch in ``server.py`` keeps them
usable from any MCP client.
"""

from .server import main  # noqa: F401
