# AGENTS.md — contract for any AI agent working in this vault

> This file is the durable "connection". It travels with the vault, so any future
> agent session (me, Qwen Code, an MCP client) picks up the same rules without
> you having to re-explain them. Keep it at the vault root.

## Identity of this vault
This is a **data farm**: notes are *records*, not prose. Every record is typed,
has frontmatter, and links to the records it depends on. The graph is the product.

## Folder contract (PARA + provenance layers)
| Folder | Holds | Rule |
|---|---|---|
| `00-Inbox/` | unsorted captures | must be emptied into a typed folder within 7 days |
| `10-Sources/` | one note per external source (paper, page, person, dataset) | never edited after capture except for `status` |
| `20-Entities/` | one note per thing that persists (system, person, concept, dataset) | the hub layer; most links point here |
| `30-Claims/` | one atomic, falsifiable statement per note | must carry `source`, `confidence`, `verified` |
| `40-Projects/` | active work with a deadline | links to the entities and claims it uses |
| `50-Areas/` | ongoing responsibilities | no deadline |
| `90-Meta/` | `Home`, `Conventions`, MOCs, generated indexes | `Home.md` is the graph entry point |
| `.datafarm/` | **generated** artifacts (`graph.json`, `graph.html`, `stats.json`) | machine-owned; agents may overwrite; humans do not edit |
| `Attachments/` | binary files | referenced with `![[file]]` only |

## Hard rules for agents
1. **Read-only by default.** Writes go to `.datafarm/` unless the user explicitly approves.
2. **Never delete or rename a note.** To retire one, set `status: archived` in frontmatter.
3. **Never invent a source.** A `30-Claims/` note without a real `source` is invalid — write `source: unverified` and `confidence: low` instead.
4. **Atomic notes.** One idea per note. Prefer a new note + link over a longer note.
5. **Links over tags for relationships; tags for state/type.** Use `[[wikilinks]]` (shortest path, no `.md`) so Obsidian's graph resolves them.
6. **Idempotent generation.** Anything written to `.datafarm/` must be reproducible from the notes alone.
7. **No secrets in notes.** If you find one, tell the user; do not copy it anywhere.
8. **Report what you actually ran**, including failures. Never claim a result you did not verify.

## Frontmatter schema (minimum)
```yaml
---
id: ent-0007              # stable, never reused
type: entity              # source | entity | claim | project | area | meta
title: Vector Store
tags: [infra, storage]
created: 2026-10-25
updated: 2026-10-25
status: draft             # draft | verified | stale | archived
---
```
Claims add:
```yaml
source: "[[SRC-0012 Attention Is All You Need]]"
confidence: high          # high | medium | low
verified: 2026-10-25      # date the claim was checked, or false
supersedes: []            # ids of claims this replaces
```

## Provenance rule (this is what makes it a *second brain* and not a pile of text)
Every claim traces to a source; every source records where it came from
(`url`, `retrieved`, `quote`). If the chain breaks, the claim is `confidence: low`.

## Regenerate the graph
```bash
python3 .datafarm-tools/vault_indexer.py . --out .datafarm --reuse-layout
python3 .datafarm-tools/vault_probe.py . --test-write
```
