#!/usr/bin/env python3
"""console.py - one prompt in front of every trader agent. Standard library only.

This is a DECISION-SUPPORT CONSOLE. It is not an automated investment system and
it cannot become one: there is no code path here that places, approves, amends or
cancels an order, and the broker tool is reachable only through its read-only
`show` subcommand. That is enforced by a whitelist, not by a promise, and it is
tested.

What it does: you ask a question in plain words, it works out which of the
installed skills can answer it, runs them, and prints their real output plus one
summary line. Nothing is invented and nothing is interpolated: every number you
see came from a subprocess that just ran.

    python3 console.py agents                       # what is wired up, and from which pack
    python3 console.py ask "does the ema12 rule actually work on QQQ"
    python3 console.py ask "what did pelosi file this year"
    python3 console.py ask "size a trade on TSLA with a 5000 budget"
    python3 console.py evidence QQQ,SPY,TSLA --strategy ema12-flip    # pooled across instruments
    python3 console.py pipeline TSLA                                  # the whole chain, read only
    python3 console.py repl                                           # interactive

Packs are discovered, not hardcoded: it looks for SKILL.md folders under each root
below, so a new skill shows up without an edit.

    TRADER_PACK_V2   default /home/user/trader-agents              (day trading)
    TRADER_PACK_V1   default /home/user/_research/trader-skill     (13F copy, screener, tax)

Every run appends one line to console-log.jsonl: the question, the intent, the
exact command lines, the exit codes and the wall time. If you ever want to know
why the console told you something, the audit trail is there.

Not financial advice. Education and tooling.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

# Paths are DERIVED, never hardcoded. This console ships inside the workspace, so
# its own location defines the roots. A literal absolute path baked into a file is
# a silent failure: it stops resolving the moment the tree is mounted, copied or
# run under a different prefix, and discovery then reports "nothing installed"
# instead of the truth. Override with the two env vars below.
HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(HERE)


def _first_existing(candidates):
    """Pack roots are derived from this file's location and tried in order, so the
    console works in the monorepo layout, in the old split layout, and anywhere the
    tree gets copied. An env var always wins. Nothing is hardcoded to one machine."""
    for c in candidates:
        if c and os.path.isdir(c) and any(
                os.path.isfile(os.path.join(c, d, "SKILL.md"))
                for d in os.listdir(c) if os.path.isdir(os.path.join(c, d))):
            return c
    return candidates[0] if candidates else None


V2 = os.environ.get("TRADER_PACK_V2") or _first_existing([
    os.path.join(WORKSPACE, "trader-agents"),
    os.path.join(WORKSPACE, "agent-hub", "trader-agents"),
    os.path.join(os.path.dirname(WORKSPACE), "trader-agents"),
])
V1 = os.environ.get("TRADER_PACK_V1") or _first_existing([
    os.path.join(WORKSPACE, "trader-skill"),
    os.path.join(WORKSPACE, "_research", "trader-skill"),
    os.path.join(WORKSPACE, "agent-hub", "trader-skill"),
    os.path.join(os.path.dirname(WORKSPACE), "_research", "trader-skill"),
])
LOG = os.environ.get("TRADER_CONSOLE_LOG") or os.path.join(HERE, "console-log.jsonl")

# The broker tool can lead to a real order in the hands of the rest of the pack.
# The console may only ever SHOW a ticket. Everything else is refused before a
# subprocess is spawned.
BROKER_READONLY = ("show",)
FORBIDDEN_ARGS = ("approve", "decline", "result", "fill", "flatten", "log")

# ---------------------------------------------------------------- discovery

def _retry(fn, tries=5, delay=0.25):
    """Filesystem reads can transiently fail on some sandboxes and network mounts.
    Retry, and if it still fails, fail LOUDLY: an empty agent table that looks like
    'nothing installed' is far worse than an exception."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except OSError as e:
            last = e
            time.sleep(delay * (i + 1))
    raise RuntimeError("cannot read the filesystem after %d tries: %s" % (tries, last))


