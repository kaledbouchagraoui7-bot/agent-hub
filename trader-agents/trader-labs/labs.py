#!/usr/bin/env python3
"""Strategy Lab for trader-labs. Standard library only.

Takes a trading rule that someone published online, runs it on your own data,
and reports what it actually did. Three questions, in this order:

  1. Does the rule make money on the data it was tuned on?        (in-sample)
  2. Does it still make money on data it never saw?               (out-of-sample)
  3. How many variants were tried before the winner was picked?   (selection bias)

A rule that passes 1 and fails 2 is not a strategy, it is a description of the
past. A rule picked as the best of 1,380 variants is very likely to fail 2, and
that is arithmetic, not opinion: the best of N noisy results is above the average
by roughly sigma * sqrt(2 * ln(N)) even when every variant is pure noise (3.80 sigma at N = 1,380).

    python3 labs.py run --strategy ema12-flip --symbol QQQ --offline FILE
    python3 labs.py run --strategy level-breakout --symbol QQQ --oos-from 2024-01-01
    python3 labs.py variants --strategy level-breakout --symbol QQQ   # the whole grid
    python3 labs.py rank --symbol QQQ --offline FILE                  # every rule, one table
    python3 labs.py claims                                            # what the videos assert
    python3 labs.py run --strategy ema12-flip --symbol QQQ --json --write

Two rules ship with it, both transcribed from published videos:

  ema12-flip     After the New York open, watch one 5-minute candle. Close above
                 the 12 EMA, go long. Close below it, go flat (and short only if
                 you pass --allow-short). The stop trails the trend: the highest
                 close since the entry minus --atr-k times the 14-bar ATR, and it
                 only ever moves up. Out at your flat-by time whatever happens.
                 The video claims 57 % wins, 508 % over six years, 1,400 trades.

  level-breakout Mark a level before the open (the opening range of the first
                 --or-minutes). After 9:30, the first 5-minute candle that CLOSES
                 through it is the entry. The stop sits behind that candle. The
                 target is --target-r times the risk, 4R by default, so the winner
                 runs instead of being scalped. Out at the close if neither side
                 came first. The video claims 1,750 trades, about one win in four,
                 313R in-sample, +99R out-of-sample, then -107R after that.

Honesty rules this tool will not bend:
  * The stop is checked before the target inside every bar. A bar that touched
    both counts as the stop. That is the conservative call and it costs nothing
    but optimism.
  * The trailing stop that applies during a bar is the one that was already
    ratcheted at the PREVIOUS bar's close. A stop never uses the bar it is
    protecting.
  * Entry is the close of the signal bar, so the rule never buys a price it could
    not have seen.
  * Every trade is measured in R (risk per share at the entry), never in percent
    of account, so results do not depend on a position size you have not chosen.
  * It places nothing. There is no order in this file. If a rule survives and you
    want to trade it, /trader-exit writes the plan, /trader-budget sizes it,
    /trader-risk checks it and /trader-broker asks you yes or no.

Data and its limits: Yahoo's free chart JSON, unofficial, delayed, and it keeps
only about 60 days of 5-minute bars (range=60d&interval=5m is the most intraday
history it gives you). A six-year intraday backtest is therefore NOT possible
from free data: you need a vendor file, and --offline reads one in Yahoo's chart
shape (.json or .json.gz, as many sessions as it holds). Whatever window you
supply, --is-until and --oos-from split it, and the split is printed with the
trade counts on both sides so you can see how thin the evidence is. 60 days of
one ticker is a smoke test, not a verdict.

Not financial advice. Education and tooling. Most people who day trade lose money,
and a backtest that looks strong is the normal starting point of that, not an
exception to it.

Data: https://query2.finance.yahoo.com/v8/finance/chart/<T>?range=60d&interval=5m
"""

import argparse
import datetime
import gzip
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "trader-labs/1.0 (personal research; contact via SEC_USER_AGENT)"
HOSTS = ("query2", "query1")
PAUSE = 1.2
EPOCH = datetime.datetime(1970, 1, 1)
OPEN_MIN = 9 * 60 + 30
CLOSE_MIN = 16 * 60
EARLY_MIN = 13 * 60
EARLY_CLOSE = {
    "2026-11-27", "2026-12-24", "2027-11-26",
}
HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}

# The published assertions this lab can be asked about. Each one carries what it
# would take to check it. Nothing here is stated as fact.
CLAIMS = [
    {
        "id": "ema12-508pct",
        "strategy": "ema12-flip",
        "claim": "508 % total return over six years, more than 1,400 trades, 57 % win rate, now trading live",
        "source": "transcript of a short-form video, channel unnamed in the brief",
        "verifiable_with_free_data": False,
        "why": ("Yahoo gives about 60 days of 5-minute bars, so six years of intraday history "
                "needs a vendor file. A return in percent also needs a position-size rule and a "
                "compounding convention, which the video does not give; R per trade is reportable, "
                "508 % is not, without them."),
        "what_would_check_it": ("a 5-minute bar file for one Nasdaq instrument covering the six years, "
                                "the sizing rule, the commission and slippage assumption, and the "
                                "number of variants tried before this one was picked"),
    },
    {
        "id": "level-313r",
        "strategy": "level-breakout",
        "claim": "1,750 trades, about one win in four, 313R total, best of 1,380 variants",
        "source": "transcript of a short-form video (channel referenced as quant labs)",
        "verifiable_with_free_data": False,
        "why": ("same data limit, and the number that matters is not 313R, it is 1 of 1,380: "
                "picking the best of 1,380 noisy results inflates the in-sample score by roughly "
                "sigma * sqrt(2 * ln(1380)) = 3.80 sigma even if every variant is noise."),
        "what_would_check_it": "the full variant grid with every result, not just the winner",
    },
    {
        "id": "level-oos",
        "strategy": "level-breakout",
        "claim": "+99R on 2024 to 2026 (years it never saw), then -107R on the same rules afterwards",
        "source": "transcript of a short-form video (channel referenced as quant labs)",
        "verifiable_with_free_data": False,
        "why": ("this one is the most useful sentence in either video, and it needs no checking: "
                "the speaker reports that the rule went from +99R out-of-sample to -107R on the "
                "next window. That is the expected behaviour of a rule selected on in-sample score. "
                "It is evidence against the strategy, from its own author."),
        "what_would_check_it": "nothing needed; take it as the author's own out-of-sample result",
    },
]


