# Obsidian Data Farm — connection kit + v0 graph engine

Status: **connection layer designed and verified; data-farm build is intentionally deferred until you share the larger project brief.**

```
obsidian-datafarm/
├── HOW-TO-CONNECT-TO-OBSIDIAN.md   ← READ THIS FIRST (5 connection paths, exact commands)
├── README.md                       ← this file
├── CONNECTION-REPORT-demo.txt      ← real probe output against the demo vault
├── src/
│   ├── vault_probe.py              ← read-only connection + secret diagnostic
│   └── vault_indexer.py            ← notes → graph.json / graph.html / stats.json
├── tests/test_vault_tools.py       ← 34 tests, stdlib unittest, all passing
├── starter-vault/                  ← open this folder as an Obsidian vault
│   ├── AGENTS.md                   ← the contract any future AI agent must obey
│   ├── 00-Inbox … 90-Meta/         ← PARA + provenance layers
│   ├── _templates/                 ← source / entity / claim / project
│   ├── .datafarm-tools/            ← copy of the two scripts (dot-prefixed = invisible to Obsidian)
│   └── .datafarm/                  ← generated graph artifacts
└── demo_vault/                     ← 123-note synthetic vault used for validation
```

## Quick start (60 seconds)

```bash
cd /home/user/obsidian-datafarm

# 1. is my vault reachable and safe to share?
python3 src/vault_probe.py /path/to/MyVault --test-write

# 2. build the graph
python3 src/vault_indexer.py /path/to/MyVault --out /path/to/MyVault/.datafarm --reuse-layout
```
Outputs land in `.datafarm/`: `graph.html` (open in any browser, works offline), `graph.json`
(pipeline input), `stats.json` (health report).

To see it working right now, open `demo_vault/.datafarm/graph.html`.

## What the indexer understands

| Feature | Behaviour |
|---|---|
| `[[wikilink]]`, `[[t\|alias]]`, `[[t#heading]]`, `[[t#^block]]`, `![[embed]]` | resolved to real paths |
| `[text](relative.md)`, `![](img.png)` | resolved; `http(s)/mailto/obsidian/file` links counted separately, not as edges |
| Link resolution | Obsidian-style shortest-path: exact path → path+`.md` → unique basename → longest-suffix match on duplicates |
| Code | fenced ` ``` `/`~~~` blocks and inline `` `code` `` are stripped before link/tag extraction |
| Tags | inline `#tag`, nested `#a/b`, frontmatter `tags:` (list or inline). Case-insensitive. `#1984` rejected (Obsidian rule: must contain a non-numeric char) |
| Frontmatter | minimal YAML reader (scalars, inline `[a,b]`, block lists) — no dependency |
| Metrics | in/out degree, orphans, density, unresolved links, duplicate basenames, word/byte counts, top hubs |
| Layout | Barnes–Hut quadtree force-directed, deterministic (seeded), `--reuse-layout` warm start |
| Excluded | `.obsidian .trash .git .datafarm .datafarm-tools _templates templates node_modules __pycache__`, dot-files, **all symlinks** |

## Verified performance (this machine, single core, pure stdlib)

| Notes | Edges | Scan | Layout | HTML |
|---|---|---|---|---|
| 123 (demo) | 361 | <0.1 s | 0.4 s total | 75 KB |
| 500 | 1 992 | 0.06 s | 2.5 s | 0.15 MB |
| 1 500 | 5 987 | 0.17 s | 9.7 s | 0.43 MB |
| 3 000 | 11 989 | 0.35 s | 13.1 s | 0.86 MB |
| 5 000 | 19 992 | 0.51 s | 15.4 s | 1.11 MB |

The first version used exact O(n²) repulsion and took **199 s at 3 000 notes**; Barnes–Hut cut
that to **13 s** (15×). Layout quality was cross-checked against `networkx.spring_layout` on the
same 500-node graph: median edge length / extent **0.155 vs 0.225** (tighter), linked-vs-random
pair distance ratio **0.75 vs 0.61**.

## Tests

```bash
python3 -m unittest discover -s tests -v     # 34 tests
```
Covered: alias/heading/block links, links inside code, ambiguous + duplicate basenames, optional
`.md`, self-links, unresolved tracking, non-UTF-8 files, empty vault, tag rules, frontmatter
shapes, layout determinism/finiteness/disconnected components, `--max-render` capping, HTML
`</script>` breakout escaping, CLI exit codes, probe secret detection **and non-leakage**,
write-test cleanup, symlink escape + symlink loop.

## Security posture

* Both scripts are **read-only** against the vault; the only writes are to `--out`.
* The probe's secret scanner prints **redacted previews only** (`AKIAIOSFODN…REDACTED`) — a test
  asserts the full value never appears in the report.
* `graph.html` is fully self-contained: no CDN, no fonts, no network (the only `http://` string is
  the SVG XML namespace). Payload is JSON-embedded with `</` escaped and HTML-escaped titles.
* Symlinks are never followed, so a vault containing a link to `/` cannot exfiltrate or hang.
* No third-party packages at runtime. `networkx`/`numpy`/`scipy` were installed **only** to
  cross-validate layout quality and are not imported by the shipped code.

## Deferred until you share the project brief

Semantic layer (embeddings + similarity edges), typed edges in frontmatter, incremental ingestion
from external sources, community detection / MOC auto-generation, Dataview & Bases integration,
canvas export, conflict-free write-back, and the graph QA harness. Each is a design decision that
depends on your data volume and consumers — guessing now would be overengineering.
