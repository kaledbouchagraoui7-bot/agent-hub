# `day-trader-skill` — research, analysis and synthesis

Source: https://github.com/Jakeschincariol/day-trader-skill @ `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd`
("The Trader skill v2: 11 day-trading skills", 2026-10-20). License: **MIT**, © 2026 Jake Schincariol.
Replica: `/home/user/trader-agents` — 107 files, **sha256-identical** to upstream (excluding `.git`).

> This analysis lives *outside* the replica on purpose: `tests/test_repo.py::test_root_matches_the_reel`
> asserts an exact root listing, so adding any file to the repo root breaks its own contract test.

---

## 1. What the "agents" actually are

There is **no `agents/` directory and no Claude Code subagent (`agents/*.md`) file** in this repo.
The eleven "agents" are **Claude Skills**: a folder per agent containing

| part | role |
|---|---|
| `SKILL.md` | the agent itself — YAML frontmatter (`name`, `description`, `argument-hint`) + a prose operating manual |
| `<tool>.py` | a stdlib-only Python CLI the skill drives |
| `*.example.json` | config/state templates |

The frontmatter `description` is the routing surface: each one ends with an explicit
*"Use when the user says …"* trigger list, which is how Claude decides to load the skill.
That is the whole mechanism — no framework, no server, no dependency.

`.claude-plugin/plugin.json` declares `"skills": "./"`, i.e. **the repo root is the skill
directory**; `.claude-plugin/marketplace.json` makes the same repo installable as a plugin
marketplace of one. Installed as a plugin, Claude Code namespaces them
(`/day-trader-skill:trader-scanner`); copied into `~/.claude/skills/` they are plain `/trader-scanner`.

## 2. Inventory (verified by parsing every SKILL.md)

| # | Agent | SKILL.md lines | Tool | Tool lines | argument-hint |
|---|---|---|---|---|---|
| 1 | `trader-scanner` | 203 | `scan.py` | 1083 | `[universe \| daily \| orb] [--at HH:MM]` |
| 2 | `trader-news` | 104 | `news.py` | 546 | `[tickers]` |
| 3 | `trader-entry` | 144 | `entry.py` | 960 | `[TICKER] [--setup orb\|level] [--interval 5m\|1m]` |
| 4 | `trader-exit` | 132 | `exit.py` | 735 | `[--stop or-mid\|or-low\|price:X\|pct:X\|atr:K] [--target 2R\|1R\|price:X]` |
| 5 | `trader-timemachine` | 168 | `timemachine.py` | 956 | `[path to plan.json, or TICKER]` |
| 6 | `trader-risk` | 172 | `check.py` | 819 | `[path to orders.json]` |
| 7 | `trader-budget` | 166 | `size.py` | 881 | `[budget in dollars]` |
| 8 | `trader-broker` | 212 | `ticket.py` | 720 | `[order number]` |
| 9 | `trader-alerts` | 160 | `alerts.py` | 787 | `[ticker] [price]` |
| 10 | `trader-analyst` | 123 | `facts.py` | 548 | `[tickers]` |
| 11 | `trader-pelosi` | 158 | `ptr.py` | 566 | `[member name] [--read]` |

1 742 lines of agent prose, 8 601 lines of Python. Every `name:` matches its folder (asserted).

## 3. Architecture: a file-based pipeline, not a service

The agents communicate **only through JSON files in a `trader/` folder** in the user's project.
No IPC, no database, no shared memory — each tool reads its predecessor's artifact and writes its own.

```
scanner ──watchlist.json──> news ──> entry ──entry.json──> exit ──plan.json──> timemachine
                                                                  │
                                              budget <────────────┘
                                                │ orders.json
                                                v
                                             risk ──state/risk.json──> broker ──(your yes)──> Alpaca MCP
                                                │
   alerts <──plan.json (stop / target / flat-by)┘        analyst, pelosi: standalone, on a schedule
```

Verified artifact chain from a live run: `trader/entry.json → plan.json → orders.json →
state/risk.json → alerts.json`.

**Why this design is good:** every step is inspectable, replayable, testable offline, and
crash-safe; a stale artifact is detectable because each file carries a date/`as_of`.
**Cost:** the coupling is by *convention* (file names and key names), so a schema change in one
tool silently breaks the next. The repo mitigates this with 315 tests that exercise the contracts.

## 4. The safety model (the most interesting part)

Four independent gates, verified by execution:

1. **Nothing places an order.** No tool contains any brokerage call; `ticket.py` only *prints* the
   exact `place_stock_order` JSON. The actual call is made by Claude through Alpaca's MCP server,
   which is behind Claude's own "Allow once / Deny" card. Two human confirmations.
2. **`paper: true`, `require_stop: true`, `allow_short/margin/options: false`** in
   `config.example.json` (asserted by `test_repo.py`).
