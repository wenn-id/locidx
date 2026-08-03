import json
import os
import unittest

from locidx.server import _handle
from locidx.tools import dispatch, TOOLS
from tests.helpers import LocIdxTestCase


class MCPTest(LocIdxTestCase):
    def test_initialize(self):
        resp = _handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "locidx")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list(self):
        resp = _handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertEqual(names, {"search", "index", "stats", "roots"})

    def test_tools_call_index_and_search(self):
        root = self.tree({"hello.py": "print('hello')\n"})
        result = dispatch("index", {"root": root})
        self.assertEqual(result["stats"]["added"], 1)

        result = dispatch("search", {"query": "hello", "root": root})
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["text"], "print('hello')")

    def test_tools_call_unknown(self):
        with self.assertRaises(KeyError):
            dispatch("nope", {})

    def test_unknown_method(self):
        resp = _handle({"jsonrpc": "2.0", "id": 9, "method": "bogus"})
        self.assertEqual(resp["error"]["code"], -32601)

    def test_schema_is_json_serializable(self):
        for tool in TOOLS.values():
            json.dumps(tool)


if __name__ == "__main__":
    unittest.main()
