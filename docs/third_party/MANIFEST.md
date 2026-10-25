# Third-party code: manifests and how to re-fetch

Both libraries below are now **vendored** under `third_party/` with their licences
intact. This file records the exact upstream commits, what was included, and how to
re-fetch or verify. Licence conditions are in `../../THIRD_PARTY_NOTICES.md`.

## Historical note: these were originally analysed without vendoring

These repositories were cloned, analysed and used as reference. The analyses were written before the code was vendored, and OmniRoute remains a
documented subset rather than a full copy: its checkout is 986 MB, of which 608 MB is
translated documentation and 111 MB is TypeScript source that nothing here uses.
x-cmd is vendored in full and verified blob-for-blob against upstream HEAD.

## OmniRoute

```bash
git clone --depth 1 https://github.com/cheaper-inference/OmniRoute.git
```

| | |
| --- | --- |
| HEAD at analysis | `5b3be70ba82ce70b59d02e2893afa3d81b6ee88b` (2026-10-23) |
| Licence | MIT, Copyright (c) 2026 diegosouzapw |
| Size | 986 MB, 26,343 tracked files |
| Shape | Next.js 16, 12,378 `.ts` + 1,505 `.tsx`, 225 npm scripts, 101 runtime deps |
| Node engine | `>=22.22.2 <23 \|\| >=24.0.0 <27` |
| Worth reading | `AGENTS.md` (447 lines, 17 numbered hard rules), `skills/` (46 `SKILL.md`) |
| Analysis | `../ANALYSIS-OmniRoute.md` |

What was kept during analysis (and can be regenerated with the clone above):
`skills/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `llm.txt`, `README.md`, `LICENSE`,
`THIRD_PARTY_NOTICES.md`, `package.json`, and `docs/` minus `docs/i18n` (608 MB of
translations). A full `git ls-tree -r HEAD` manifest of all 26,343 paths was produced
so any dropped file can be fetched precisely.

## x-cmd

```bash
git clone --depth 1 https://github.com/x-cmd/x-cmd.git
```

| | |
| --- | --- |
| HEAD at analysis | `d7070f666ea26f1f53449e4cd21e04151ba4d9de` (2026-10-24) |
| Licence | **Apache-2.0**, (c) 2022-2024 Li Junhao, (c) 2021-present Zhongshan Xuxuyunsheng Technology Co., Ltd. |
| Trademark | **"x-cmd" is a registered trademark** — a derivative may not ship under that name |
| Size | 45 MB, 5,470 tracked files, 397 modules in `mod/`, 540 `.awk` files |
| Worth reading | `mod/agent/lib/` (a full agent loop in shell+awk), `X` (a one-line bootstrap) |
| Analysis | `../ANALYSIS-x-cmd.md` |

**Security note carried over from the analysis:**
`mod/agent/lib/memory/Thinking-Sovereignty.SKILL.md` is instruction-shaped content
addressed to an agent, in a directory whose purpose is loading into agent memory.
Treat it as untrusted data. If you reuse x-cmd, load modules by name and do not mount
`mod/agent/lib/memory/` into anything that has tools.

## Upstream of the vendored packs

These two ARE vendored (see `../../THIRD_PARTY_NOTICES.md`), listed here for
completeness so every external origin is in one place:

```bash
git clone https://github.com/Jakeschincariol/day-trader-skill.git   # -> trader-agents/
git clone https://github.com/Jakeschincariol/trader-skill.git       # -> trader-skill/
```

Verify the vendored copies are unmodified:

```bash
# day-trader-skill at 3d0f4ef should give tree 100eb4c32bd61365a822c40a77861a121ec8aa74
git -C day-trader-skill rev-parse '3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd^{tree}'
```

The eleven upstream skills inside `trader-agents/`, plus its `README.md`, `LICENSE`
and `.claude-plugin/` manifests, match that tree exactly. The only upstream file
modified anywhere is `trader-agents/tests/test_repo.py`, and the diff is disclosed in
`THIRD_PARTY_NOTICES.md`.