3. **Risk verdicts are bound to the exact order and the exact day.** Observed live:
   * same-day PASS → ticket prints `READY: trader-risk PASS, waiting for your yes`
   * verdict from another date → `NOT READY: the risk check is from 2026-10-19, not today`
   * order never risk-checked → `NOT READY: this exact order was not in the last risk check`
4. **Market-calendar refusal.** On Saturday 2026-10-24 the risk manager blocked a perfectly-sized
   order: `window: the market is closed today (weekend, Sat 2026-10-24 15:42 New York)`.
   Exits are never blocked by day limits (asymmetric on purpose).

Plus a stale-plan guard in `size.py` (`the plan is for 2026-10-19 and today is 2026-10-24`).
All 11 SKILL.md files carry an explicit "not financial advice" disclaimer (asserted + verified 11/11).

## 5. Data sources and dependency posture

* **Zero third-party packages** — verified by AST-walking all 11 tools: 21 distinct top-level
  imports, **all stdlib**. The README's "nothing to pip install" claim is true.
* Python 3.8 compatible — no `zoneinfo`, `removeprefix`, PEP 585 generics or `match` in the tools
  (verified by token scan outside string literals; upstream asserts the same in `test_repo.py`).
* Free public endpoints: Yahoo Finance chart JSON + RSS, Nasdaq Trader SymDir, SEC EDGAR
  (submissions, XBRL company facts, 8-K), House Clerk PTR index/PDFs, Stooq CSV.
* Only one env var is read anywhere: **`SEC_USER_AGENT`** (SEC requires identification).
  **No hardcoded credentials anywhere** (regex-scanned all `.py/.md/.json/.txt`).
* Every network tool has an `--offline PATH` mode reading saved responses — that is what makes the
  whole suite deterministic and hermetic.

## 6. Verification actually performed on the replica

| check | result |
|---|---|
| `diff -r --exclude=.git` upstream vs replica | **no differences** |
| sha256 of all 107 payload files | **all match** |
| upstream test suite in the replica (`python3 -m unittest discover -s tests`) | **315 passed, 0 failed** (17.1 s) |
| `py_compile` / AST parse, 24 files | clean |
| `--help` on all 11 CLIs | all rc=0 |
| scanner `universe` (offline SymDir) | 36 rows → **17 kept**, correct drop reasons |
| scanner `orb` (offline, 2026-10-19 10:15) | **231 usable charts → 42 confirmed** — matches README exactly |
| entry → exit → timemachine → budget → risk → broker | full chain ran; **every number matches the README's worked example** |
| timemachine, 10 000 replays, seed 19 | target 29.4 % / stop 25.5 % / neither 45.1 %; history 33 fires → 13/15/5 |
| budget | 8 shares, $2 913.44, max loss $46.88 (limit $50 binds) |
| risk | `PASS` on the Monday clock; `BLOCK` on Saturday and on stop-less orders |
| broker | `READY` only with a same-day PASS; `NOT READY` otherwise |
| news / analyst / pelosi (offline) | real headlines; AAPL 6 quarters of XBRL; Pelosi PTR 20035143 parsed to 7 rows |

## 7. Defects and risks I found

**In the replica: none.** Two failures appeared during verification and both were **my harness's
fault**, not the repo's:
1. writing a scratch dir into the repo root broke `test_root_matches_the_reel` → harness now works
   in a `mktemp -d` outside the repo;
2. a Python-3.8 token scan flagged `tests/test_repo.py`, where those tokens exist only as *string
   literals inside the assertions that forbid them* → scan now excludes string literals and applies
   to the 11 shipped tools (which is what the README actually promises).

**Inherited observations about upstream (not changed, since the brief was "copy exactly"):**
* `trader-broker/SKILL.md` and `README.md` hardcode Alpaca's MCP shape; a different broker needs edits.
* Yahoo's chart endpoint is unofficial and can lag or rate-limit — the SKILL.md files say so, and the
  tools label their output "(Yahoo, free, can lag)". Correct handling, but a real operational limit.
* `--offline` accepts a folder *or* a file, and the error text differs by mode; passing a directory
  where a `.zip`/`.json.gz` is expected yields `[Errno 21] Is a directory` rather than a friendly hint.
* Fixtures are date-pinned to October 2026, so the offline suite will need refreshing as data ages.
* The README states FINRA removed the $25 000 PDT minimum on 2026-06-04 (Regulatory Notice 26-10).
  **I did not independently verify that regulatory claim** — treat it as the author's, not mine.

## 8. Reuse value for your own work

Three patterns worth stealing for the Obsidian data farm:
1. **Skill = frontmatter + prose manual + one stdlib CLI.** Portable across Claude Code, plugin
   install, folder copy, or paste-into-chat. Zero runtime dependencies.
2. **File-based handoff with dated artifacts** gives you an auditable pipeline for free — exactly the
   `Source → Claim → Entity → Project` provenance model already drafted in `starter-vault/AGENTS.md`.
3. **A repo-contract test suite** (`test_repo.py`) that asserts structure, disclaimers, safety
   defaults and even prose style. That is what let me prove the replica is faithful in one command.
