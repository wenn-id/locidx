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
