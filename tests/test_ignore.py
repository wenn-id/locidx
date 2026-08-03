import unittest

from locidx.ignore import IgnoreMatcher, parse


class IgnoreTest(unittest.TestCase):
    def match(self, text, path, is_dir=False):
        m = IgnoreMatcher([("", parse(text))])
        return m.ignored(path, is_dir=is_dir)

    def test_comment_and_blank(self):
        self.assertFalse(self.match("# hi\n\n", "a.py"))

    def test_basename_anywhere(self):
        self.assertTrue(self.match("*.py\n", "src/a.py"))
        self.assertFalse(self.match("*.py\n", "src/a.txt"))

    def test_dir_only(self):
        self.assertTrue(self.match("build/\n", "build/x.py", is_dir=True))
        self.assertTrue(self.match("build/\n", "build", is_dir=True))
        # Without the trailing slash it still matches directories by name.
        self.assertTrue(self.match("build\n", "build/x.py", is_dir=True))

    def test_anchored_root(self):
        self.assertTrue(self.match("/src\n", "src/a.py", is_dir=True))
        self.assertFalse(self.match("/src\n", "other/src/a.py", is_dir=True))

    def test_negation_wins(self):
        self.assertFalse(self.match("*.py\n!keep.py\n", "keep.py"))
        self.assertTrue(self.match("*.py\n!keep.py\n", "other.py"))

    def test_double_star(self):
        self.assertTrue(self.match("**/test/**\n", "a/b/test/c.py", is_dir=True))
        self.assertTrue(self.match("foo/**/bar\n", "foo/x/bar", is_dir=True))

    def test_internal_slash_relative(self):
        self.assertTrue(self.match("src/generated/\n", "src/generated/x", is_dir=True))

    def test_character_class_is_skipped(self):
        # Unsupported syntax is ignored safely rather than exploding.
        self.assertFalse(self.match("file[0-9].txt\n", "file5.txt"))


if __name__ == "__main__":
    unittest.main()
