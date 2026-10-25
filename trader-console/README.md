# trader-console

One prompt in front of every trader agent. Standard library only, Python 3.8+.

This is a **decision-support console**, not an automated trading system. There is no
code path in it that places, approves, amends or cancels an order. The broker tool is
reachable only through its read-only `show` subcommand, enforced by a whitelist that
is checked before any subprocess starts and covered by tests.

## Why it exists

You have 16 agents across two packs and no way to ask them anything without
remembering 16 CLIs. This routes a plain-English question to whichever agents can
answer it, runs them, and prints their real output. Nothing is invented and nothing
is interpolated: every number came from a subprocess that just ran.

```
question -> intent -> agent(s) -> real subprocess output -> one summary line
                                  |
                                  +-> console-log.jsonl  (full audit trail)
```

## Install / run

```bash
cd /home/user/trader-console
python3 console.py agents                 # what is wired up, from which pack
python3 console.py ask "does the ema12 rule actually work on QQQ"
python3 console.py ask "what did pelosi file this year"
python3 console.py ask "copy buffett from his 13f"
python3 console.py ask "how many shares with a $5000 budget on TSLA"
python3 console.py evidence QQQ,SPY,TSLA,NVDA,AMD,IWM --strategy ema12-flip
python3 console.py pipeline TSLA --now "2026-10-19 10:16" --budget 5000
python3 console.py repl                   # interactive
python3 -m unittest discover -s . -p test_console.py    # 24 tests
```

Packs are **discovered**, not hardcoded: any folder containing a `SKILL.md` is wired
up automatically. Roots default to `<workspace>/trader-agents` (v2, day trading) and
`<workspace>/_research/trader-skill` (v1, investor), derived from this file's own
location. Override with `TRADER_PACK_V2` / `TRADER_PACK_V1`.

Where a skill name exists in both packs, **the v2 day-trading tool wins**; v1
contributes only what v2 lacks (`trader-copycat`, `trader-screener`,
`trader-rebalance`, `trader-tax`).

## Commands

| command | what it does |
| --- | --- |
| `agents` | lists all wired agents, their pack, their tool, and which are read-only |
| `ask "..."` | routes one question, runs the matching agents, prints output + intent. `--dry-run` shows commands without running them |
| `evidence SYM,SYM,SYM` | pools one rule across several instruments and judges it on the **pooled t statistic**. Refuses fewer than 3 symbols, so one lucky ticker cannot carry the result |
| `pipeline SYM` | the full read-only chain: scanner -> news -> entry -> exit -> timemachine -> budget -> risk -> broker `show`. Stops at the ticket, by construction |
| `repl` | interactive prompt |

## What `evidence` found, and why it is the most useful command here

Run on live Yahoo data, 60 sessions per instrument:

| rule | instruments | trades | pooled avg R | pooled t | verdict |
| --- | --- | --- | --- | --- | --- |
| `ema12-flip` (the "508%, 57% win rate" rule) | 6 | 360 | **-0.7858** | **-24.75** | loses on every instrument tested |
| `level-breakout` 4R (the "313R, best of 1,380" rule) | 6 | 240 | **-0.0473** | **-0.43** | no detectable edge |

The win rate of the second rule replicated almost exactly (26.7% measured vs "lost
almost three out of four" claimed) while its profitability did not exist. That
distinction is the whole point of the tool: the mechanics of a viral strategy are
usually real, and the edge usually is not.

`evidence` prints `t`, not just the total, and states plainly when the sample cannot
separate an edge from luck. It never prints a guaranteed-return claim of any kind;
there is a test asserting that.

## Safety model

1. **Broker is read-only.** `BROKER_READONLY = ("show",)`; `FORBIDDEN_ARGS` contains
   `approve, decline, result, fill, flatten, log`. A test drives eleven aggressive
   phrasings ("approve my order and fill it", "flatten everything now") and asserts
   none of them can produce a mutating argument.
2. **No identity fabrication.** `trader-copycat copy` needs `SEC_USER_AGENT` with
   *your* real name and email, because the SEC requires identification on every
   request. The console only ever runs `find`, and says so in the output. It will not
   invent a name and email for a government endpoint.
3. **Nothing is silent.** If a configured pack root exists but yields no skills, or
   neither root yields any, discovery raises a `RuntimeError` explaining how to set
   the env vars. An empty agent table that looks like "nothing installed" is worse
   than an exception.
4. **Audit trail.** Every `ask`, `evidence` and `pipeline` appends one JSON line to
   `console-log.jsonl`: timestamp, question, intent, exact argv, exit codes, wall
   time, and for `evidence` the pooled statistics.
5. **No shell.** Every command is an argv list passed to `subprocess.run` with
   `capture_output`; there is no `shell=True` anywhere.
6. **Retry on filesystem reads.** Discovery retries transient `OSError`s, because a
   single failed `isdir` on a network mount should not silently produce an empty
   console.

## Two robustness fixes worth knowing about

**1. Discovery used to run at import time and fail silently.** When the pack roots
were momentarily unreadable, `AGENTS` came back empty and the console printed
"0 agents wired up" as if nothing were installed, which is indistinguishable from a
genuine misconfiguration. Discovery is now lazy, retries transient `OSError`s, and
**raises** if a configured root exists but yields no skills or if neither root yields
any. An empty table that looks like success is worse than an exception.

**2. Paths are derived, never hardcoded.** The roots come from
`WORKSPACE = os.path.dirname(os.path.abspath(__file__))`, not from a literal.

Honest note on the diagnosis: the original failure was **intermittent filesystem
visibility in the sandbox**, not a bad literal. `/home/user` does resolve correctly
(`os.path.realpath` confirms it) and the console now returns 16 agents on 8
consecutive runs from two different working directories. Deriving the paths did not
by itself fix that, and I am not claiming it did. It is still the right hygiene:
it makes the file relocatable, and the loud-failure-plus-retry behaviour above is
what actually handles the flakiness. The regression test
(`test_paths_are_derived_not_hardcoded`) keeps the property either way.

If you copy this file somewhere, keep both properties.

## Tests

24 tests, stdlib `unittest`, all passing: discovery and pack precedence, the
missing-root loud failure, routing for 12 phrasings, ticker/budget extraction,
fallback routing, the broker whitelist (4 separate tests), the copycat identity rule,
dry-run output, evidence refusing <3 symbols, the pipeline writing each artifact and
defaulting to the pack's example rules, audit-log JSONL validity, and a ban on
guaranteed-return language in all output.

## Not financial advice

Education and tooling. It reads public data and does arithmetic. It does not know
your situation and it cannot see the future. Most people who day trade lose money:
in the largest census of retail day traders ever published (Chague, De-Losso &
Giovannetti, SSRN 3423101, all individuals who started in Brazilian equity futures
2013-2015), **97% of those who persisted more than 300 days lost money**, 1.1%
earned more than the minimum wage and 0.5% more than a starting bank teller.