class LabsError(Exception):
    pass


# ---------------------------------------------------------------- time (house helpers)

def _nth_sunday(year, month, n):
    d = datetime.date(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def eastern_offset(utc):
    """Hours from UTC for New York: -4 in daylight time, -5 otherwise."""
    y = utc.year
    start = datetime.datetime.combine(_nth_sunday(y, 3, 2), datetime.time(7, 0))
    end = datetime.datetime.combine(_nth_sunday(y, 11, 1), datetime.time(6, 0))
    naive = utc.replace(tzinfo=None)
    return -4 if start <= naive < end else -5


def to_eastern(utc):
    return utc.replace(tzinfo=None) + datetime.timedelta(hours=eastern_offset(utc))


def eastern_to_utc(local):
    for off in (-4, -5):
        utc = local - datetime.timedelta(hours=off)
        if eastern_offset(utc) == off:
            return utc
    return local + datetime.timedelta(hours=5)


def utc_of(ts):
    return EPOCH + datetime.timedelta(seconds=int(ts))


def ny_of(ts):
    return to_eastern(utc_of(ts))


def clock24(minutes):
    return "%02d:%02d" % divmod(int(minutes), 60)


def parse_clock(text, what):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(?:([AaPp])\.?\s*[Mm]\.?)?\s*$", str(text or ""))
    if not m:
        raise LabsError("%s wants a New York time like 10:15 AM or 15:55, not %r" % (what, text))
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if mi > 59 or h > 23 or (ap and not 1 <= h <= 12):
        raise LabsError("%s %r is not a clock time" % (what, text))
    if ap == "p" and h != 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    elif not ap and 1 <= h <= 8:
        h += 12
    return h * 60 + mi


def close_minute(day):
    """The regular-session close for a New York date, early closes included."""
    return EARLY_MIN if day.isoformat() in EARLY_CLOSE else CLOSE_MIN


def is_session_day(day):
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS


# ---------------------------------------------------------------- indicators

def ema(values, period):
    """Exponential moving average, seeded with the SMA of the first `period` values.

    Returns a list the same length as `values`, with None until the seed exists.
    ema[0] is None, so a rule can never act on a bar the average has not seen.
    """
    if period < 1:
        raise LabsError("an EMA period must be 1 or more, not %s" % period)
    out = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / float(period)
    out[period - 1] = seed
    k = 2.0 / (period + 1.0)
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1.0 - k)
        out[i] = prev
    return out


def atr(bars, period=14):
    """Wilder's ATR over a list of bars, aligned to the bar index (None until seeded)."""
    if period < 1:
        raise LabsError("an ATR period must be 1 or more, not %s" % period)
    out = [None] * len(bars)
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b["high"] - b["low"])
        else:
            pc = bars[i - 1]["close"]
            trs.append(max(b["high"] - b["low"], abs(b["high"] - pc), abs(b["low"] - pc)))
        if i == period - 1:
            out[i] = sum(trs[:period]) / float(period)
        elif i >= period:
            out[i] = (out[i - 1] * (period - 1) + trs[i]) / float(period)
    return out


def mean(a):
    return sum(a) / float(len(a)) if a else 0.0


def stdev(a):
    if len(a) < 2:
        return 0.0
    m = mean(a)
    return math.sqrt(sum((x - m) ** 2 for x in a) / float(len(a) - 1))


def t_stat(rs):
    """One-sample t on the per-trade R series: how far the average R is from zero
    in units of its own standard error. Below about 2, the sample cannot tell an
    edge from noise."""
    n = len(rs)
    if n < 2:
        return 0.0
    sd = stdev(rs)
    if sd <= 0:
        return 0.0
    return mean(rs) / (sd / math.sqrt(n))


def selection_inflation_sigma(n_variants):
    """Expected height of the best of N independent standard normals.
    sqrt(2 ln N): 1,380 variants -> 3.80 sigma of pure luck."""
    if n_variants <= 1:
        return 0.0
    return math.sqrt(2.0 * math.log(n_variants))


# ---------------------------------------------------------------- data