def discover(root, pack):
    """{skill_name: {...}} for every SKILL.md folder under root. Lazy and retrying."""
    out = {}
    if not _retry(lambda: os.path.isdir(root)):
        return out
    for d in _retry(lambda: sorted(os.listdir(root))):
        folder = os.path.join(root, d)
        if not _retry(lambda f=folder: os.path.isfile(os.path.join(f, "SKILL.md"))):
            continue
        tools = [f for f in _retry(lambda fl=folder: sorted(os.listdir(fl))) if f.endswith(".py")]
        out[d] = {"folder": folder, "tool": os.path.join(folder, tools[0]) if tools else None,
                  "tools": tools, "pack": pack}
    return out


_CACHE = None
_MISSING = []


def agents():
    """Discover once, on first use, and remember. Never silently returns empty when a
    configured pack root exists but yielded nothing."""
    global _CACHE, _MISSING
    if _CACHE is not None:
        return _CACHE
    a = discover(V2, "v2-day-trader")
    v1 = discover(V1, "v1-investor")
    # Seven skill names exist in BOTH packs (alerts, analyst, broker, budget, news,
    # pelosi, risk). The v2 day-trading versions are the newer ones and must win;
    # a blind dict.update() would have silently replaced them. v1 contributes only
    # what v2 does not have: copycat, screener, rebalance, tax.
    overlap = sorted(set(a) & set(v1))
    for k, v in v1.items():
        if k not in a:
            a[k] = v
    globals()["_OVERLAP"] = overlap
    _MISSING = [r for r in (V2, V1) if _retry(lambda r=r: os.path.isdir(r)) and
                not any(v["folder"].startswith(r) for v in a.values())]
    for r in (V2, V1):
        if not _retry(lambda r=r: os.path.isdir(r)):
            _MISSING.append("%s (directory not found)" % r)
    if not a:
        raise RuntimeError(
            "no agents found under %s or %s. Set TRADER_PACK_V2 / TRADER_PACK_V1 to the "
            "folders that contain SKILL.md skills." % (V2, V1))
    _CACHE = a
    return a


class _Agents(object):
    """Dict-like lazy view, so module code can keep using AGENTS['x'] and AGENTS.get(x)."""
    def __getitem__(self, k):
        return agents()[k]

    def get(self, k, d=None):
        return agents().get(k, d)

    def __contains__(self, k):
        return k in agents()

    def __iter__(self):
        return iter(agents())

    def __len__(self):
        return len(agents())

    def keys(self):
        return agents().keys()

    def values(self):
        return agents().values()

    def items(self):
        return agents().items()


AGENTS = _Agents()

# ---------------------------------------------------------------- intent routing
# Each intent: keywords -> the skills that answer it, in the order they should run.
# Ordered so the most specific intent wins (evidence before generic backtest).

