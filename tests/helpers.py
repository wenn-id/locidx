"""Shared test helpers: temp trees and databases."""

import os
import shutil
import tempfile
import unittest

from locidx.db import temp_db_path
from locidx.db import Database


def make_tree(base, spec):
    """Create a directory tree from a {path: content} mapping."""
    for rel, content in spec.items():
        full = os.path.join(base, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if content is None:
            os.makedirs(full, exist_ok=True)
        else:
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content)
    return base


class LocIdxTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="locidx-test-")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def tmp(self, *parts):
        return os.path.join(self._tmp, *parts)

    def tree(self, spec):
        return make_tree(self._tmp, spec)

    def db(self):
        return Database(temp_db_path())

    def index(self, root, db=None, **kwargs):
        from locidx.indexer import Indexer

        if db is None:
            db = self.db()
            self.addCleanup(db.close)
        Indexer(root, db, **kwargs).run()
        db.commit()
        return db
