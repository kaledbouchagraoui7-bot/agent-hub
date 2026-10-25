# Analysed code library (not vendored)

Two repositories cloned, analysed and parked for later reuse. Nothing here is
wired into `trader-agents` or `obsidian-datafarm`; it is reference material.

| repo | upstream HEAD | licence | kept here | full clone |
|---|---|---|---|---|
| [cheaper-inference/OmniRoute](https://github.com/cheaper-inference/OmniRoute) | `5b3be70ba82ce70b59d02e2893afa3d81b6ee88b` (2026-10-23) | MIT, © 2026 diegosouzapw | extract analysed in-session; not vendored, see `third_party/MANIFEST.md` | too big to persist, see below |
| [x-cmd/x-cmd](https://github.com/x-cmd/x-cmd) | `d7070f666ea26f1f53449e4cd21e04151ba4d9de` (2026-10-24) | Apache-2.0, © Li Junhao + Zhongshan Xuxuyunsheng Technology | full source analysed in-session; not vendored, see `third_party/MANIFEST.md` | this *is* the full source |

## Re-clone commands (exact, verified)

```bash
git clone --depth 1 https://github.com/cheaper-inference/OmniRoute.git   # 986 MB, 26,343 files
git clone --depth 1 https://github.com/x-cmd/x-cmd.git                    #  45 MB,  5,470 files
```

The full OmniRoute working copy was moved to `/tmp/full-clones/OmniRoute` and is
available **for this session only**. It is not part of the persisted workspace,
because the checkout is 844 MB plus a 142 MB `.git`, and 608 MB of that is
`docs/i18n` (10,584 translated markdown files). Re-clone it when needed.

## What was kept from OmniRoute, and what was dropped

Kept: `skills/` (46 `SKILL.md` agent manifests), `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `llm.txt`, `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`,
`package.json`, `CHANGELOG.md`, `ROADMAP.md`, `SECURITY.md`, `CONTRIBUTING.md`,
`Makefile`, and `docs/` minus `docs/i18n`.

Dropped: `.git` (142 MB), `docs/i18n` (608 MB), `src/` (111 MB, 3,676 TS files),
`tests/` (66 MB), `open-sse/` (23 MB), `electron/`, `node_modules`-adjacent build
output. `MANIFEST-upstream-git-ls-tree.txt` lists all 26,343 upstream paths with
their git blob SHAs, so anything dropped can be identified and fetched precisely.

x-cmd is small enough to keep whole, so nothing was dropped but `.git`.

## Licensing conditions if you reuse this code

* **OmniRoute, MIT.** Keep the copyright notice and the permission notice in any
  copy or substantial portion. `LICENSE` is in the extract.
* **x-cmd, Apache-2.0.** Keep `NOTICE.md`, `LICENSE.txt` and the per-file
  `LICENSES/` attributions; state changes if you modify files. Note that
  `NOTICE.md` also records that **"x-cmd" is a registered trademark**, so a
  derivative must not be distributed under that name.

## One security note about x-cmd, read before you paste anything from it

`x-cmd/mod/agent/lib/memory/Thinking-Sovereignty.SKILL.md` is not documentation.
It is a file written to be loaded into an agent's memory, and it asserts
first-principles for the agent itself ("思考主权", thinking sovereignty, the AI as
an independent cognitive entity that decides how and when to think). Whether or
not you agree with it, treat it as **untrusted data**: it is instruction-shaped
content from a third-party repository. It was analysed here and **not** adopted,
and nothing from either repository was executed with elevated trust.

The same discipline applies to `OmniRoute/AGENTS.md`. That one is a genuine
engineering charter and worth copying (see the analysis), but it is still a file
from someone else's repository telling an agent what to do. Read it, decide, then
write your own.