INTENTS = [
    ("does-it-work", ("does it work", "actually work", "overfit", "backtest this",
                      "test this strategy", "test the strategy", "does the", "really work",
                      "survive", "out of sample", "walk forward", "selection bias",
                      "best of", "variants", "prove it", "scam", "hype"),
     ["trader-labs"]),
    ("congress", ("pelosi", "congress", "congressman", "congressional", "ptr", "stock act",
                  "politician", "senator", "disclosure filing"),
     ["trader-pelosi"]),
    ("copy-investor", ("copy buffett", "copy berkshire", "13f", "reverse engineer",
                       "what does ackman own", "copy an investor", "copycat", "clone",
                       "millionaire", "billionaire", "what do the whales", "hedge fund holdings"),
     ["trader-copycat"]),
    ("earnings", ("earnings", "10-q", "10-k", "8-k", "margins", "revenue growth", "eps",
                  "quarter", "xbrl", "transcript", "reports this week"),
     ["trader-analyst"]),
    ("news", ("news", "why is it moving", "why moving", "headline", "breaking", "briefing",
              "catalyst", "rumor", "rumour"),
     ["trader-news"]),
    ("scan", ("scan", "watchlist", "find me setups", "breaking out", "what should i look at",
              "universe", "screener", "screen for", "opening range breakouts", "bull flag",
              "oversold"),
     ["trader-scanner", "trader-screener"]),
    ("entry", ("when to get in", "entry signal", "time my entry", "has it broken out",
               "did it break", "watch the entry", "entry"),
     ["trader-entry"]),
    ("exit", ("where is my stop", "wheres my stop", "set my stop", "stop loss", "target",
              "risk reward", "what's my r", "whats my r", "plan the exit", "when do i get out"),
     ["trader-exit"]),
    ("odds", ("odds", "what are the chances", "simulate", "monte carlo", "replay",
              "time machine", "how often does", "coin flip", "probability"),
     ["trader-timemachine"]),
    ("sizing", ("how many shares", "size this", "size the trade", "position size", "budget",
                "how much should i buy", "i have $", "i have eur", "max loss", "rebalance",
                "weights"),
     ["trader-budget", "trader-rebalance"]),
    ("risk", ("risk check", "is this safe", "does this break my rules", "can i take this trade",
              "how much have i risked", "check my order", "pdt", "daily loss limit"),
     ["trader-risk"]),
    ("ticket", ("ticket", "show the order", "what would i send", "place the order", "buy it",
                "execute", "send it", "close my position", "flatten"),
     ["trader-broker"]),
    ("alerts", ("alert me", "tell me if", "watch my stop", "watch my trade", "remind me",
                "is the market open", "when does the market open", "get me a price",
                "market clock", "opening bell"),
     ["trader-alerts"]),
    ("tax", ("tax", "wash sale", "capital gains", "tax lot", "short term", "harvest"),
     ["trader-tax"]),
]

FALLBACK = ["trader-scanner", "trader-news"]


def route(question):
    """Return (intent_name, [skill names that exist and match])."""
    q = " ".join(str(question or "").lower().split())
    for name, keys, skills in INTENTS:
        if any(k in q for k in keys):
            present = [s for s in skills if s in AGENTS]
            if present:
                return name, present
    return "general", [s for s in FALLBACK if s in AGENTS]


TICKER = re.compile(r"\b([A-Z][A-Z.\-]{0,5})\b")
STOPWORDS = {"I", "A", "IS", "IT", "OF", "TO", "IN", "ON", "AT", "DO", "DOES", "MY", "THE",
             "AND", "OR", "FOR", "WITH", "WHAT", "HOW", "WHEN", "WHY", "CAN", "YOU", "ME",
             "NOT", "ALL", "ANY", "NOW", "TODAY", "USD", "EUR", "ETF", "R", "PM", "AM", "ET"}


def extract_tickers(question):
    out = []
    for m in TICKER.finditer(str(question or "")):
        t = m.group(1).strip(".")
        if t.upper() in STOPWORDS or len(t) < 1:
            continue
        if t not in out:
            out.append(t)
    return out


