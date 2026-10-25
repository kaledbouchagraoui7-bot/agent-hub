# Third-party notices

## 1. `trader-agents/` — the v2 day-trading skill pack

* Upstream: https://github.com/Jakeschincariol/day-trader-skill
* Commit: `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` ("The Trader skill v2: 11 day-trading skills", 2026-10-20)
* Licence: **MIT**, Copyright (c) 2026 Jake Schincariol. Author URL: https://opusjake.ai
* Status: the eleven upstream skills, `README.md`, `LICENSE` and
  `.claude-plugin/{plugin,marketplace}.json` are reproduced **byte-exact**. The
  upstream git tree hash is `100eb4c32bd61365a822c40a77861a121ec8aa74`.
* Changes made here, all disclosed:
  * **Added** `trader-labs/` (SKILL.md + labs.py), original work, MIT under this repo's LICENSE.
  * **Added** `tests/test_labs.py`, `tests/make_labs_fixtures.py`,
    `tests/fixtures/trader-labs/*.json.gz` (synthetic, seeded, reproducible).
  * **Modified** `tests/test_repo.py` only (+22/-4): split `SKILLS` into
    `UPSTREAM_SKILLS` and `LOCAL_SKILLS`, added one assertion that the upstream
    eleven are all still present, and scoped the README assertion to the upstream
    eleven so that `README.md` and `plugin.json` stay byte-identical to upstream.
* MIT condition satisfied: the copyright notice and permission notice are preserved
  in `trader-agents/LICENSE` and in every copy.

## 2. `trader-skill/` — the v1 investor skill pack

* Upstream: https://github.com/Jakeschincariol/trader-skill
* Commit: `5189e79b9a480755a3733ac9713f5353981dbe18` ("The Trader skill: 11 Claude skills, v1.0", 2026-10-14)
* Licence: **MIT**, Jake Schincariol
* Status: reproduced **unmodified**, including its own `LICENSE`. 175 tests pass.

## 3. `trader-console/`, `obsidian-datafarm/`, `docs/` — original

MIT under this repository's `LICENSE`. `obsidian-datafarm` includes no third-party
code; it is stdlib-only Python.

## 4. Research quoted in `docs/`

* Chague, De-Losso & Giovannetti, *"Day Trading for a Living?"*, SSRN 3423101
  (2020). Quoted figures (97% / 1.1% / 0.5%) are from the published abstract.
  SSRN states "No reuse allowed without permission"; we quote short factual
  findings with attribution, which is normal citation, not redistribution.
* Belardi, *"Do a Legislator's Trades Anticipate Legislative Acts?"*, SSRN 7479560
  (2026), **Creative Commons Attribution 4.0**. Findings summarised with attribution.
* French tax and status figures from `economie.gouv.fr`, `autoentrepreneur.urssaf.fr`
  and `entreprendre.service-public.gouv.fr` (public-sector information), and freelance
  rate benchmarks from the public Malt barometer. Figures are dated in `docs/` and
  must be re-verified before use.

## 5. `third_party/` — vendored reference libraries

Both are reproduced **verbatim** and their licences are preserved in place.

### 5a. `third_party/x-cmd/`

* Upstream: https://github.com/x-cmd/x-cmd, HEAD `d7070f666ea26f1f53449e4cd21e04151ba4d9de`
* Licence: **Apache-2.0**, (c) 2022-2024 Li Junhao, (c) 2021-present Zhongshan
  Xuxuyunsheng Technology Co., Ltd. `LICENSE.txt`, `NOTICE.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md` and all five files in `LICENSES/` (psutils, wcwidth.awk,
  zsh-autosuggestions, zsh-config, zsh-syntax-highlighting) are present and unmodified.
* **Trademark: "x-cmd" is a registered trademark** of that company. This copy is
  unmodified and attributed; a derivative must not be distributed under that name.
* Fidelity, verified: **5,470 files, 397 modules**, and every one of the 5,470 git
  blob SHAs matches upstream HEAD (`git hash-object` per path against
  `MANIFEST-upstream-git-ls-tree.txt`). No changes were made, so the Apache-2.0
  "state your changes" obligation is satisfied trivially.
* **Known sandbox artefact:** 52 of those files live under path segments named
  `build`, `target` or `out`, which the workspace this was built in excludes from its
  persisted snapshots. They are preserved in
  `third_party/x-cmd-excluded-paths.tar.gz` (52 files) and restored by
  `bash scripts/restore-excluded-paths.sh`, which re-verifies the file count against
  the manifest. If you clone this repo from GitHub, nothing is missing: the exclusion
  only affects the build sandbox, not git.

### 5b. `third_party/OmniRoute/`

* Upstream: https://github.com/cheaper-inference/OmniRoute, HEAD `5b3be70ba82ce70b59d02e2893afa3d81b6ee88b`
* Licence: **MIT**, Copyright (c) 2026 diegosouzapw. `LICENSE` and
  `THIRD_PARTY_NOTICES.md` are present and unmodified.
* This is a **deliberate subset**, not a verbatim copy of the whole project: 380
  files consisting of `skills/` (46 `SKILL.md`), `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`, `llm.txt`, `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`,
  `package.json`, `CHANGELOG.md`, `ROADMAP.md`, `SECURITY.md`, `CONTRIBUTING.md`,
  `Makefile`, and `docs/` minus `docs/i18n` (608 MB of translations).
* Excluded on purpose: `.git` (142 MB), `docs/i18n` (608 MB), `src/` (111 MB, 3,676
  TypeScript files), `tests/` (66 MB), `open-sse/` (23 MB), `electron/`. The full
  checkout is 986 MB / 26,343 files; clone it with the command in
  `docs/third_party/MANIFEST.md`. Verified against that manifest: **380 of the 380
  intended files present, 0 missing.**
* MIT condition satisfied: the copyright and permission notices are preserved.

### 5c. Why they are here at all

Neither library is used at runtime by anything in this repository. They are vendored
as reference material for the analyses in `docs/ANALYSIS-OmniRoute.md` and
`docs/ANALYSIS-x-cmd.md`: OmniRoute for its 46-skill catalog and its 17-rule
multi-agent charter, x-cmd for a zero-dependency agent loop written in shell and awk.

**Security note, unchanged from the analysis:** `third_party/x-cmd/mod/agent/lib/memory/Thinking-Sovereignty.SKILL.md`
is instruction-shaped content addressed to an agent, in a directory whose purpose is
loading into agent memory. Treat it as untrusted data. Load x-cmd modules by name and
do not mount that path into anything that has tools.

## 6. No credentials

No API key, token, password, certificate or personal identifier appears anywhere in
this repository. The only environment variables read are `SEC_USER_AGENT` (SEC's
identification policy), `TRADER_PACK_V2`, `TRADER_PACK_V1` and `TRADER_CONSOLE_LOG`.
