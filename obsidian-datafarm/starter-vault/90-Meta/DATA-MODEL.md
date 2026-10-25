---
id: meta-datamodel
type: meta
title: Data Model
tags: [schema, provenance]
created: 2026-10-25
updated: 2026-10-25
status: verified
---

# Data Model

Four record types, one direction of truth:

```
Source ──supports──> Claim ──about──> Entity <──uses── Project
```

| Type | Cardinality | Required frontmatter | Links to |
|---|---|---|---|
| `source` | 1 per external artifact | `url`, `retrieved`, `quote` | nothing (leaf) |
| `claim` | 1 atomic statement | `source`, `confidence`, `verified` | 1 source, ≥1 entity |
| `entity` | 1 per persistent thing | `type`, `status` | claims, other entities |
| `project` | 1 per bounded effort | `due`, `status` | entities, claims |

## Invariants (enforce these in review)
1. No claim without a source. `source: unverified` + `confidence: low` is the escape hatch.
2. No orphan entity: every entity is linked from ≥1 claim or project.
3. Every `supersedes` list points at notes with `status: archived`.
4. `.datafarm/` is derived — if it disagrees with the notes, the notes win.

## Why this shape
It gives you (a) an auditable second brain — every statement is falsifiable and
traceable; and (b) a graph that is meaningful rather than decorative, because edges
carry a *type* encoded in the folder + frontmatter of their endpoints.