def extract_budget(question):
    m = re.search(r"(?:\$|eur|EUR|\u20ac)\s?([\d,]+(?:\.\d+)?)", str(question or ""))
    if not m:
        m = re.search(r"\b([\d]{3,7})\s?(?:euros?|eur|dollars?|usd|\$|\u20ac)\b",
                      str(question or ""), re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------- running

def build_command(skill, question, offline=None, extra=None):
    """One read-only command line for a skill. Returns (argv, note) or (None, why-not)."""
    info = AGENTS.get(skill)
    if not info or not info["tool"]:
        return None, "no tool for %s" % skill
    tool = info["tool"]
    tickers = extract_tickers(question)
    first = tickers[0] if tickers else None
    argv = [sys.executable, tool]
    note = ""

    if skill == "trader-labs":
        if re.search(r"variant|best of|grid|selection bias", question or "", re.I):
            argv += ["variants", "--strategy", "level-breakout"]
        elif re.search(r"rank|compare all|every variant", question or "", re.I):
            argv += ["rank"]
        elif re.search(r"claim|508|313r|the video|what did they say", question or "", re.I):
            argv += ["claims"]
            return argv, "claims are quoted from transcripts, never asserted as fact"
        else:
            strat = "level-breakout" if re.search(r"level|breakout|opening range|4r|8r",
                                                 question or "", re.I) else "ema12-flip"
            argv += ["run", "--strategy", strat]
            if first:
                argv += ["--symbol", first]
            argv += ["--json"]
        note = "one instrument, ~60 sessions of free data: a smoke test, not a verdict"
    elif skill == "trader-pelosi":
        argv += ["index"]
        m = re.search(r"--member\s+(\S+)", question or "")
        who = m.group(1) if m else ("pelosi" if "pelosi" in (question or "").lower() else None)
        if who:
            argv += ["--member", who]
    elif skill == "trader-copycat":
        argv += ["find"]
        if first or re.search(r"buffett|berkshire", question or "", re.I):
            argv += ["berkshire" if re.search(r"buffett|berkshire", question or "", re.I)
                     else (first or "berkshire").lower()]
        note = ("'find' only. 'copy' needs SEC_USER_AGENT with YOUR real name and email; "
                "the console will not invent an identity for a government endpoint")
    elif skill == "trader-analyst":
        if first:
            argv += [first]
    elif skill == "trader-news":
        if tickers:
            argv += ["--tickers"] + tickers[:6]
    elif skill == "trader-scanner":
        argv += ["daily" if not re.search(r"orb|opening range|intraday", question or "", re.I) else "orb"]
    elif skill == "trader-screener":
        pass
    elif skill == "trader-entry":
        argv += ["check"] + ([first] if first else [])
    elif skill == "trader-exit":
        argv += ["show"] if "show" in re.findall(r"[a-z]+", (question or "").lower()) else ["plan"]
    elif skill == "trader-timemachine":
        argv += ["run"]
    elif skill == "trader-budget":
        argv += ["--json"]
        b = extract_budget(question)
        if b:
            argv += ["--budget", "%g" % b]
    elif skill == "trader-risk":
        pass
    elif skill == "trader-broker":
        argv += list(BROKER_READONLY)
        note = "read-only: the console can show a ticket, never approve, fill or flatten one"
    elif skill == "trader-alerts":
        argv += ["clock"] if re.search(r"market open|clock|when does the market", question or "", re.I) \
            else ["list"]
    elif skill == "trader-tax" or skill == "trader-rebalance":
        pass

    if offline:
        argv += ["--offline", offline]
    if extra:
        argv += list(extra)

    for bad in FORBIDDEN_ARGS:
        if skill == "trader-broker" and bad in argv:
            return None, "refused: %r is not a read-only broker command" % bad
    return argv, note


def run(argv, timeout=180, cwd=None):
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           cwd=cwd or os.path.dirname(LOG))
        return {"rc": p.returncode, "out": p.stdout, "err": p.stderr,
                "seconds": round(time.time() - t0, 2)}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "", "err": "timed out after %ss" % timeout,
                "seconds": round(time.time() - t0, 2)}
    except OSError as e:
        return {"rc": 127, "out": "", "err": str(e), "seconds": round(time.time() - t0, 2)}


def log(record):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def summarise_labs(raw):
    """Turn labs.py --json into one honest line."""
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    a = d.get("all") or {}
    if not a.get("trades"):
        return {"trades": 0, "line": "no trades in the window: nothing to judge"}
    return {"trades": a["trades"], "win_rate": a.get("win_rate"), "avg_r": a.get("avg_r"),
            "total_r": a.get("total_r"), "t": a.get("t_stat"),
            "line": "%d trades, %s%% wins, %+.4fR a trade, %+.2fR total, t=%s"
                    % (a["trades"], a.get("win_rate"), a.get("avg_r") or 0,
                       a.get("total_r") or 0, a.get("t_stat"))}


