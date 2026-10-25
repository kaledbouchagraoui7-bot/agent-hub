#!/usr/bin/env python3
"""Build the two deterministic fixtures trader-labs is tested on.

Both are synthetic, seeded, and reproducible: run this file and the two fixtures
come back byte-identical. They are not market data and they are not a claim about
any market. They exist so the engine can be checked against series whose answer
is known in advance.

    python3 tests/make_labs_fixtures.py            # writes both files, prints a checksum

  labs-noedge-5m.json.gz    a pure random walk, zero drift. Any rule run on it
                            must come out near 0R a trade with a t below 2. If a
                            backtester finds an edge here, the backtester is wrong.
  labs-trend-5m.json.gz     the same walk plus a persistent per-day drift, so a
                            trend-following rule that goes long above a moving
                            average and trails its stop SHOULD be positive, in
                            sample and out of sample. If the engine cannot see an
                            edge that is really there, it is broken too.

Shape is Yahoo's chart v8 JSON, gzipped, so the tools read it with --offline and
no network. Five-minute bars, 09:30 to 15:55 New York, weekdays only, the house
holiday list respected, 2026-01-02 to 2026-10-19.
"""

import datetime
import gzip
import hashlib
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures", "trader-labs")
FIRST = datetime.date(2026, 1, 2)
LAST = datetime.date(2026, 10, 19)
STEP = 5
BARS = (16 * 60 - (9 * 60 + 30)) // STEP          # 77 bars, 09:30 .. 15:55

HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07",
}


def _nth_sunday(year, month, n):
    d = datetime.date(year, month, 1)
    d += datetime.timedelta(days=(6 - d.weekday()) % 7)
    return d + datetime.timedelta(weeks=n - 1)


def eastern_offset(utc):
    y = utc.year
    start = datetime.datetime.combine(_nth_sunday(y, 3, 2), datetime.time(7, 0))
    end = datetime.datetime.combine(_nth_sunday(y, 11, 1), datetime.time(6, 0))
    return -4 if start <= utc.replace(tzinfo=None) < end else -5


def ny_to_epoch(ny_naive):
    for off in (-4, -5):
        cand = ny_naive - datetime.timedelta(hours=off)
        if eastern_offset(cand) == off:
            utc = cand
            break
    else:
        utc = ny_naive + datetime.timedelta(hours=5)
    return int((utc - datetime.datetime(1970, 1, 1)).total_seconds())


def session_days():
    days = []
    d = FIRST
    while d <= LAST:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            days.append(d)
        d += datetime.timedelta(days=1)
    return days


def build(seed, drift_fn, start_price=400.0):
    """drift_fn(day_index, bar_index) -> per-bar log drift. Volatility is fixed."""
    rng = random.Random(seed)
    ts, op, hi, lo, cl, vol = [], [], [], [], [], []
    price = start_price
    for di, day in enumerate(session_days()):
        for bi in range(BARS):
            ny = datetime.datetime.combine(day, datetime.time(0, 0)) + \
                datetime.timedelta(minutes=9 * 60 + 30 + bi * STEP)
            drift = drift_fn(di, bi)
            shock = rng.gauss(0.0, 0.0015)
            o = price
            c = o * math.exp(drift + shock)
            wick = abs(rng.gauss(0.0, 0.0007))
            h = max(o, c) * (1.0 + wick)
            l = min(o, c) * (1.0 - wick)
            ts.append(ny_to_epoch(ny))
            op.append(round(o, 4)); hi.append(round(h, 4))
            lo.append(round(l, 4)); cl.append(round(c, 4))
            vol.append(int(rng.uniform(300000, 900000)))
            price = c
    return {"chart": {"result": [{
        "meta": {"currency": "USD", "symbol": "LABS", "exchangeName": "NMS",
                 "fullExchangeName": "NasdaqGS", "instrumentType": "EQUITY",
                 "regularMarketPrice": cl[-1], "chartPreviousClose": start_price,
                 "dataGranularity": "5", "range": "custom", "validRanges": ["custom"],
                 "regularMarketTime": ts[-1]},
        "timestamp": ts,
        "indicators": {"quote": [{"open": op, "high": hi, "low": lo, "close": cl, "volume": vol}]},
    }], "error": None}}


def noedge(di, bi):
    return 0.0


def trend(di, bi):
    """A persistent drift that flips sign every 20 sessions, strongest in the
    first hour: the kind of series a trend-following rule should be able to see."""
    sign = 1.0 if (di // 20) % 2 == 0 else -1.0
    ramp = 1.6 if bi < 12 else 1.0
    return sign * 0.00045 * ramp


def write(name, payload):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    # mtime=0 and compresslevel pinned: gzip embeds a timestamp by default, which
    # would make a regenerated fixture differ byte-wise from the committed one.
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(payload, fh, separators=(",", ":"))
    with open(path, "r+b") as fh:            # zero the mtime field in the header
        fh.seek(4)
        fh.write(b"\x00\x00\x00\x00")
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    print("%-24s %7d bytes  sha256 %s" % (name, os.path.getsize(path), digest[:16]))
    return path


def main():
    a = build(101, noedge)
    b = build(202, trend)
    write("labs-noedge-5m.json.gz", a)
    write("labs-trend-5m.json.gz", b)
    q = a["chart"]["result"][0]
    print("bars per fixture: %d over %d sessions" % (len(q["timestamp"]), len(session_days())))
    print("deterministic: regenerate with the same seeds for byte-identical files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
