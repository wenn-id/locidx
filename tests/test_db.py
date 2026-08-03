import os
import unittest

from locidx.db import Database, default_db_path, temp_db_path, load
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


if __name__ == "__main__":
    unittest.main()