def chart_url(sym, rng="60d", interval="5m", host="query2"):
    return "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s" % (
        host, urllib.parse.quote(sym.upper().replace(".", "-")), rng, interval)


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_chart(sym, rng="60d", interval="5m"):
    last = None
    for n, host in enumerate(HOSTS):
        if n:
            time.sleep(PAUSE)
        for attempt in (0, 1):
            url = chart_url(sym, rng, interval, host)
            try:
                return _get(url)
            except urllib.error.HTTPError as e:
                last = e.code
                if e.code == 404:
                    raise LabsError("Yahoo has no %s chart at %s interval for %s (HTTP 404)"
                                    % (rng, interval, sym))
                if e.code == 429:
                    raise LabsError("Yahoo rate-limited this machine (HTTP 429). Wait a few minutes, "
                                    "or pass --offline with a saved chart file.")
                if 500 <= e.code < 600 and attempt == 0:
                    time.sleep(PAUSE)
                    continue
                raise LabsError("Yahoo answered HTTP %d for %s" % (e.code, url.split("?")[0]))
            except (urllib.error.URLError, OSError) as e:
                last = e
                if attempt == 0:
                    time.sleep(PAUSE)
                    continue
    raise LabsError("could not reach Yahoo for %s (%s). Pass --offline FILE to work without a network."
                    % (sym, last))


def parse_chart(text, sym=None):
    """Yahoo chart JSON v8 -> {symbol, bars[], where bars carry ts, ny datetime, minute, date}."""
    try:
        data = json.loads(text)
    except ValueError:
        raise LabsError("that is not JSON, so it is not a Yahoo chart file")
    res = ((data.get("chart") or {}).get("result")) or []
    if not res:
        err = (data.get("chart") or {}).get("error") or {}
        raise LabsError("the chart file has no result: %s" % (err.get("description") or err))
    r = res[0]
    meta = r.get("meta") or {}
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0] or {}
    ts = r.get("timestamp") or []
    o, h, l, c, v = (q.get(k) or [] for k in ("open", "high", "low", "close", "volume"))
    got = meta.get("symbol") or sym
    if sym and got and str(got).upper() != str(sym).upper().replace(".", "-"):
        raise LabsError("the chart file holds %s, not %s" % (got, sym))
    bars = []
    for i, t in enumerate(ts):
        try:
            oi, hi, li, ci = float(o[i]), float(h[i]), float(l[i]), float(c[i])
        except (TypeError, ValueError, IndexError):
            continue                      # Yahoo pads holes with nulls; skip them
        if min(oi, hi, li, ci) <= 0:
            continue
        ny = ny_of(t)
        bars.append({
            "ts": int(t), "ny": ny, "date": ny.date(),
            "minute": ny.hour * 60 + ny.minute,
            "open": oi, "high": hi, "low": li, "close": ci,
            "volume": int(v[i]) if i < len(v) and v[i] is not None else 0,
        })
    if not bars:
        raise LabsError("the chart file has no usable bars")
    bars.sort(key=lambda b: b["ts"])
    return {"symbol": str(got or sym or "").upper(), "bars": bars,
            "interval": meta.get("dataGranularity") or "5",
            "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose")}


def load_offline(path, sym=None):
    """A saved chart file (.json / .json.gz), or a folder of them, merged into one series."""
    if os.path.isdir(path):
        files = sorted(os.path.join(path, f) for f in os.listdir(path)
                       if f.endswith((".json", ".json.gz")))
        if not files:
            raise LabsError("no chart JSON in the folder %s" % path)
    elif os.path.isfile(path):
        files = [path]
    else:
        raise LabsError("no offline file or folder at %s" % path)
    charts = []
    for f in files:
        try:
            if f.endswith(".gz"):
                with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            else:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
        except OSError as e:
            raise LabsError("cannot read %s (%s)" % (f, e))
        charts.append(parse_chart(text, sym if len(files) == 1 else None))
    bars, seen = [], set()
    for ch in charts:
        for b in ch["bars"]:
            if b["ts"] not in seen:
                seen.add(b["ts"])
                bars.append(b)
    if not bars:
        raise LabsError("no usable bars in %s" % path)
    bars.sort(key=lambda b: b["ts"])
    return {"symbol": charts[0]["symbol"], "bars": bars, "interval": charts[0]["interval"],
            "prev_close": charts[0].get("prev_close")}


def get_chart(sym, offline=None, rng="60d", interval="5m"):
    if offline:
        return load_offline(offline, sym)
    return parse_chart(fetch_chart(sym, rng, interval), sym)


def sessions(chart, interval_min=5):
    """Group bars into regular-session days: {date: [bars]}, weekends and holidays dropped."""
    out = {}
    for b in chart["bars"]:
        day = b["date"]
        if not is_session_day(day):
            continue
        if b["minute"] < OPEN_MIN or b["minute"] >= close_minute(day):
            continue
        out.setdefault(day, []).append(b)
    for day in out:
        out[day].sort(key=lambda b: b["ts"])
    return out


# ---------------------------------------------------------------- the rules

def _exit_at_close(tr, bar, why):
    price = bar["close"]
    tr["exit"] = round(price, 4)
    tr["exit_time"] = clock24(bar["minute"])
    tr["exit_date"] = bar["date"].isoformat()
    tr["exit_bar"] = bar["ny"].strftime("%Y-%m-%d %H:%M")
    tr["why"] = why
    tr["r"] = round(tr["_sign"] * (price - tr["entry"]) / tr["risk"], 4)
    return tr


