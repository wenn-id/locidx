"""Gitignore-style pattern matching.

Enough of ``.gitignore`` semantics to feel natural, implemented with zero
dependencies:

* ``#`` comments and blank lines are ignored
* trailing ``/`` anchors the pattern to directories
* leading ``/`` anchors the pattern to the root of the scan
* ``!`` negations re-include previously excluded paths
* ``**`` matches any number of directories
* a pattern without a slash anywhere matches at any depth

Patterns come from, in order: ``.gitignore`` files found while walking,
``.locidxignore`` files in any scanned directory, and the ``--ignore`` /
``--no-ignore`` CLI flags.
"""

import re


def _translate(pattern, dir_only, anchored, base=""):
    """Compile a single glob pattern into a regex.

    Returns ``None`` when the pattern contains syntax this module does not
    handle (character classes), in which case the pattern is skipped. The
    caller stays safe and the indexer keeps going.

    Anchoring follows gitignore rules:

    * a pattern containing a slash (including a leading ``/``) is anchored
      to the directory that contains the ignore file
    * a bare pattern matches a basename at any depth
    """
    if "[" in pattern or "]" in pattern:
        return None

    i = 0
    out = []
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # Consume "**" plus any following "/".
                i += 2
                if i < n and pattern[i] == "/":
                    i += 1
                out.append(".*")
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "\\" and i + 1 < n:
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        else:
            out.append(re.escape(c))
        i += 1

    regex = "".join(out)
    if dir_only and not regex.endswith("/"):
        regex += "/"

    if anchored or "/" in pattern:
        # Anchored to the ignore file's directory.
        prefix = "^" + (re.escape(base) + "/" if base else "")
    else:
        prefix = "(^|/)"

    if dir_only:
        # Matches the directory itself and everything under it.
        return re.compile(prefix + regex), dir_only
    # Matches the exact path (or path boundary, so directories match too).
    return re.compile(prefix + regex + "($|/)"), dir_only


def _tokenize(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    negate = False
    if line.startswith("!"):
        negate = True
        line = line[1:].lstrip()
    if line.endswith("\\ "):
        line = line[:-2]
    dir_only = line.endswith("/")
    if dir_only:
        line = line.rstrip("/")
    anchored = line.startswith("/")
    if anchored:
        line = line.lstrip("/")
    if not line:
        return None
    return {
        "negate": negate,
        "dir_only": dir_only,
        "anchored": anchored,
        "source": line,
    }


def parse(text):
    """Parse ignore-file text into a list of rule dicts."""
    rules = []
    for raw in text.splitlines():
        token = _tokenize(raw)
        if token is not None:
            rules.append(token)
    return rules


class IgnoreMatcher:
    """Match relative paths against a stack of ignore rules.

    ``rules`` is a list of (base_dir, rules) pairs — ignore files located in
    deeper directories apply only to paths under that directory.
    """

    def __init__(self, rules=None):
        self._stack = list(rules or [])
        self._cache = {}

    def add(self, base_dir, rules):
        """Push an ignore file's rules, scoped to ``base_dir``."""
        self._stack.append((base_dir, rules))

    def _relevant(self, rel_path, is_dir):
        """Return the compiled rules that apply to this path, deepest first."""
        out = []
        for base, rules in reversed(self._stack):
            if base == "" or rel_path == base or rel_path.startswith(base + "/"):
                for r in rules:
                    key = (base, r["source"], is_dir, r["dir_only"], r["anchored"])
                    hit = self._cache.get(key)
                    if hit is None:
                        hit = _translate(
                            r["source"],
                            r["dir_only"],
                            r["anchored"],
                            base=base,
                        )
                        self._cache[key] = hit
                    if hit is not None and hit[0].search(rel_path):
                        out.append((r, hit[0]))
        return out

    def ignored(self, rel_path, is_dir):
        """Return True when ``rel_path`` should be excluded.

        Later rules win over earlier ones (gitignore semantics: the last
        matching pattern decides). A ``!`` rule can therefore re-include a
        path matched by a previous pattern.

        Directory-only patterns must also match the bare directory name, so
        a trailing-slash rule like ``build/`` rejects ``build`` itself, and
        every descendant.
        """
        candidates = []
        if is_dir:
            candidates.extend(self._relevant(rel_path + "/", True))
        candidates.extend(self._relevant(rel_path, is_dir))
        if not candidates:
            return False
        rule, _regex = candidates[-1]
        return not rule["negate"]

    def __bool__(self):
        return bool(self._stack)
