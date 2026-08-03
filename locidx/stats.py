"""Language detection and stat aggregation."""

import json
import os

# Common programming language signatures by extension.
# Values are (extension, human name). Order matters: the first match wins.
_EXTENSIONS = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".hxx": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".m": "Objective-C",
    ".mm": "Objective-C",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".jsx": "JavaScript",
    ".astro": "Astro",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".cfg": "INI",
    ".dockerfile": "Dockerfile",
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl",
    ".r": "R",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".fs": "F#",
    ".fsx": "F#",
    ".groovy": "Groovy",
    ".gradle": "Gradle",
    ".vb": "Visual Basic",
    ".vbs": "VBScript",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".nim": "Nim",
    ".zig": "Zig",
    ".odin": "Odin",
    ".v": "V",
    ".vsh": "V",
    ".crystal": "Crystal",
    ".jl": "Julia",
    ".tcl": "Tcl",
    ".m4": "m4",
    ".make": "Makefile",
    ".mk": "Makefile",
    ".cmake": "CMake",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".sol": "Solidity",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".env": "Env",
    ".properties": "Properties",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".txt": "Text",
    ".log": "Log",
}

# Special filenames that don't use extensions.
_NAMES = {
    "makefile": "Makefile",
    "gnumakefile": "Makefile",
    "cmakelists.txt": "CMake",
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    "jenkinsfile": "Jenkinsfile",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
    "procfile": "Procfile",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "package.json": "JSON",
    "composer.json": "JSON",
    "cargo.toml": "TOML",
    "go.mod": "Go",
    "gradlew": "Gradle",
    "pipfile": "Python",
    ".bashrc": "Shell",
    ".bash_profile": "Shell",
    ".zshrc": "Shell",
    ".vimrc": "Vim",
    "webpack.config.js": "JavaScript",
}

_SHEBANG = (
    ("python", "Python"),
    ("node", "JavaScript"),
    ("deno", "JavaScript"),
    ("bun", "JavaScript"),
    ("bash", "Shell"),
    ("sh", "Shell"),
    ("zsh", "Shell"),
    ("fish", "Shell"),
    ("ruby", "Ruby"),
    ("perl", "Perl"),
    ("php", "PHP"),
    ("lua", "Lua"),
    ("pwsh", "PowerShell"),
    ("powershell", "PowerShell"),
    ("swift", "Swift"),
    ("go", "Go"),
)


def detect_language(path):
    """Return the best-guess language name for a file path."""
    base = os.path.basename(path)
    low = base.lower()
    if low in _NAMES:
        return _NAMES[low]
    ext = os.path.splitext(low)[1]
    if ext in _EXTENSIONS:
        return _EXTENSIONS[ext]
    if low == ".gitignore":
        return "GitIgnore"
    return "Unknown"


def aggregate(db, root=None, min_lines=3):
    """Compute per-language stats over indexed files.

    Returns ``(rows, totals)`` where ``rows`` is a list of dicts
    (language, files, lines) sorted by lines descending, and ``totals`` is a
    dict with total files and lines. Files with fewer than ``min_lines``
    lines are counted as files but excluded from line totals — this keeps
    generated single-line files from skewing the numbers.
    """
    params = []
    where = ""
    if root is not None:
        where = "WHERE f.path LIKE ?"
        params.append(os.path.abspath(root) + "%")

    rows = db.query(
        "SELECT f.path, c.text FROM files f "
        "JOIN content c ON c.path = f.path %s" % where,
        params,
    )

    by_lang = {}
    total_files = 0
    total_lines = 0
    for row in rows:
        path, text = row["path"], row["text"]
        if not text:
            continue
        lang = detect_language(path)
        nlines = text.count("\n") + (0 if text.endswith("\n") else 1)
        bucket = by_lang.setdefault(
            lang, {"language": lang, "files": 0, "lines": 0}
        )
        bucket["files"] += 1
        total_files += 1
        if nlines >= min_lines:
            bucket["lines"] += nlines
            total_lines += nlines

    ordered = sorted(by_lang.values(), key=lambda b: (-b["lines"], -b["files"], b["language"]))
    totals = {"files": total_files, "lines": total_lines}
    return ordered, totals


def to_json(rows, totals, indent=2):
    """Serialize stats to JSON (single dependency-free writer)."""
    return json.dumps(
        {"languages": rows, "totals": totals}, indent=indent, ensure_ascii=False
    )
