import os
import unittest

from locidx.stats import aggregate, detect_language
from tests.helpers import LocIdxTestCase


class StatsTest(LocIdxTestCase):
    def test_detect_language(self):
        self.assertEqual(detect_language("main.py"), "Python")
        self.assertEqual(detect_language("app.tsx"), "TypeScript")
        self.assertEqual(detect_language("Dockerfile"), "Dockerfile")
        self.assertEqual(detect_language("Makefile"), "Makefile")
        self.assertEqual(detect_language("unknown.xyz"), "Unknown")

    def test_aggregate(self):
        root = self.tree({
            "a.py": "1\n2\n3\n",
            "b.py": "1\n2\n",
            "c.js": "1\n",
        })
        db = self.index(root)
        rows, totals = aggregate(db, root=root)
        py = next(r for r in rows if r["language"] == "Python")
        self.assertEqual(py["files"], 2)
        # 3-line file contributes 3; 2-line file is below min_lines=3, skipped.
        self.assertEqual(py["lines"], 3)
        js = next(r for r in rows if r["language"] == "JavaScript")
        self.assertEqual(js["files"], 1)
        self.assertEqual(js["lines"], 0)
        self.assertEqual(totals["files"], 3)

    def test_stats_root_filter_does_not_match_sibling_or_case_variant(self):
        root = self.tmp("root")
        sibling = self.tmp("root-app")
        case_variant = self.tmp("ROOT")
        for path in (root, sibling, case_variant):
            os.makedirs(path, exist_ok=True)
        db = self.db()
        self.addCleanup(db.close)
        for path in (root, sibling, case_variant):
            file_path = os.path.join(path, "a.py")
            db.execute(
                "INSERT INTO files(path, size, mtime, text_hash, indexed_at) VALUES (?, ?, ?, ?, ?)",
                (file_path, 6, 1, "hash", "now"),
            )
            db.execute("INSERT INTO content(path, text) VALUES (?, ?)", (file_path, "1\n2\n3\n"))
        db.commit()

        _rows, totals = aggregate(db, root=root)
        self.assertEqual(totals, {"files": 1, "lines": 3})

    def test_empty(self):
        root = self.tree({})
        db = self.index(root)
        rows, totals = aggregate(db, root=root)
        self.assertEqual(rows, [])
        self.assertEqual(totals, {"files": 0, "lines": 0})


if __name__ == "__main__":
    unittest.main()