def run_ema_flip(day_bars, ema_period=12, atr_period=14, atr_k=3.0, skip=0,
                 allow_short=False, flat_by=None):
    """One session of the EMA flip rule. At most one trade a day, in at the close
    of the signal bar, trailing stop ratcheted at each close and enforced from the
    NEXT bar (never with information the entry did not have)."""
    if len(day_bars) < max(ema_period, atr_period) + 2:
        return None
    closes = [b["close"] for b in day_bars]
    e = ema(closes, ema_period)
    a = atr(day_bars, atr_period)
    last = flat_by if flat_by is not None else close_minute(day_bars[0]["date"]) - interval_of(day_bars)
    started = OPEN_MIN + skip
    tr = None
    for i, b in enumerate(day_bars):
        if e[i] is None or a[i] is None or a[i] <= 0:
            continue
        if tr is None:
            if b["minute"] < started or b["minute"] >= last:
                continue
            prev_close = closes[i - 1]
            prev_ema = e[i - 1]
            if prev_ema is None:
                continue                      # no previous state, so no flip to act on
            above = b["close"] > e[i]
            was_above = prev_close > prev_ema
            if above == was_above:
                continue                      # no crossing on this bar
            if not above and not allow_short:
                continue                      # long-only mode ignores down flips
            if b["close"] == e[i]:
                continue                      # a close exactly on the line is not a decision
            side = 1 if above else -1
            entry = b["close"]
            stop = entry - side * atr_k * a[i]
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            tr = {"date": b["date"].isoformat(), "side": "buy" if side > 0 else "sell",
                  "entry": round(entry, 4), "entry_time": clock24(b["minute"]),
                  "entry_bar": b["ny"].strftime("%Y-%m-%d %H:%M"),
                  "stop0": round(stop, 4), "stop": stop, "risk": round(risk, 4),
                  "target": None, "extreme": entry, "_sign": side, "_i": i,
                  "setup": "ema%d-flip" % ema_period, "bars_held": 0}
            continue
        # in a trade: enforce yesterday's stop first, then ratchet at this close
        tr["bars_held"] += 1
        hit = (b["low"] <= tr["stop"]) if tr["_sign"] > 0 else (b["high"] >= tr["stop"])
        if hit:
            tr["exit"] = round(tr["stop"], 4)
            tr["exit_time"] = clock24(b["minute"])
            tr["exit_date"] = b["date"].isoformat()
            tr["exit_bar"] = b["ny"].strftime("%Y-%m-%d %H:%M")
            tr["why"] = "trailing stop"
            tr["r"] = round(-1.0, 4)
            return tr
        tr["extreme"] = max(tr["extreme"], b["close"]) if tr["_sign"] > 0 else min(tr["extreme"], b["close"])
        new_stop = (tr["extreme"] - tr["_sign"] * atr_k * a[i]) if tr["_sign"] > 0 \
            else (tr["extreme"] + atr_k * a[i])
        if tr["_sign"] > 0:
            tr["stop"] = max(tr["stop"], new_stop)
        else:
            tr["stop"] = min(tr["stop"], new_stop)
        if b["minute"] >= last:
            return _exit_at_close(tr, b, "flat by the close")
    if tr is not None and day_bars:
        return _exit_at_close(tr, day_bars[-1], "session ended")
    return None


def interval_of(day_bars):
    if len(day_bars) < 2:
        return 5
    d = day_bars[1]["ts"] - day_bars[0]["ts"]
    return max(1, int(round(d / 60.0)))


def run_level_breakout(day_bars, or_minutes=5, target_r=4.0, allow_short=False,
                       flat_by=None, min_risk_bps=5.0):
    """One session of the level breakout rule: the opening range of the first
    or_minutes is the level, the first CLOSE through it is the entry, the stop is
    behind the signal candle, the target is target_r times that risk."""
    if len(day_bars) < 3:
        return None
    step = interval_of(day_bars)
    n_or = max(1, int(round(or_minutes / float(step))))
    if n_or >= len(day_bars):
        return None
    or_bars = day_bars[:n_or]
    hi = max(b["high"] for b in or_bars)
    lo = min(b["low"] for b in or_bars)
    last = flat_by if flat_by is not None else close_minute(day_bars[0]["date"]) - step
    tr = None
    for b in day_bars[n_or:]:
        if tr is None:
            if b["minute"] >= last:
                break
            side = 0
            if b["close"] > hi:
                side = 1
            elif b["close"] < lo and allow_short:
                side = -1
            if not side:
                continue
            entry = b["close"]
            stop = b["low"] if side > 0 else b["high"]
            risk = side * (entry - stop)
            if risk <= 0:
                continue
            if risk < entry * min_risk_bps / 10000.0:
                continue                      # a doji signal bar makes R meaningless
            tr = {"date": b["date"].isoformat(), "side": "buy" if side > 0 else "sell",
                  "entry": round(entry, 4), "entry_time": clock24(b["minute"]),
                  "entry_bar": b["ny"].strftime("%Y-%m-%d %H:%M"),
                  "stop0": round(stop, 4), "stop": stop, "risk": round(risk, 4),
                  "target": round(entry + side * target_r * risk, 4),
                  "_sign": side, "setup": "level-breakout",
                  "level": round(hi if side > 0 else lo, 4), "bars_held": 0}
            continue
        tr["bars_held"] += 1
        if tr["_sign"] > 0:
            if b["low"] <= tr["stop"]:
                return _closed(tr, tr["stop"], b, "stop")
            if b["high"] >= tr["target"]:
                return _closed(tr, tr["target"], b, "target %gR" % target_r)
        else:
            if b["high"] >= tr["stop"]:
                return _closed(tr, tr["stop"], b, "stop")
            if b["low"] <= tr["target"]:
                return _closed(tr, tr["target"], b, "target %gR" % target_r)
        if b["minute"] >= last:
            return _exit_at_close(tr, b, "flat by the close")
    if tr is not None and day_bars:
        return _exit_at_close(tr, day_bars[-1], "session ended")
    return None


