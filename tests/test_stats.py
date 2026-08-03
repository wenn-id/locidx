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

    def test_empty(self):
        root = self.tree({})
        db = self.index(root)
        rows, totals = aggregate(db, root=root)
        self.assertEqual(rows, [])
        self.assertEqual(totals, {"files": 0, "lines": 0})


if __name__ == "__main__":
    unittest.main()
