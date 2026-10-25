# agent-hub

Every agent, tool and research artifact built or verified in this project, in one
repository. Standard-library Python, no runtime dependencies, no API keys required.

```
agent-hub/
├── trader-agents/     12 Claude skills for day trading (v2 pack + trader-labs)
├── trader-skill/      11 Claude skills for investing (v1 pack: 13F copy, screener, tax)
├── trader-console/    one prompt in front of all 16 of them
├── obsidian-datafarm/ vault -> knowledge graph, plus the Obsidian connection kit
├── third_party/       vendored reference libraries (x-cmd, OmniRoute), licences intact
├── docs/              the research, the rankings, the setup steps, the connection guide
├── scripts/           run-tests.sh, init-git.sh, push-github.sh, restore-excluded-paths.sh
├── LICENSE            MIT (this repository's own additions)
└── THIRD_PARTY_NOTICES.md   attribution for everything that is not ours
```

## Run everything

```bash
bash scripts/run-tests.sh          # all four suites: 606 tests
bash scripts/init-git.sh           # rebuild the commit (idempotent; see note below)
```

**`docs/SETUP-STEPS.md` has the step-by-step for connecting every external source**
(SEC identity, the House Clerk file, your Obsidian vault, GitHub, a long bar file,
the French micro-entreprise, the PEA, a paper broker, a freelance profile), with who
does what and how to verify each one.

`scripts/init-git.sh` exists because the workspace this was built in does not persist
`.git` directories between sessions while all file content does persist, so history
can vanish while the work stays. It rebuilds a clean, reproducible commit from
content and is safe to run repeatedly.

Individually:

```bash
cd trader-agents     && python3 -m unittest discover -s tests               # 369
cd trader-skill      && python3 -m unittest discover -s tests               # 175
cd trader-console    && python3 -m unittest discover -s . -p test_console.py #  25
cd obsidian-datafarm && python3 -m unittest discover -s tests               #  37
```

## What each part does

### `trader-console` — the entry point

```bash
cd trader-console
python3 console.py agents                                   # 16 agents, which pack, which are read-only
python3 console.py ask "does the ema12 rule actually work on QQQ"
python3 console.py ask "what did pelosi file this year"
python3 console.py ask "copy buffett from his 13f"
python3 console.py ask "how many shares with a $5000 budget on TSLA"
python3 console.py evidence QQQ,SPY,TSLA,NVDA,AMD,IWM --strategy ema12-flip
python3 console.py pipeline TSLA --now "2026-10-19 10:16" --budget 5000
python3 console.py repl
```

It routes a plain-English question to whichever agents can answer it, runs them and
prints their real output. Nothing is invented or interpolated: every number came from
a subprocess that just ran. Every run appends an audit line to `console-log.jsonl`.

**It is decision support, not automated trading.** There is no code path in it that
places, approves, amends or cancels an order. The broker tool is reachable only via
its read-only `show` subcommand; `approve`, `decline`, `result`, `fill`, `flatten` and
`log` are refused before any subprocess starts, and four tests attack that rule.

### `trader-agents` — 12 skills (the v2 day-trading pack)

`trader-scanner`, `trader-news`, `trader-entry`, `trader-exit`, `trader-timemachine`,
`trader-risk`, `trader-budget`, `trader-broker`, `trader-alerts`, `trader-analyst`,
`trader-pelosi`, and **`trader-labs`** (ours).

