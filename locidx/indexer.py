"""Incremental file indexing.

The indexer walks a tree, respecting gitignore-style rules, and syncs a
per-root SQLite database:

* files that disappeared are removed
* files whose mtime changed are re-read and their text rehashed
* text content is stored once per unique hash

The result is a queryable snapshot of a codebase that can be searched
without ever touching the filesystem again.
"""

import hashlib
import os
import time

from . import ignore as ignore_mod
from .db import Database, path_prefix_pattern

_IGNORE_FILES = (".gitignore", ".locidxignore")
_DB_FILES = (".locidx.sqlite", ".locidx.sqlite-wal", ".locidx.sqlite-shm")
_BINARY_THRESHOLD = 65536  # bytes probed before assuming text


def _looks_binary(data, sample=8192):
    """Return True when a byte sample is likely binary.

    NUL bytes and a high ratio of control characters are both treated as
    binary markers. Files that cannot be decoded are always skipped.
    """
    chunk = data[:sample]
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    control = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
    return control / len(chunk) > 0.30


def _hash_text(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


class Indexer:
    """Incremental indexer for a single root directory."""

    def __init__(self, root, db, extra_ignores=None, no_ignore=False, size_limit=2 * 1024 * 1024):
        self.root = os.path.abspath(root)
        self.db = db
        self.extra_ignores = extra_ignores or []
        self.no_ignore = no_ignore
        self.size_limit = size_limit

    # -- ignore handling -------------------------------------------------

    def _matcher(self):
        matcher = ignore_mod.IgnoreMatcher()
        if self.no_ignore:
            return matcher
        root_ignore = os.path.join(self.root, ".gitignore")
        if os.path.isfile(root_ignore):
            with open(root_ignore, "r", encoding="utf-8", errors="replace") as fh:
                matcher.add("", ignore_mod.parse(fh.read()))
        for pattern in self.extra_ignores:
            matcher.add("", ignore_mod.parse(pattern + "\n"))
        return matcher

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _rel(root, path):
        return os.path.relpath(path, root)

    def _load_ignore_file(self, matcher, root, path):
        for name in _IGNORE_FILES:
            full = os.path.join(path, name)
            if not os.path.isfile(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    rules = ignore_mod.parse(fh.read())
            except OSError:
                continue
            if rules:
                matcher.add(self._rel(root, path), rules)

    @staticmethod
    def _read_text(full_path):
        with open(full_path, "rb") as fh:
            data = fh.read()
        if _looks_binary(data):
            return None
        return data.decode("utf-8", "replace")

    # -- main loop -------------------------------------------------------

    def run(self):
        """Synchronize the index with the current tree.

        Returns a dict with ``added``, ``removed``, ``updated``, ``skipped``,
        and ``total`` counters.
        """
        matcher = self._matcher()
        seen = {}
        stats = {"added": 0, "removed": 0, "updated": 0, "skipped": 0, "total": 0}

        # Load current index contents for this root.
        rows = self.db.query(
            "SELECT path, size, mtime FROM files WHERE path LIKE ? ESCAPE '\\'",
            (path_prefix_pattern(self.root),),
        )
        old = {r["path"]: (r["size"], r["mtime"]) for r in rows}

        # Walk the tree.
        stack = [self.root]
        while stack:
            path = stack.pop()
            rel = self._rel(self.root, path)
            if os.path.isdir(path):
                if rel != "." and matcher.ignored(rel, is_dir=True):
                    continue
                self._load_ignore_file(matcher, self.root, path)
                try:
                    entries = os.listdir(path)
                except OSError:
                    continue
                for name in entries:
                    child = os.path.join(path, name)
                    if os.path.islink(child):
                        continue
                    stack.append(child)
                continue

            # Regular file.
            if rel != "." and matcher.ignored(rel, is_dir=False):
                stats["skipped"] += 1
                continue
            base = os.path.basename(path)
            if base in _IGNORE_FILES or base in _DB_FILES:
                stats["skipped"] += 1
                continue
            try:
                st = os.stat(path)
            except OSError:
                stats["skipped"] += 1
                continue
            if st.st_size > self.size_limit:
                stats["skipped"] += 1
                continue
            stats["total"] += 1
            seen[path] = st

        # Remove files that no longer exist.
        current = set(seen)
        for path in list(old):
            if path not in current:
                self.db.execute("DELETE FROM content WHERE path = ?", (path,))
                self.db.execute("DELETE FROM files WHERE path = ?", (path,))
                stats["removed"] += 1

        # Upsert changed or new files.
        new_rows = []
        content_rows = []
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for path, st in sorted(seen.items()):
            prev = old.get(path)
            if prev and prev[0] == st.st_size and abs(prev[1] - st.st_mtime) < 1e-6:
                # Unchanged: keep the stored text so the hash is stable.
                continue
            text = self._read_text(path)
            if text is None:
                continue
            digest = _hash_text(text)
            # Read again with fresh stat to avoid a race between the walk
            # and the read; if it changed, the next run picks it up.
            try:
                st2 = os.stat(path)
            except OSError:
                continue
            new_rows.append((path, st2.st_size, st2.st_mtime, digest, now))
            content_rows.append((path, text))
            if prev:
                stats["updated"] += 1
            else:
                stats["added"] += 1

        self.db.executemany(
            "INSERT INTO files(path, size, mtime, text_hash, indexed_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET "
            "size=excluded.size, mtime=excluded.mtime, "
            "text_hash=excluded.text_hash, indexed_at=excluded.indexed_at",
            new_rows,
        )
        self.db.executemany(
            "INSERT INTO content(path, text) VALUES (?, ?) "
            "ON CONFLICT(path) DO UPDATE SET text=excluded.text",
            content_rows,
        )
        self.db.commit()
        return stats


def index_root(root, db=None, extra_ignores=None, no_ignore=False, size_limit=2 * 1024 * 1024):
    """Convenience wrapper: open a database (or reuse one) and index a root."""
    own = db is None
    if own:
        db = Database()
    try:
        db.execute(
            "INSERT OR IGNORE INTO roots(path, created_at) VALUES (?, ?)",
            (os.path.abspath(root), time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        stats = Indexer(root, db, extra_ignores=extra_ignores, no_ignore=no_ignore, size_limit=size_limit).run()
        return db, stats
    finally:
        if own:
            db.close()