def _closed(tr, price, bar, why):
    tr["exit"] = round(price, 4)
    tr["exit_time"] = clock24(bar["minute"])
    tr["exit_date"] = bar["date"].isoformat()
    tr["exit_bar"] = bar["ny"].strftime("%Y-%m-%d %H:%M")
    tr["why"] = why
    tr["r"] = round(tr["_sign"] * (price - tr["entry"]) / tr["risk"], 4)
    return tr


STRATEGIES = {
    "ema12-flip": run_ema_flip,
    "level-breakout": run_level_breakout,
}


def backtest(chart, strategy, is_until=None, oos_from=None, **kw):
    """Run one rule over every session in the chart. Returns trades + the split."""
    fn = STRATEGIES.get(strategy)
    if fn is None:
        raise LabsError("unknown strategy %r (choose from: %s)"
                        % (strategy, ", ".join(sorted(STRATEGIES))))
    trades = []
    for day in sorted(sessions(chart)):
        try:
            tr = fn(chart_bars_for_day(chart, day), **kw)
        except LabsError:
            raise
        except (TypeError, ValueError):
            tr = None
        if tr:
            trades.append(tr)
    def keep(t):
        d = t["date"]
        return d
    is_tr = [t for t in trades if (not is_until or t["date"] <= is_until)]
    oos_tr = [t for t in trades if (is_until and t["date"] > is_until)]
    if oos_from:
        oos_tr = [t for t in oos_tr if t["date"] >= oos_from]
    return {"strategy": strategy, "symbol": chart["symbol"], "params": _params(kw),
            "trades": trades, "in_sample": is_tr, "out_of_sample": oos_tr,
            "sessions": len(sessions(chart)), "window": _window(trades)}


def chart_bars_for_day(chart, day):
    return [b for b in chart["bars"] if b["date"] == day]


def _params(kw):
    return {k: v for k, v in sorted(kw.items()) if v is not None}


def _window(trades):
    if not trades:
        return None
    return {"from": min(t["date"] for t in trades), "to": max(t["date"] for t in trades)}


# ---------------------------------------------------------------- statistics

