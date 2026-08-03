# locidx

**Local-first code indexer and search.** Index a codebase once, then search it
instantly — offline, private, and with **zero dependencies**.

`locidx` builds a SQLite index of your project, respects `.gitignore`-style
rules, updates incrementally, and gives you three ways to query it: a CLI, an
interactive TUI, and a [Model Context Protocol](https://modelcontextprotocol.io)
server so AI agents can search your code too.

---

## Why locidx?

* **Zero dependencies.** Python 3.9+ standard library only. No `pip install`
  battle royale — the indexer, CLI, TUI, and MCP server all use `sqlite3`,
  `curses`, and `json`.
* **Private and local-first.** Everything lives in SQLite files on your
  machine. No network, no telemetry, no "send us your code" to get search.
* **Fast and incremental.** Only files whose mtime changed are re-read.
  Searching reads the database, never the filesystem.
* **gitignore-aware.** Real `.gitignore` semantics: negation, anchoring,
  `**`, directory-only patterns — plus optional `--ignore` globs and
  per-directory `.locidxignore` files.
* **One tool, three interfaces.** Terminal, TUI, and MCP — the same index
  serves all three.

## Install

```bash
# From source (no install needed to run — just clone and use ./locidx)
git clone https://github.com/wenn-id/locidx
cd locidx

# Or install the package (creates the `locidx` command)
python -m pip install .
```

You can also run it straight from the checkout without installing:

```bash
python -m locidx.cli --help
```

## Quick start

```bash
# 1. Index a project (creates .locidx.sqlite inside it)
locidx index ~/src/myproject --stats

# 2. Search it
locidx find "def parse_" ~/src/myproject

# 3. Language stats
locidx stats --json ~/src/myproject
```

### Global database

By default `locidx index` creates a **per-project** database
(`.locidx.sqlite` in the indexed folder). That keeps everything self-contained
and shareable.

For a single machine-wide index across many projects, add `--global`:

```bash
locidx index ~/src/project-a --global
locidx index ~/src/project-b --global
locidx search "TODO" --global          # searches every indexed root
locidx roots                           # list all indexed roots
locidx clear                           # wipe the global index
```

## CLI reference

| Command | Description |
| --- | --- |
| `locidx index [PATH] [--global] [--stats] [--no-ignore] [--ignore GLOB] [--size-limit MB]` | Build or update the index |
| `locidx find PATTERN [PATH]` | Search inside a project's own index |
| `locidx search PATTERN [PATH] [--global] [--max N] [--case]` | Search the global index |
| `locidx stats [PATH] [--json]` | Per-language file/line stats |
| `locidx roots` | List indexed roots |
| `locidx clear` | Wipe the global index |

## Interactive TUI

```bash
locidx tui [PATH]
```

* `/` — enter a search query
* `j` / `k` — move through results
* `o` — open the selected file in `$VISUAL`/`$EDITOR`
* `g` / `G` — jump to top / bottom
* `q` — quit

> The TUI is a thin wrapper over the same search core, so results in the
> terminal and the TUI are always identical.

## MCP server

`locidx` speaks the Model Context Protocol over stdio, so any MCP client
(Claude, code agents, custom tooling) can search your indexed code with
structured results.

```bash
# Run the server directly
locidx mcp
```

Configure it in your MCP client, e.g. Claude Desktop:

```json
{
  "mcpServers": {
    "locidx": {
      "command": "locidx",
      "args": ["mcp"]
    }
  }
}
```

### MCP tools

| Tool | Description |
| --- | --- |
| `search(query, root?, max_results?)` | Literal substring search; returns matching lines with paths and line numbers |
| `index(root, extra_ignores?, no_ignore?)` | Incrementally index a directory |
| `stats(root?)` | Per-language file/line statistics |
| `roots()` | List every indexed root |

The server is a minimal JSON-RPC 2.0 implementation over stdio with zero
dependencies — no `mcp` SDK required.

## How it works

```
                    ┌─────────────────────────────┐
  .gitignore ──►    │                             │
                    │   locidx index PATH         │
  source tree ──►   │   ┌──────────────────┐      │
                    │   │  incremental walk │─────┼──►  .locidx.sqlite
                    │   └──────────────────┘      │        (SQLite)
                    └─────────────────────────────┘
                             │
               ┌─────────────┼──────────────┐
               ▼             ▼              ▼
           locidx find   locidx stats    locidx mcp
           (CLI)         (CLI/TUI)       (MCP server)
```

1. `locidx index` walks the tree, applies ignore rules, and stores each text
   file's path, size, mtime, a SHA-256 content hash, and the text itself in
   SQLite.
2. Unchanged files (same size + mtime) are skipped on subsequent runs.
3. Queries (`find`, `stats`, TUI, MCP) read only from SQLite — the
   filesystem is never touched again.

## Ignore rules

`locidx` honors `.gitignore` and `.locidxignore` files at any depth, plus
`--ignore` globs:

```
# .gitignore
*.log                # everywhere
build/               # directory only
/src/generated/      # anchored
!keep.log            # re-include
node_modules/        # handled out of the box
```

`--no-ignore` disables all ignore handling.

## Project layout

```
locidx/
├── locidx/
│   ├── cli.py       # argparse CLI
│   ├── tui.py       # curses TUI
│   ├── indexer.py   # incremental walk + content hashing
│   ├── search.py    # literal substring search
│   ├── stats.py     # language detection + aggregation
│   ├── ignore.py    # gitignore-style matching
│   ├── db.py        # tiny SQLite wrapper (schema + helpers)
│   ├── mcp.py       # MCP entrypoint
│   ├── server.py    # JSON-RPC 2.0 stdio server
│   └── tools.py     # agent-friendly tool wrappers
└── tests/           # stdlib unittest suite (runs in CI without install)
```

## Development

```bash
# Run the test suite (stdlib only)
python -m unittest discover -s tests -v

# Or with pytest, if you have it
python -m pytest -q
```

CI runs the same unittest command across Python 3.9–3.12.

## License

MIT — do whatever you want with it, but please star it if it saves you time.
