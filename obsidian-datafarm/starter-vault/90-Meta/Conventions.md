---
id: meta-conventions
type: meta
title: Conventions
tags: [conventions]
created: 2026-10-25
updated: 2026-10-25
status: verified
---

# Conventions

## Filenames
`<PREFIX>-<NNN> <Human Title>.md` → `SRC-014 Attention Is All You Need.md`
Prefixes: `SRC` source · `ENT` entity · `CLM` claim · `PRJ` project · `AREA` area · `MOC` map of content.
Spaces are fine; avoid `# ^ [ ] | :` and leading dots (Obsidian ignores dot-prefixed files).

## Links
- Use `[[wikilink]]`, shortest-path form, no `.md`.
- Alias when the sentence needs it: `[[ENT-007 Vector Store|the vector store]]`.
- Point at a section with `[[note#Heading]]`, at a block with `[[note#^id]]`.
- **Do not** create two notes with the same basename — resolution becomes ambiguous
  (the indexer warns about this in `stats.json → duplicate_basenames`).

## Tags
Type/state only: `#status/draft`, `#status/verified`, `#area/security`.
Relationships are links, never tags. Tags must start with a letter (`#1984` is not a tag in Obsidian).

## Status lifecycle
`draft → verified → stale → archived`. Nothing is ever deleted.