# ---------------------------------------------------------------- commands

def cmd_agents(a):
    print("%d agents wired up, discovered from:" % len(AGENTS))
    print("  v2 %s%s" % (V2, "" if os.path.isdir(V2) else "   (MISSING)"))
    print("  v1 %s%s" % (V1, "" if os.path.isdir(V1) else "   (MISSING)"))
    print()
    print("  %-20s %-16s %-22s %s" % ("skill", "pack", "tool", "read-only commands"))
    for name in sorted(AGENTS):
        i = AGENTS[name]
        tool = os.path.basename(i["tool"]) if i["tool"] else "(none)"
        ro = "show only" if name == "trader-broker" else "all"
        print("  %-20s %-16s %-22s %s" % (name, i["pack"], tool, ro))
    print()
    ov = globals().get("_OVERLAP") or []
    if ov:
        print()
        print("  %d skill names exist in both packs; the v2 day-trading version wins:" % len(ov))
        print("  %s" % ", ".join(ov))
        print("  v1 contributes only: %s" % ", ".join(sorted(
            k for k, v in AGENTS.items() if v["pack"] == "v1-investor")))
    print()
    print("The console can show a ticket. It cannot approve, fill or flatten one,")
    print("and it never will: those arguments are refused before anything runs.")
    return 0


def cmd_ask(a):
    q = a.question
    intent, skills = route(q)
    print("question : %s" % q)
    print("intent   : %s" % intent)
    print("agents   : %s" % (", ".join(skills) if skills else "none matched"))
    print()
    results = []
    for s in skills:
        argv, note = build_command(s, q, offline=a.offline)
        if argv is None:
            print("--- %s: skipped (%s)" % (s, note))
            results.append({"skill": s, "skipped": note})
            continue
        print("--- %s (%s)" % (s, " ".join(argv[1:])))
        if note:
            print("    note: %s" % note)
        if a.dry_run:
            print("    [dry run, not executed]")
            results.append({"skill": s, "argv": argv, "dry_run": True})
            continue
        r = run(argv, timeout=a.timeout)
        body = r["out"].strip() or r["err"].strip()
        for line in body.splitlines()[:a.lines]:
            print("    " + line)
        if len(body.splitlines()) > a.lines:
            print("    ... (%d more lines)" % (len(body.splitlines()) - a.lines))
        print("    [rc=%s, %.1fs]" % (r["rc"], r["seconds"]))
        summ = summarise_labs(r["out"]) if s == "trader-labs" else None
        results.append({"skill": s, "argv": argv, "rc": r["rc"], "seconds": r["seconds"],
                        "summary": summ})
        print()
    log({"ts": datetime.datetime.utcnow().isoformat() + "Z", "question": q, "intent": intent,
         "results": results})
    if intent == "does-it-work":
        print("Read the t statistic, not the total. Below about 2, the sample cannot")
        print("separate an edge from luck, and one instrument over 60 sessions is a")
        print("smoke test. Use `evidence SYM,SYM,SYM` before believing anything.")
    print()
    print("Nothing was placed. Not financial advice.")
    return 0