The first eleven are a **byte-exact replica** of
[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
at commit `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd`, MIT licensed, reproduced with
attribution as that licence requires. Their `README.md`, `LICENSE` and plugin
manifests are unmodified. `trader-labs` is original work added locally, plus the
minimal `tests/test_repo.py` extension needed for a twelfth skill to coexist with the
upstream contract tests.

`trader-labs` backtests a published rule and reports what it actually did: in-sample
vs out-of-sample, R per trade, a t statistic, profit factor, max drawdown, and the
selection bias of picking the best of N variants. Four honesty rules are enforced in
code and pinned by tests: the stop is checked before the target inside every bar; a
trailing stop never uses the bar it protects; entry is the signal bar's close; the
walk-forward split is fixed by date before the run.

### `trader-skill` — 11 skills (the v1 investor pack)

Also a byte-exact replica of
[Jakeschincariol/trader-skill](https://github.com/Jakeschincariol/trader-skill) at
commit `5189e79b9a480755a3733ac9713f5353981dbe18`, MIT, unmodified, 175 tests. This
is where `trader-copycat` (SEC 13F reverse-engineering), `trader-screener`,
`trader-rebalance` and `trader-tax` live. Where a skill name exists in both packs,
the console prefers the v2 day-trading tool.

### `obsidian-datafarm` — the knowledge-graph half

`src/vault_indexer.py` turns a vault of markdown into `graph.json`, `stats.json` and a
self-contained interactive `graph.html` (no CDN, no network): wikilinks, aliases,
heading and block refs, embeds, markdown links, Obsidian's shortest-path link
resolution, nested and frontmatter tags, code-fence stripping, orphan and
duplicate-basename detection, and a Barnes-Hut force-directed layout that took 3,000
notes from **199 s to 13.1 s**. `src/vault_probe.py` is a read-only connection and
secret-scanning diagnostic that prints redacted previews only.

`starter-vault/` is a working vault: PARA folders, a provenance data model
(Source -> Claim -> Entity -> Project), four templates, and an `AGENTS.md` contract
that any future AI session picks up without re-explanation.

`HOW-TO-CONNECT-TO-OBSIDIAN.md` documents the five ways to give an agent access to a
vault, and which of them can and cannot work from a sandboxed chat.

### `docs/` — the research

| file | what it settles |
| --- | --- |
| `ANALYSIS-can-trading-reach-3k.md` | Whether €3k/month from trading is reachable on ~€500. It is not, with the arithmetic |
| `RANKING-quant-labs-strategies.md` | The two published strategies, tested and ranked |
| `ANALYSIS-day-trader-skill.md` | Architecture and safety model of the upstream pack |
| `ANALYSIS-OmniRoute.md` | 46-skill catalog and a 17-rule agent charter worth copying |
| `ANALYSIS-x-cmd.md` | A zero-dependency shell agent loop, and a prompt-injection surface to avoid |
| `CONNECTIONS.md` | Every external source, whether it is reachable, and how to connect it |
| **`SETUP-STEPS.md`** | **Step-by-step for each connection: who does it, the exact commands, and how to verify** |
| `third_party/MANIFEST.md` | Exact clone commands and HEAD SHAs for the libraries analysed but not vendored |

## The headline empirical result

Run on live Yahoo data, 60 sessions per instrument, by `console.py evidence`:

| rule | trades | win % | avg R/trade | total R | pooled t |
| --- | --- | --- | --- | --- | --- |
| EMA-12 flip ("508%, 57% win rate") | 360 | 10.8% | **−0.7858** | **−282.88** | **−24.75** |
| Level breakout 4R ("313R, best of 1,380") | 240 | 26.7% | **−0.0473** | −11.36 | −0.43 |

The first loses on all six instruments. The second replicates the claimed *win rate*
almost exactly while showing no edge at all. That distinction is the reason
`trader-labs` exists.

## Data sources

All free, all public, no keys: Yahoo Finance chart and spark APIs and news RSS, SEC
EDGAR (`data.sec.gov`), Nasdaq Trader SymDir, the House Clerk PTR index. EDGAR asks
you to identify yourself, so set `SEC_USER_AGENT="Your Name you@example.com"`. The
House Clerk endpoint returns 403 to datacentre IPs, so use `--offline` with a file you
downloaded in a browser. Details in `docs/CONNECTIONS.md`.

## Safety posture

* Paper trading by default; `require_stop`, no shorts, no margin, no options.
* A risk verdict is bound to the exact order and the exact day; a stale one is refused.
* Entries are refused when the market is closed. Exits never are.
* Every skill carries an explicit "not financial advice" disclaimer (asserted by test).
* The console cannot reach an order-mutating command; the copycat tool cannot invent
  an identity for a government endpoint.
* No credential, key or secret appears anywhere in this repository (scanned).

## Licensing

This repository's original work (`trader-labs`, `trader-console`,
`obsidian-datafarm`, `docs/`) is MIT, see `LICENSE`.

The two skill packs are third-party MIT code reproduced with attribution, and
`docs/` quotes two academic sources (one CC-BY-4.0). `third_party/` vendors two
reference libraries: **x-cmd** (Apache-2.0, 5,470 files, every git blob SHA verified
against upstream HEAD, plus a registered trademark that forbids derivative naming)
and a documented **subset of OmniRoute** (MIT, 380 files of a 26,343-file project).
Neither is used at runtime. Full details, upstream commits, exactly what was excluded
and why, and the conditions for reuse are in `THIRD_PARTY_NOTICES.md`.

52 x-cmd files live under path segments named `build`/`target`/`out`, which the build
sandbox excludes from its snapshots; they are preserved in
`third_party/x-cmd-excluded-paths.tar.gz` and restored by
`bash scripts/restore-excluded-paths.sh`, which re-verifies the count against the
manifest. A clone from GitHub is complete; the exclusion affects only the sandbox.

Nothing here is investment advice, tax advice or legal advice. Most people who day
trade lose money: in the largest census ever published, 97% of individuals who
persisted more than 300 days lost money, 1.1% earned more than a minimum wage and
0.5% more than a starting bank teller (Chague, De-Losso & Giovannetti, SSRN 3423101).
