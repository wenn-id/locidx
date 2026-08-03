"""Agent-friendly tool wrappers for the MCP server.

Each function is a pure Python function that takes plain arguments and
returns a JSON-serializable dict. The JSON-RPC layer in ``server.py``
converts between MCP call payloads and these signatures.
"""

import os

from .db import Database
from .indexer import Indexer
from .search import search as _search
from .stats import aggregate as _aggregate


def _open_db(root=None):
    """Open the database associated with a root (or the global one)."""
    if root:
        return Database(os.path.join(os.path.abspath(root), ".locidx.sqlite"))
    return Database()


def _root_for(root):
    if root:
        return os.path.abspath(root)
    return None


def search_tool(query, root=None, max_results=100):
    """Search indexed files for a literal substring."""
    db = _open_db(root)
    try:
        results = _search(db, query, root=_root_for(root), max_results=max_results)
        return {"results": results, "count": len(results)}
    finally:
        db.close()


def index_tool(root, extra_ignores=None, no_ignore=False):
    """Index (or re-index) a directory and return counters."""
    root = os.path.abspath(root)
    db = _open_db(root)
    try:
        stats = Indexer(
            root,
            db,
            extra_ignores=extra_ignores or [],
            no_ignore=no_ignore,
        ).run()
        return {"root": root, "stats": stats}
    finally:
        db.close()


def stats_tool(root=None):
    """Return per-language statistics for an indexed tree."""
    db = _open_db(root)
    try:
        rows, totals = _aggregate(db, root=_root_for(root))
        return {"root": _root_for(root) or "all", "languages": rows, "totals": totals}
    finally:
        db.close()


def roots_tool():
    """List every indexed root in the global database."""
    db = Database()
    try:
        rows = db.query("SELECT path FROM roots ORDER BY path")
        return {"roots": [r["path"] for r in rows]}
    finally:
        db.close()


TOOLS = {
    "search": {
        "name": "search",
        "description": "Search previously indexed files for a literal substring. Returns matching lines with file path and line number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Literal substring to search for"},
                "root": {"type": "string", "description": "Optional project root to search within"},
                "max_results": {"type": "integer", "description": "Maximum results (default 100)"},
            },
            "required": ["query"],
        },
    },
    "index": {
        "name": "index",
        "description": "Index a directory so it can be searched later. Incremental: only changed files are re-read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Directory to index"},
                "extra_ignores": {"type": "array", "items": {"type": "string"}, "description": "Extra ignore globs"},
                "no_ignore": {"type": "boolean", "description": "Disable .gitignore/.locidxignore"},
            },
            "required": ["root"],
        },
    },
    "stats": {
        "name": "stats",
        "description": "Per-language file and line statistics for an indexed tree (or all trees).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Optional project root"},
            },
        },
    },
    "roots": {
        "name": "roots",
        "description": "List every indexed root in the global database.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def dispatch(name, arguments):
    """Dispatch an MCP tool call to the matching pure function."""
    if name == "search":
        return search_tool(**arguments)
    if name == "index":
        return index_tool(**arguments)
    if name == "stats":
        return stats_tool(**arguments)
    if name == "roots":
        return roots_tool()
    raise KeyError("unknown tool: %s" % name)
