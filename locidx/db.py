"""Tiny read-only SQLite wrapper with zero dependencies.

Everything in locidx that needs persistence uses this single abstraction:
index metadata, the search index, and cached stats. No row factories, no
magic — just plain dict rows and ``with db:`` transactions.
"""

import os
import sqlite3
import tempfile


def default_db_path():
    """Return the default database location for the current user.

    Uses ``XDG_DATA_HOME`` when set, otherwise ``~/.local/share``. An
    environment variable can force an override, which is handy for tests.
    """
    override = os.environ.get("LOCIDX_DB")
    if override:
        return os.path.expanduser(override)
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        base = os.path.expanduser(data_home)
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "locidx", "locidx.sqlite")


def temp_db_path():
    """Return a throwaway database path (used by tests)."""
    fd, path = tempfile.mkstemp(prefix="locidx-test-", suffix=".sqlite")
    os.close(fd)
    os.unlink(path)
    return path


def path_prefix_pattern(path):
    """Return an escaped SQLite LIKE pattern for files below ``path``."""
    root = os.path.abspath(path).rstrip(os.sep)
    escaped = root.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    separator = os.sep.replace("\\", "\\\\")
    return escaped + separator + "%"


SCHEMA = """
CREATE TABLE IF NOT EXISTS roots (
    path TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    text_hash TEXT,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content (
    path TEXT PRIMARY KEY REFERENCES files(path) ON DELETE CASCADE,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stats_cache (
    root TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);",
    "CREATE INDEX IF NOT EXISTS idx_content_path ON content(path);",
)


class Database:
    """Minimal sqlite3 wrapper exposing ``query`` and ``execute``.

    ``query`` returns a list of :class:`sqlite3.Row`, which support both
    index and key access — convenient and dependency-free.
    """

    def __init__(self, path=None):
        self.path = path or default_db_path()
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.executescript(SCHEMA)
        for statement in _INDEXES:
            self._conn.execute(statement)
        self._conn.commit()

    def query(self, sql, params=()):
        return self._conn.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        self._conn.execute(sql, params)

    def executemany(self, sql, rows):
        self._conn.executemany(sql, rows)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def load(db, sql, params=()):
    """Run a SELECT and return plain dicts."""
    rows = db.query(sql, params)
    return [dict(r) for r in rows]