def stats(trades):
    """The numbers that matter, in R. Nothing here depends on a position size."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": None, "total_r": 0.0, "avg_r": None,
                "expectancy_r": None, "profit_factor": None, "max_drawdown_r": 0.0,
                "t_stat": None, "best_r": None, "worst_r": None, "avg_bars_held": None}
    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    # max drawdown of the cumulative R curve, in R
    peak = 0.0
    run = 0.0
    mdd = 0.0
    for r in rs:
        run += r
        peak = max(peak, run)
        mdd = max(mdd, peak - run)
    return {
        "trades": n,
        "wins": len(wins),
        "win_rate": round(100.0 * len(wins) / n, 2),
        "total_r": round(sum(rs), 2),
        "avg_r": round(mean(rs), 4),
        "expectancy_r": round(mean(rs), 4),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "max_drawdown_r": round(mdd, 2),
        "t_stat": round(t_stat(rs), 2),
        "best_r": round(max(rs), 2),
        "worst_r": round(min(rs), 2),
        "avg_bars_held": round(mean([t.get("bars_held", 0) for t in trades]), 1),
        "gross_win_r": round(gross_win, 2),
        "gross_loss_r": round(gross_loss, 2),
    }


def verdict(st_is, st_oos, n_variants=1):
    """One plain sentence. Deliberately hard to flatter."""
    if st_is["trades"] < 30:
        return ("NOT ENOUGH DATA: %d trades in-sample. Under about 30 you cannot separate a rule "
                "from luck, and no verdict below means anything." % st_is["trades"])
    luck = selection_inflation_sigma(n_variants)
    lines = []
    is_avg = st_is["avg_r"] or 0.0
    oos_avg = (st_oos["avg_r"] or 0.0) if st_oos["trades"] else None
    if st_oos["trades"] < 30:
        lines.append("IN-SAMPLE ONLY: %+.4fR a trade over %d trades (t=%s). There is no "
                     "out-of-sample window with enough trades to judge it."
                     % (is_avg, st_is["trades"], st_is["t_stat"]))
    else:
        decay = (oos_avg - is_avg)
        lines.append("IN-SAMPLE %+.4fR a trade (t=%s), OUT-OF-SAMPLE %+.4fR a trade (t=%s): "
                     "the edge moved %+.4fR when the data changed."
                     % (is_avg, st_is["t_stat"], oos_avg, st_oos["t_stat"], decay))
        is_sig = abs(st_is["t_stat"] or 0.0) >= 2.0
        oos_sig = abs(st_oos["t_stat"] or 0.0) >= 2.0
        if not is_sig and not oos_sig:
            lines.append("Neither window shows a signal: both t statistics are inside +-2, so this "
                         "is noise measured twice. There is no edge here to overfit, and no edge "
                         "to trade. Do not read the sign of a number this small.")
        elif is_sig and is_avg > 0 and oos_avg <= 0:
            lines.append("That is the signature of a rule fitted to its own sample. Treat the "
                         "in-sample number as the measurement of an error, not of an edge.")
        elif is_sig and is_avg < 0:
            lines.append("The rule loses, and loses measurably: the in-sample t is below -2. "
                         "A losing rule is a finding, not a failure of the test. Either the rule "
                         "is wrong for this instrument or the stop is inside the noise; a tighter "
                         "trail on a 5-minute bar is usually the second one.")
        elif oos_avg > 0 and abs(decay) < 0.5 * abs(is_avg or 1e-9):
            lines.append("It held up on data it had not seen. That is the only result worth "
                         "carrying forward, and it is still one window of one instrument.")
        else:
            lines.append("In-sample and out-of-sample disagree without either being decisive. "
                         "That is an inconclusive result, and inconclusive means do not trade it.")
    if n_variants > 1:
        lines.append("Best of %d variants: expect the winner's in-sample score to sit about "
                     "%.2f standard deviations above the pack from luck alone. Compare the "
                     "winner's out-of-sample row with the MEDIAN variant's, not with the best."
                     % (n_variants, luck))
    if (st_is["t_stat"] or 0) < 2:
        lines.append("t=%s is below 2: this sample cannot reject 'no edge'." % st_is["t_stat"])
    return " ".join(lines)


# ---------------------------------------------------------------- variants

def variant_grid(strategy):
    if strategy == "ema12-flip":
        return [dict(ema_period=e, atr_period=p, atr_k=k)
                for e in (9, 12, 20) for p in (10, 14, 20) for k in (2.0, 3.0, 4.0, 5.0)]
    if strategy == "level-breakout":
        return [dict(or_minutes=m, target_r=r)
                for m in (5, 15, 30) for r in (1.0, 2.0, 4.0, 6.0, 8.0)]
    return [{}]


def run_variants(chart, strategy, is_until=None, oos_from=None, grid=None, allow_short=False):
    grid = grid or variant_grid(strategy)
    rows = []
    for i, g in enumerate(grid):
        kw = dict(g)
        kw["allow_short"] = allow_short
        bt = backtest(chart, strategy, is_until=is_until, oos_from=oos_from, **kw)
        st_is = stats(bt["in_sample"])
        st_oos = stats(bt["out_of_sample"])
        rows.append({"variant": i, "params": g, "in_sample": st_is, "out_of_sample": st_oos})
    ranked = sorted(rows, key=lambda r: -(r["in_sample"]["avg_r"] or -9e9))
    n = len(ranked)
    best = ranked[0] if n else None
    summary = {
        "strategy": strategy, "variants": n,
        "best_in_sample": best,
        "median_in_sample_avg_r": round(_median([r["in_sample"]["avg_r"] or 0.0 for r in ranked]), 4) if n else None,
        "median_out_of_sample_avg_r": round(_median([r["out_of_sample"]["avg_r"] or 0.0 for r in ranked
                                                     if r["out_of_sample"]["trades"]]), 4) if n else None,
        "expected_luck_sigma": round(selection_inflation_sigma(n), 2),
        "selection_gap_r": None,
    }
    if best and best["out_of_sample"]["trades"]:
        summary["selection_gap_r"] = round((best["in_sample"]["avg_r"] or 0.0)
                                           - (best["out_of_sample"]["avg_r"] or 0.0), 4)
    return {"rows": ranked, "summary": summary}


def _median(a):
    if not a:
        return 0.0
    s = sorted(a)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# ---------------------------------------------------------------- output

NOT_FINANCIAL_ADVICE = "Education and tooling, not financial advice."
NO_ORDER = ("Nothing was placed. This tool cannot place an order: it reads bars and does arithmetic. "
            "If a rule survives and you want to trade it, /trader-exit writes the plan, "
            "/trader-budget sizes it, /trader-risk checks it, and /trader-broker asks you yes or no.")


def _fmt_stats(st, label):
    if not st["trades"]:
        return "  %-14s no trades" % label
    pf = st["profit_factor"]
    return ("  %-14s %4d trades | win %5.1f%% | total %+8.2fR | avg %+.4fR | PF %s | "
            "max DD %.2fR | t=%s"
            % (label, st["trades"], st["win_rate"], st["total_r"], st["avg_r"],
               ("%.2f" % pf) if pf is not None else "n/a", st["max_drawdown_r"], st["t_stat"]))


def print_run(bt, n_variants=1, show=8):
    st_all = stats(bt["trades"])
    st_is = stats(bt["in_sample"])
    st_oos = stats(bt["out_of_sample"])
    w = bt["window"] or {"from": "?", "to": "?"}
    print("%s %s, %s to %s (%d sessions in the file)"
          % (bt["symbol"], bt["strategy"], w["from"], w["to"], bt["sessions"]))
    if bt["params"]:
        print("  params: " + ", ".join("%s=%s" % kv for kv in sorted(bt["params"].items())))
    print(_fmt_stats(st_all, "all trades"))
    print(_fmt_stats(st_is, "in-sample"))
    print(_fmt_stats(st_oos, "out-of-sample"))
    if st_all["trades"]:
        sides = {}
        for t in bt["trades"]:
            sides[t["side"]] = sides.get(t["side"], 0) + 1
        whys = {}
        for t in bt["trades"]:
            whys[t["why"]] = whys.get(t["why"], 0) + 1
        print("  sides: " + ", ".join("%s %d" % kv for kv in sorted(sides.items()))
              + " | exits: " + ", ".join("%s %d" % kv for kv in sorted(whys.items())))
    print()
    print(verdict(st_is, st_oos, n_variants))
    if show and bt["trades"]:
        print()
        print("  last %d trades:" % min(show, len(bt["trades"])))
        for t in bt["trades"][-show:]:
            print("    %s %-4s %-5s in %s @ %s, stop %s%s, out %s @ %s (%s) = %+.2fR"
                  % (t["date"], t["side"], t["setup"], t["entry_time"], t["entry"],
                     t["stop0"], (" -> target %s" % t["target"]) if t.get("target") else "",
                     t["exit_time"], t["exit"], t["why"], t["r"]))
    print()
    print(NO_ORDER)
    print(NOT_FINANCIAL_ADVICE)


def print_variants(res, show=10):
    s = res["summary"]
    print("%s: %d variants, one rule family" % (s["strategy"], s["variants"]))
    print("  expected in-sample lift of the best variant from luck alone: %.2f sigma"
          % s["expected_luck_sigma"])
    print("  median variant in-sample avg R: %s | median out-of-sample avg R: %s"
          % (s["median_in_sample_avg_r"], s["median_out_of_sample_avg_r"]))
    if s["selection_gap_r"] is not None:
        print("  the winner's in-sample avg R minus its own out-of-sample avg R: %+.4fR"
              % s["selection_gap_r"])
    print()
    print("  %-4s %-34s %6s %9s %8s %6s %9s %8s" %
          ("#", "params", "IS n", "IS avgR", "IS t", "OOS n", "OOS avgR", "OOS t"))
    for r in res["rows"][:show]:
        p = ", ".join("%s=%s" % kv for kv in sorted(r["params"].items()))
        i, o = r["in_sample"], r["out_of_sample"]
        print("  %-4d %-34s %6d %9s %8s %6d %9s %8s"
              % (r["variant"], p[:34], i["trades"],
                 ("%+.4f" % i["avg_r"]) if i["trades"] else "-", i["t_stat"] if i["trades"] else "-",
                 o["trades"], ("%+.4f" % o["avg_r"]) if o["trades"] else "-",
                 o["t_stat"] if o["trades"] else "-"))
    print()
    print("  Read the MEDIAN row, not the top row. The top row was chosen because it looks good.")
    print()
    print(NO_ORDER)
    print(NOT_FINANCIAL_ADVICE)


def print_rank(results):
    print("Ranked by out-of-sample average R, then in-sample. A rule with no out-of-sample")
    print("trades ranks below every rule that has them, whatever its in-sample score.")
    print()
    print("  %-17s %-30s %6s %9s %6s %9s %8s %s" %
          ("strategy", "params", "IS n", "IS avgR", "OOS n", "OOS avgR", "IS t", "verdict"))

    def key(r):
        o = r["out_of_sample"]
        i = r["in_sample"]
        return (1 if o["trades"] >= 30 else 0,
                (o["avg_r"] or -9e9) if o["trades"] else -9e9,
                i["avg_r"] or -9e9)
    for r in sorted(results, key=key, reverse=True):
        p = ", ".join("%s=%s" % kv for kv in sorted(r["params"].items()))[:30]
        i, o = r["in_sample"], r["out_of_sample"]
        v = "no data" if not i["trades"] else ("holds" if (o["trades"] >= 30 and (o["avg_r"] or 0) > 0)
                                               else ("dies OOS" if o["trades"] >= 30 else "untested OOS"))
        print("  %-17s %-30s %6d %9s %6d %9s %8s %s"
              % (r["strategy"], p, i["trades"], ("%+.4f" % i["avg_r"]) if i["trades"] else "-",
                 o["trades"], ("%+.4f" % o["avg_r"]) if o["trades"] else "-",
                 i["t_stat"] if i["trades"] else "-", v))
    print()
    print("  Ranking inside one window of one instrument is weak evidence. Re-run it on a")
    print("  different instrument and a different window before you believe the order.")
    print()
    print(NO_ORDER)
    print(NOT_FINANCIAL_ADVICE)


def print_claims():
    print("Published claims this lab can be pointed at. None of them is stated here as fact,")
    print("and none of them came with the data needed to check it.")
    for c in CLAIMS:
        print()
        print("  %s (%s)" % (c["id"], c["strategy"]))
        print("    claim:  %s" % c["claim"])
        print("    source: %s" % c["source"])
        print("    checkable with free data: %s" % ("yes" if c["verifiable_with_free_data"] else "no"))
        print("    why: %s" % c["why"])
        print("    what would check it: %s" % c["what_would_check_it"])
    print()
    print("  Run one with: labs.py run --strategy <name> --symbol <T> --offline <file>")
    print()
    print(NOT_FINANCIAL_ADVICE)


def _strip_private(trades):
    return [{k: v for k, v in t.items() if not k.startswith("_")} for t in trades]


# ---------------------------------------------------------------- cli

def cmd_run(a):
    chart = get_chart(a.symbol, offline=a.offline, rng=a.range, interval=a.interval)
    kw = _kw_from_args(a)
    bt = backtest(chart, a.strategy, is_until=a.is_until, oos_from=a.oos_from, **kw)
    if a.json:
        out = {"strategy": bt["strategy"], "symbol": bt["symbol"], "params": bt["params"],
               "window": bt["window"], "sessions": bt["sessions"],
               "all": stats(bt["trades"]), "in_sample": stats(bt["in_sample"]),
               "out_of_sample": stats(bt["out_of_sample"]),
               "verdict": verdict(stats(bt["in_sample"]), stats(bt["out_of_sample"]), a.variants),
               "trades": _strip_private(bt["trades"][-200:]),
               "disclaimer": NOT_FINANCIAL_ADVICE}
        print(json.dumps(out, indent=1, sort_keys=True))
    else:
        print_run(bt, n_variants=a.variants, show=a.show)
    if a.write:
        _write(a.write, {"strategy": bt["strategy"], "symbol": bt["symbol"], "params": bt["params"],
                         "window": bt["window"], "all": stats(bt["trades"]),
                         "in_sample": stats(bt["in_sample"]), "out_of_sample": stats(bt["out_of_sample"]),
                         "trades": _strip_private(bt["trades"])})
        print("Wrote %s." % a.write)
    return 0 if bt["trades"] else 1


def cmd_variants(a):
    chart = get_chart(a.symbol, offline=a.offline, rng=a.range, interval=a.interval)
    res = run_variants(chart, a.strategy, is_until=a.is_until, oos_from=a.oos_from,
                       allow_short=a.allow_short)
    if a.json:
        print(json.dumps(res, indent=1, sort_keys=True))
    else:
        print_variants(res, show=a.show)
    if a.write:
        _write(a.write, res)
        print("Wrote %s." % a.write)
    return 0


def cmd_rank(a):
    chart = get_chart(a.symbol, offline=a.offline, rng=a.range, interval=a.interval)
    results = []
    for strat in sorted(STRATEGIES):
        for g in variant_grid(strat):
            kw = dict(g)
            kw["allow_short"] = a.allow_short
            bt = backtest(chart, strat, is_until=a.is_until, oos_from=a.oos_from, **kw)
            results.append({"strategy": strat, "params": g,
                            "in_sample": stats(bt["in_sample"]),
                            "out_of_sample": stats(bt["out_of_sample"])})
    if a.json:
        print(json.dumps(results, indent=1, sort_keys=True))
    else:
        print_rank(results)
    return 0


def cmd_claims(a):
    if a.json:
        print(json.dumps(CLAIMS, indent=1))
    else:
        print_claims()
    return 0


def _kw_from_args(a):
    if a.strategy == "ema12-flip":
        return {"ema_period": a.ema_period, "atr_period": a.atr_period, "atr_k": a.atr_k,
                "skip": a.skip, "allow_short": a.allow_short,
                "flat_by": parse_clock(a.flat_by, "--flat-by") if a.flat_by else None}
    return {"or_minutes": a.or_minutes, "target_r": a.target_r, "allow_short": a.allow_short,
            "flat_by": parse_clock(a.flat_by, "--flat-by") if a.flat_by else None}


def _write(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="labs.py",
        description="Test a published trading rule on your own data, honestly (trader-labs).")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--symbol", default="QQQ")
        p.add_argument("--offline", metavar="PATH",
                       help="a saved Yahoo chart JSON (.json/.json.gz) or a folder of them; no network")
        p.add_argument("--range", default="60d", help="Yahoo range when fetching (default 60d)")
        p.add_argument("--interval", default="5m", choices=["5m", "15m", "30m", "1h", "1d"])
        p.add_argument("--is-until", dest="is_until", metavar="YYYY-MM-DD",
                       help="in-sample ends on this New York date; later trades are out-of-sample")
        p.add_argument("--oos-from", dest="oos_from", metavar="YYYY-MM-DD",
                       help="drop out-of-sample trades before this date")
        p.add_argument("--flat-by", help="flatten at this New York time (default: the session close)")
        p.add_argument("--allow-short", action="store_true",
                       help="take the short side too (off by default: the pack is long-only)")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("run", help="backtest one rule over the file or the free 60-day window")
    common(p)
    p.add_argument("--strategy", default="ema12-flip", choices=sorted(STRATEGIES))
    p.add_argument("--ema-period", type=int, default=12)
    p.add_argument("--atr-period", type=int, default=14)
    p.add_argument("--atr-k", type=float, default=3.0, help="trail distance in ATRs (default 3)")
    p.add_argument("--skip", type=int, default=0, help="minutes after 9:30 before the rule may fire")
    p.add_argument("--or-minutes", type=int, default=5, help="opening-range length for level-breakout")
    p.add_argument("--target-r", type=float, default=4.0, help="target in R for level-breakout")
    p.add_argument("--variants", type=int, default=1,
                   help="how many variants were tried before this one was picked, for the verdict")
    p.add_argument("--show", type=int, default=8, help="print this many recent trades")
    p.add_argument("--write", nargs="?", const="trader/labs.json", metavar="PATH",
                   help="save the result (default trader/labs.json)")

    p = sub.add_parser("variants", help="run the whole parameter grid and show the selection bias")
    common(p)
    p.add_argument("--strategy", default="level-breakout", choices=sorted(STRATEGIES))
    p.add_argument("--show", type=int, default=10)
    p.add_argument("--write", nargs="?", const="trader/labs-variants.json", metavar="PATH")

    p = sub.add_parser("rank", help="every rule and every variant in one table")
    common(p)

    p = sub.add_parser("claims", help="what the videos assert, and what it would take to check it")
    p.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    try:
        return {"run": cmd_run, "variants": cmd_variants, "rank": cmd_rank,
                "claims": cmd_claims}[a.cmd](a)
    except LabsError as e:
        print("labs.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
