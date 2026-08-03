import io
import json
import os
import unittest
from contextlib import redirect_stdout

from locidx.cli import build_parser, main
from tests.helpers import LocIdxTestCase


class CliTest(LocIdxTestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_index_and_find_roundtrip(self):
        root = self.tree({
            "greet.py": "def greet():\n    return 'hello'\n",
            "data.txt": "hello there\n",
        })
        code, out = self.run_cli(["index", root])
        self.assertEqual(code, 0)
        self.assertIn("Indexed 2 files", out)

        code, out = self.run_cli(["find", "greet", root])
        self.assertEqual(code, 0)
        self.assertIn("greet.py:1", out)

    def test_stats_json(self):
        root = self.tree({"a.py": "1\n2\n3\n"})
        self.run_cli(["index", root])
        code, out = self.run_cli(["stats", "--json", root])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("languages", payload)
        self.assertEqual(payload["languages"][0]["language"], "Python")

    def test_search_no_results(self):
        root = self.tree({"a.py": "x\n"})
        self.run_cli(["index", root])
        code, out = self.run_cli(["search", "zzz", root])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_version(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_bad_path(self):
        code, out = self.run_cli(["index", "/definitely/not/here"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
