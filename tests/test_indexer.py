import os
import unittest

from locidx.indexer import Indexer, _looks_binary
from tests.helpers import LocIdxTestCase


class IndexerTest(LocIdxTestCase):
    def test_indexes_text_files(self):
        root = self.tree({
            "a.py": "def f():\n    return 1\n",
            "b.txt": "hello\n",
        })
        db = self.index(root)
        paths = {r["path"] for r in db.query("SELECT path FROM files")}
        self.assertEqual(paths, {os.path.join(root, "a.py"), os.path.join(root, "b.txt")})

    def test_skips_binary_and_hidden(self):
        root = self.tmp("bin")
        os.makedirs(root)
        with open(os.path.join(root, "data.bin"), "wb") as fh:
            fh.write(b"\x00\x01\x02binary")
        self.assertFalse(_looks_binary(b"hello\n"))
        self.assertTrue(_looks_binary(b"\x00\x01\x02"))

    def test_removes_deleted_files(self):
        root = self.tree({"a.py": "x\n"})
        db = self.index(root)
        os.unlink(os.path.join(root, "a.py"))
        Indexer(root, db).run()
        db.commit()
        self.assertEqual(db.query("SELECT COUNT(*) AS n FROM files")[0]["n"], 0)

    def test_incremental_root_does_not_remove_sibling_prefix(self):
        root = self.tmp("root")
        sibling = self.tmp("root-app")
        os.makedirs(root, exist_ok=True)
        os.makedirs(sibling, exist_ok=True)
        with open(os.path.join(root, "inside.py"), "w") as fh:
            fh.write("inside\n")
        with open(os.path.join(sibling, "outside.py"), "w") as fh:
            fh.write("outside\n")
        db = self.db()
        self.addCleanup(db.close)

        Indexer(sibling, db).run()
        Indexer(root, db).run()
        db.commit()

        paths = {row["path"] for row in db.query("SELECT path FROM files")}
        self.assertEqual(
            paths,
            {
                os.path.join(root, "inside.py"),
                os.path.join(sibling, "outside.py"),
            },
        )

    def test_incremental_skips_unchanged(self):
        root = self.tree({"a.py": "x\n"})
        db = self.index(root)
        first = db.query("SELECT text_hash FROM files")[0]["text_hash"]
        Indexer(root, db).run()
        second = db.query("SELECT text_hash FROM files")[0]["text_hash"]
        self.assertEqual(first, second)

    def test_updates_on_change(self):
        root = self.tree({"a.py": "x\n"})
        db = self.index(root)
        with open(os.path.join(root, "a.py"), "w") as fh:
            fh.write("y\n")
        # Ensure the mtime actually changes (coarse filesystems).
        os.utime(os.path.join(root, "a.py"), (os.path.getmtime(root) + 2, os.path.getmtime(root) + 2))
        Indexer(root, db).run()
        db.commit()
        text = db.query("SELECT text FROM content")[0]["text"]
        self.assertEqual(text, "y\n")

    def test_respects_gitignore(self):
        root = self.tree({
            ".gitignore": "secret.txt\nbuild/\n",
            "secret.txt": "hidden",
            "build/x.py": "print(1)\n",
            "ok.py": "print(2)\n",
        })
        db = self.index(root)
        paths = {os.path.relpath(r["path"], root) for r in db.query("SELECT path FROM files")}
        self.assertEqual(paths, {"ok.py"})

    def test_respects_root_locidxignore(self):
        root = self.tree({
            ".locidxignore": "vendor/\n*.log\n/root-only.py\n",
            "vendor/big.py": "ignored\n",
            "debug.log": "ignored\n",
            "root-only.py": "ignored\n",
            "nested/root-only.py": "kept\n",
            "ok.py": "kept\n",
        })
        db = self.index(root)
        paths = {os.path.relpath(r["path"], root) for r in db.query("SELECT path FROM files")}
        self.assertEqual(paths, {"nested/root-only.py", "ok.py"})

    def test_extra_ignore(self):
        root = self.tree({"a.py": "x\n", "b.py": "y\n"})
        db = self.index(root, extra_ignores=["b.py"])
        paths = {os.path.relpath(r["path"], root) for r in db.query("SELECT path FROM files")}
        self.assertEqual(paths, {"a.py"})

    def test_size_limit(self):
        root = self.tree({"big.py": "x" * 100})
        db = self.index(root, size_limit=0)
        self.assertEqual(db.query("SELECT COUNT(*) AS n FROM files")[0]["n"], 0)


if __name__ == "__main__":
    unittest.main()
