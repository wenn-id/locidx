"""Literal substring search across indexed files.

locidx deliberately avoids tokenization and stemming. Querying is a plain
substring match over the indexed text, so results are predictable, and the
text hash doubles as a change detector for callers that want to diff or
cache.

Searches run against a single root, an explicit list of paths, or the
entire index.
"""

import os

from .db import path_prefix_pattern


def _limit_quotes(pattern):
    return pattern.replace('"', '\\"')


def search(db, pattern, root=None, paths=None, max_results=200, case=False):
    """Return matching lines as dicts:

    ``path``, ``lineno`` (1-based), ``text`` (raw line), ``root``.
    """
    if not pattern:
        return []

    case_sensitive = case
    params = []
    clauses = []

    if root is not None:
        clauses.append("f.path LIKE ? ESCAPE '\\'")
        params.append(path_prefix_pattern(root))

    if paths:
        placeholders = ", ".join("?" for _ in paths)
        abs_paths = [os.path.abspath(p) for p in paths]
        clauses.append("f.path IN (%s)" % placeholders)
        params.extend(abs_paths)

    where = " AND ".join(clauses) if clauses else "1=1"
    sql = (
        "SELECT f.path, c.text FROM files f "
        "JOIN content c ON c.path = f.path "
        "WHERE %s ORDER BY f.path" % where
    )
    rows = db.query(sql, params)

    results = []
    for row in rows:
        path, text = row["path"], row["text"]
        if not text:
            continue
        if case_sensitive:
            start = 0
            while True:
                idx = text.find(pattern, start)
                if idx < 0:
                    break
                lineno = text.count("\n", 0, idx) + 1
                start = idx + 1
                if len(results) >= max_results:
                    return results
                results.append(_line_at(text, idx, path, lineno))
        else:
            low = text.lower()
            pat = pattern.lower()
            start = 0
            while True:
                idx = low.find(pat, start)
                if idx < 0:
                    break
                lineno = text.count("\n", 0, idx) + 1
                start = idx + 1
                if len(results) >= max_results:
                    return results
                results.append(_line_at(text, idx, path, lineno))
    return results


def _line_at(text, idx, path, lineno):
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    return {
        "path": path,
        "lineno": lineno,
        "text": line,
        "root": os.path.dirname(path),
    }