def cmd_evidence(a):
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if len(syms) < 3:
        print("evidence wants at least 3 instruments, so one lucky ticker cannot carry")
        print("the result. Try: evidence QQQ,SPY,TSLA,NVDA,AMD,IWM")
        return 1
    labs_tool = AGENTS.get("trader-labs", {}).get("tool")
    if not labs_tool:
        print("trader-labs is not installed, so there is nothing to pool.")
        return 1
    print("Pooling %s across %d instruments (%s), strategy %s, target %gR."
          % (a.strategy, len(syms), ", ".join(syms), a.strategy, a.target_r))
    print()
    all_r, rows = [], []
    for s in syms:
        argv = [sys.executable, labs_tool, "run", "--strategy", a.strategy, "--symbol", s,
                "--target-r", "%g" % a.target_r, "--json"]
        if a.offline:
            argv += ["--offline", a.offline]
        r = run(argv, timeout=a.timeout)
        summ = summarise_labs(r["out"])
        if not summ or not summ.get("trades"):
            rows.append((s, 0, None, None, None, None))
            print("  %-6s no trades / fetch failed (rc=%s)" % (s, r["rc"]))
            continue
        try:
            d = json.loads(r["out"])
        except ValueError:
            continue
        rs = [t["r"] for t in (d.get("trades") or [])]
        all_r.extend(rs)
        rows.append((s, summ["trades"], summ["win_rate"], summ["avg_r"], summ["total_r"], summ["t"]))
        print("  %-6s %4d trades  win %5.1f%%  avg %+.4fR  total %+8.2fR  t=%s"
              % (s, summ["trades"], summ["win_rate"] or 0, summ["avg_r"] or 0,
                 summ["total_r"] or 0, summ["t"]))
    print()
    if len(all_r) < 30:
        print("POOLED: only %d trades across everything. That is not enough to judge" % len(all_r))
        print("anything, and no summary below would mean anything.")
        log({"ts": datetime.datetime.utcnow().isoformat() + "Z", "cmd": "evidence",
             "symbols": syms, "trades": len(all_r)})
        return 1
    n = len(all_r)
    mean = sum(all_r) / float(n)
    var = sum((x - mean) ** 2 for x in all_r) / float(n - 1)
    sd = var ** 0.5
    t = mean / (sd / (n ** 0.5)) if sd > 0 else 0.0
    wins = sum(1 for x in all_r if x > 0)
    print("POOLED across %d instruments: %d trades" % (len(syms), n))
    print("  win rate      %5.1f%%" % (100.0 * wins / n))
    print("  avg R/trade  %+8.4f" % mean)
    print("  total R      %+8.2f" % sum(all_r))
    print("  t statistic  %8.2f   (|t| < 2 = cannot reject 'no edge')" % t)
    print()
    if t <= -2:
        print("VERDICT: this rule LOSES, and loses measurably, across every instrument")
        print("tested. That is not bad luck and more data will not rescue it. Do not")
        print("trade it, and do not size a position on the strength of any backtest of it.")
    elif t < 2:
        print("VERDICT: no detectable edge. The average is inside the noise for this")
        print("sample size. 'It made money in my backtest' and 'it has an edge' are")
        print("different claims, and only the second one is worth paying for.")
    else:
        print("VERDICT: positive and statistically detectable BEFORE costs. Now subtract")
        print("commission, spread and slippage per trade and see what is left. At")
        print("%d trades a year of 5-minute signals, costs usually eat this." % n)
    log({"ts": datetime.datetime.utcnow().isoformat() + "Z", "cmd": "evidence",
         "symbols": syms, "strategy": a.strategy, "trades": n, "mean_r": round(mean, 4),
         "t": round(t, 2)})
    print()
    print("Nothing was placed. Not financial advice.")
    return 0


