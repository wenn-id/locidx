import os
import unittest

from locidx.db import Database, default_db_path, descendant_path_filter, load, temp_db_path
from tests.helpers import LocIdxTestCase


class DatabaseTest(LocIdxTestCase):
    def test_default_path_uses_xdg(self):
        os.environ["XDG_DATA_HOME"] = "/tmp/xdg"
        self.addCleanup(os.environ.pop, "XDG_DATA_HOME")
        self.assertEqual(default_db_path(), "/tmp/xdg/locidx/locidx.sqlite")

    def test_override_env(self):
        os.environ["LOCIDX_DB"] = "/tmp/custom.sqlite"
        self.addCleanup(os.environ.pop, "LOCIDX_DB")
        self.assertEqual(default_db_path(), "/tmp/custom.sqlite")

    def test_creates_schema(self):
        db = self.db()
        tables = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"roots", "files", "content", "stats_cache"} <= tables)
        db.close()

    def test_load_returns_dicts(self):
        db = self.db()
        db.execute("INSERT INTO roots(path, created_at) VALUES (?, ?)", ("/x", "now"))
        db.commit()
        rows = load(db, "SELECT * FROM roots")
        self.assertEqual(rows, [{"path": "/x", "created_at": "now"}])
        db.close()

    def test_descendant_path_filter_is_exact_and_case_sensitive(self):
        root = os.path.abspath(self.tmp(r"100%_ready\\folder"))
        filter_sql, params = descendant_path_filter(root, "path")
        db = self.db()
        self.addCleanup(db.close)
        paths = [
            root + os.sep + "inside.py",
            root + "-app" + os.sep + "outside.py",
            root.upper() + os.sep + "case.py",
        ]
        for path in paths:
            db.execute(
                "INSERT INTO files(path, size, mtime, text_hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                (path, 1, 1, "hash", "now"),
            )
        db.commit()

        matched = db.query(
            "SELECT path FROM files WHERE " + filter_sql + " ORDER BY path",
            params,
        )
        self.assertEqual([row["path"] for row in matched], [paths[0]])


if __name__ == "__main__":
    unittest.main()
