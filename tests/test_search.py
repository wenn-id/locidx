import os
import unittest

from locidx.search import search
from tests.helpers import LocIdxTestCase


class SearchTest(LocIdxTestCase):
    def test_finds_substring(self):
        root = self.tree({"a.py": "alpha\nbeta\nalpha again\n"})
        db = self.index(root)
        results = search(db, "alpha")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["text"].startswith("alpha") for r in results))
        self.assertEqual([r["lineno"] for r in results], [1, 3])

    def test_case_insensitive_by_default(self):
        root = self.tree({"a.py": "Hello World\n"})
        db = self.index(root)
        self.assertEqual(len(search(db, "hello")), 1)
        self.assertEqual(len(search(db, "HELLO")), 1)

    def test_case_sensitive(self):
        root = self.tree({"a.py": "Hello\n"})
        db = self.index(root)
        self.assertEqual(len(search(db, "hello", case=True)), 0)
        self.assertEqual(len(search(db, "Hello", case=True)), 1)

    def test_root_filter(self):
        root = self.tmp("root-a")
        other = self.tmp("root-b")
        os.makedirs(root, exist_ok=True)
        os.makedirs(other, exist_ok=True)
        with open(os.path.join(root, "a.py"), "w") as fh:
            fh.write("needle\n")
        with open(os.path.join(other, "b.py"), "w") as fh:
            fh.write("needle\n")
        db = self.db()
        self.addCleanup(db.close)
        from locidx.indexer import Indexer

        Indexer(root, db).run()
        Indexer(other, db).run()
        db.commit()
        self.assertEqual(len(search(db, "needle", root=root)), 1)
        self.assertEqual(len(search(db, "needle")), 2)

    def test_root_filter_does_not_match_sibling_prefix(self):
        root = self.tmp("root")
        sibling = self.tmp("root-app")
        os.makedirs(root, exist_ok=True)
        os.makedirs(sibling, exist_ok=True)
        with open(os.path.join(root, "inside.py"), "w") as fh:
            fh.write("needle\n")
        with open(os.path.join(sibling, "outside.py"), "w") as fh:
            fh.write("needle\n")
        db = self.db()
        self.addCleanup(db.close)
        from locidx.indexer import Indexer

        Indexer(root, db).run()
        Indexer(sibling, db).run()
        db.commit()
        self.assertEqual(
            [result["path"] for result in search(db, "needle", root=root)],
            [os.path.join(root, "inside.py")],
        )

    def test_root_filter_is_case_sensitive(self):
        root = self.tmp("root")
        case_variant = self.tmp("ROOT")
        os.makedirs(root, exist_ok=True)
        os.makedirs(case_variant, exist_ok=True)
        db = self.db()
        self.addCleanup(db.close)
        rows = [
            (os.path.join(root, "inside.py"), "needle\n"),
            (os.path.join(case_variant, "outside.py"), "needle\n"),
        ]
        for path, text in rows:
            db.execute(
                "INSERT INTO files(path, size, mtime, text_hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                (path, len(text), 1, "hash", "now"),
            )
            db.execute("INSERT INTO content(path, text) VALUES (?, ?)", (path, text))
        db.commit()

        self.assertEqual(
            [result["path"] for result in search(db, "needle", root=root)],
            [os.path.join(root, "inside.py")],
        )

    def test_max_results(self):
        root = self.tree({"a.py": "x\n" * 10})
        db = self.index(root)
        self.assertEqual(len(search(db, "x", max_results=3)), 3)

    def test_empty_pattern(self):
        root = self.tree({"a.py": "x\n"})
        db = self.index(root)
        self.assertEqual(search(db, ""), [])


if __name__ == "__main__":
    unittest.main()