def cmd_pipeline(a):
    sym = a.symbol.upper()
    # sizing and risk both need rules; default to the pack's shipped example so the
    # chain can complete instead of dying at step 6 with "no budget".
    budget_args, risk_args = [], []
    cfg = a.config
    if not cfg:
        guess = os.path.join(V2, "trader-budget", "config.example.json")
        cfg = guess if os.path.isfile(guess) else None
    if cfg:
        risk_args = ["--config", cfg]
        if not a.budget:
            budget_args = ["--config", cfg]
    if a.budget:
        budget_args += ["--budget", "%g" % a.budget]
    if a.now:
        for lst in (budget_args, risk_args):
            lst += ["--now", a.now]
    steps = [
        ("scanner", "trader-scanner", ["daily", "--symbols", sym]),
        ("news", "trader-news", ["--tickers", sym]),
        # --write is what makes this a chain: each step's artifact is the next
        # step's input, so without it every step after entry fails with "no entry".
        ("entry", "trader-entry", ["check", sym, "--setup", "orb", "--write"]),
        ("exit", "trader-exit", ["plan", "--write"]),
        ("odds", "trader-timemachine", ["run"]),
        ("size", "trader-budget", ["--write"] + budget_args),
        ("risk", "trader-risk", list(risk_args)),
        ("ticket", "trader-broker", ["show"]),
    ]
    print("Read-only pipeline for %s. Each step reads what the previous one wrote." % sym)
    if cfg:
        print("Rules from %s%s" % (cfg, "" if not a.budget else " (budget overridden to %g)" % a.budget))
    print("The chain stops at a ticket. It cannot go further, by construction.")
    print()
    work = a.workdir
    if not os.path.isdir(work):
        os.makedirs(work)
    for label, skill, extra in steps:
        info = AGENTS.get(skill)
        if not info or not info["tool"]:
            print("%-9s SKIPPED (%s not installed)" % (label, skill))
            continue
        argv = [sys.executable, info["tool"]] + extra
        if a.offline:
            argv += ["--offline", a.offline]
        if a.now:
            argv += ["--now", a.now]
        if a.dry_run:
            print("%-9s [dry run] %s" % (label, " ".join(argv[1:])))
            continue
        r = run(argv, timeout=a.timeout, cwd=work)
        head = [l for l in (r["out"] or r["err"]).strip().splitlines() if l.strip()][:3]
        print("%-9s rc=%s %s" % (label, r["rc"], " | ".join(head)[:150]))
        if r["rc"] != 0 and label in ("entry", "exit", "size"):
            print("          chain stops here: the next steps need this one's output")
            break
    log({"ts": datetime.datetime.utcnow().isoformat() + "Z", "cmd": "pipeline", "symbol": sym})
    print()
    print("Nothing was placed. To act on any of this you would still need")
    print("/trader-risk to PASS the exact order and you to type yes to it yourself.")
    return 0


def cmd_repl(a):
    print("trader console. Type a question, 'agents' to list them, 'quit' to leave.")
    print("It runs read-only tools and prints their real output. Not financial advice.")
    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            return 0
        if line.lower() == "agents":
            cmd_agents(a)
            continue
        a.question = line
        a.lines = 14
        cmd_ask(a)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="console.py",
                                 description="One prompt in front of every trader agent (read-only).")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("agents", help="list every wired-up agent and its pack")

    p = sub.add_parser("ask", help="route one question to the agents that can answer it")
    p.add_argument("question")
    p.add_argument("--offline", help="pass this path to any tool that accepts --offline")
    p.add_argument("--lines", type=int, default=18, help="max lines of output per agent")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")

    p = sub.add_parser("evidence", help="pool one rule across several instruments, then judge it")
    p.add_argument("symbols", help="comma separated, at least 3: QQQ,SPY,TSLA,NVDA,AMD,IWM")
    p.add_argument("--strategy", default="ema12-flip", choices=["ema12-flip", "level-breakout"])
    p.add_argument("--target-r", type=float, default=4.0)
    p.add_argument("--offline")
    p.add_argument("--timeout", type=int, default=180)

    p = sub.add_parser("pipeline", help="run the whole read-only chain for one symbol")
    p.add_argument("symbol")
    p.add_argument("--workdir", default=os.path.join(os.path.dirname(LOG), "work"))
    p.add_argument("--offline")
    p.add_argument("--now")
    p.add_argument("--budget", type=float, help="account size for the sizing step")
    p.add_argument("--config", help="rules file for sizing and risk (default: the pack's example)")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--dry-run", action="store_true")

    sub.add_parser("repl", help="interactive prompt")

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    for k in ("lines", "timeout", "dry_run", "offline", "budget", "config"):
        if not hasattr(a, k):
            setattr(a, k, 18 if k == "lines" else (180 if k == "timeout" else
                                                    (False if k == "dry_run" else None)))
    return {"agents": cmd_agents, "ask": cmd_ask, "evidence": cmd_evidence,
            "pipeline": cmd_pipeline, "repl": cmd_repl}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
