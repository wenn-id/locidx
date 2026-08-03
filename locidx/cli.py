"""Command-line interface for locidx.

Every command is a small function that returns a status code, so the whole
CLI stays testable without subprocesses.
"""

import argparse
import os
import sys

from . import __version__
from .db import Database, load
from .indexer import index_root
from .search import search
from .stats import aggregate, to_json


def _print(*args):
    print(*args)


def _err(msg):
    print(msg, file=sys.stderr)


def _db_path(global_db, path):
    if global_db:
        return None
    return os.path.join(path, ".locidx.sqlite")


def _open_db(global_db, path):
    """Open a database, preferring a per-root DB when requested."""
    if global_db:
        return Database()
    return Database(os.path.join(path, ".locidx.sqlite"))


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_index(args):
    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        _err("error: not a directory: %s" % args.path)
        return 2
    db = _open_db(args.global_db, root)
    try:
        if not args.global_db:
            db.execute(
                "INSERT OR IGNORE INTO roots(path, created_at) VALUES (?, ?)",
                (root, ""),
            )
        _db, stats = index_root(root, db=db, extra_ignores=args.ignore, no_ignore=args.no_ignore, size_limit=args.size_limit * 1024 * 1024)
        db = _db
        print("Indexed %(total)s files (+%(added)s, ~%(updated)s, -%(removed)s, skipped %(skipped)s)" % stats)
        if args.stats:
            rows, totals = aggregate(db, root=root)
            print("Totals: %(files)s files, %(lines)s lines" % totals)
    finally:
        db.close()
    return 0


def cmd_search(args):
    db = _open_db(args.global_db, args.path)
    try:
        results = search(
            db,
            args.pattern,
            root=args.path if not args.global_db else None,
            max_results=args.max,
            case=args.case,
        )
    finally:
        db.close()
    for r in results:
        print("%s:%d: %s" % (r["path"], r["lineno"], r["text"]))
    return 0


def cmd_stats(args):
    db = _open_db(args.global_db, args.path)
    try:
        rows, totals = aggregate(db, root=args.path if not args.global_db else None)
    finally:
        db.close()
    if args.json:
        print(to_json(rows, totals))
        return 0
    if not rows:
        print("No indexed files.")
        return 0
    w = max(len(r["language"]) for r in rows)
    for r in rows:
        print("%-*s  %8d files  %10d lines" % (w, r["language"], r["files"], r["lines"]))
    print("-" * (w + 34))
    print("%-*s  %8d files  %10d lines" % (w, "TOTAL", totals["files"], totals["lines"]))
    return 0


def cmd_roots(args):
    db = Database()
    try:
        for row in load(db, "SELECT path FROM roots ORDER BY path"):
            print(row["path"])
    finally:
        db.close()
    return 0


def cmd_clear(args):
    db = Database()
    try:
        before = db.query("SELECT COUNT(*) AS n FROM files")[0]["n"]
        db.execute("DELETE FROM content")
        db.execute("DELETE FROM files")
        db.execute("DELETE FROM roots")
        db.commit()
        print("Cleared %d indexed files." % before)
    finally:
        db.close()
    return 0


def cmd_find(args):
    root = os.path.abspath(args.path)
    db = _open_db(args.global_db, root)
    try:
        results = search(db, args.pattern, root=root, max_results=args.max, case=args.case)
    finally:
        db.close()
    for r in results:
        print("%s:%d: %s" % (r["path"], r["lineno"], r["text"]))
    return 0


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="locidx",
        description="Local-first code indexer and search. Zero-dependency CLI, TUI, and MCP server.",
    )
    parser.add_argument("--version", action="version", version="locidx %s" % __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="build or update the index for a directory")
    p_index.add_argument("path", nargs="?", default=".", help="directory to index (default: .)")
    p_index.add_argument("--global", dest="global_db", action="store_true", help="use the global database instead of a per-project one")
    p_index.add_argument("--stats", action="store_true", help="print language stats after indexing")
    p_index.add_argument("--no-ignore", action="store_true", help="ignore .gitignore and .locidxignore")
    p_index.add_argument("--ignore", action="append", default=[], help="extra ignore glob (repeatable)")
    p_index.add_argument("--size-limit", type=int, default=2, help="skip files larger than N MiB (default: 2)")
    p_index.set_defaults(func=cmd_index)

    p_search = sub.add_parser("search", help="search indexed files (global database)")
    p_search.add_argument("pattern", help="literal substring to find")
    p_search.add_argument("path", nargs="?", default=None, help="optional directory to search in")
    p_search.add_argument("--global", dest="global_db", action="store_true", help="use the global database")
    p_search.add_argument("--max", type=int, default=200, help="maximum results (default: 200)")
    p_search.add_argument("--case", action="store_true", help="case-sensitive search")
    p_search.set_defaults(func=cmd_search)

    p_find = sub.add_parser("find", help="search inside a project's own index")
    p_find.add_argument("pattern", help="literal substring to find")
    p_find.add_argument("path", nargs="?", default=".", help="project directory (default: .)")
    p_find.add_argument("--global", dest="global_db", action="store_true", help="use the global database instead")
    p_find.add_argument("--max", type=int, default=200, help="maximum results (default: 200)")
    p_find.add_argument("--case", action="store_true", help="case-sensitive search")
    p_find.set_defaults(func=cmd_find)

    p_stats = sub.add_parser("stats", help="show language statistics")
    p_stats.add_argument("path", nargs="?", default=".", help="directory to analyze (default: .)")
    p_stats.add_argument("--global", dest="global_db", action="store_true", help="use the global database")
    p_stats.add_argument("--json", action="store_true", help="output JSON")
    p_stats.set_defaults(func=cmd_stats)

    p_roots = sub.add_parser("roots", help="list indexed roots in the global database")
    p_roots.set_defaults(func=cmd_roots)

    p_clear = sub.add_parser("clear", help="wipe the global database")
    p_clear.set_defaults(func=cmd_clear)

    p_tui = sub.add_parser("tui", help="launch the interactive terminal UI")
    p_tui.add_argument("path", nargs="?", default=".", help="project directory (default: .)")
    p_tui.add_argument("--global", dest="global_db", action="store_true", help="use the global database instead")
    p_tui.set_defaults(func=cmd_tui)

    p_mcp = sub.add_parser("mcp", help="run the MCP server over stdio")
    p_mcp.set_defaults(func=cmd_mcp)

    return parser


def cmd_tui(args):
    from .tui import run

    path = os.path.abspath(args.path)
    if args.global_db:
        return run(db=Database(), root=None)
    return run(db=Database(os.path.join(path, ".locidx.sqlite")), root=path)


def cmd_mcp(args):
    from .server import main as mcp_main

    return mcp_main()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
