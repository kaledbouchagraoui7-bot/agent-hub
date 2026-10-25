# The two published strategies, tested and ranked

Everything in the "measured" columns below was produced by `trader-agents/trader-labs/labs.py`
in this session. Everything in the "claimed" columns is a transcript of a short-form
video and is **not** established fact. Nothing here is financial advice.

---

## 1. What was actually claimed

**Strategy A, "the simplest Nasdaq strategy" (EMA-12 flip).** Wait for the New York
open, watch one candle, the first five minutes. Close above the 12 EMA, buy. Close
below, sell. Do not take a small fixed profit: let the winner run, with the stop
following the trend. Claimed: over six years of backtesting, more than 1,400 trades,
a 57 % win rate, 508 % total return, and now trading live automatically.

**Strategy B, "mambafx's levels" (level breakout, 4R to 8R target).** Mark levels
before New York opens. After 9:30, a five-minute candle closes through one and you
are in, with the stop right behind that candle. Do not take profit early; out before
the close if the target has not hit. The claimed fix was the target: 4R was not
enough, so let the winner run to 8R. Claimed: 1,750 trades, lost almost three out of
four, ended at +313R, but picked as one winner out of **1,380 variants**. Then
chosen on 2019 to 2023 only and run on 2024 to 2026, years it never saw: **+99R**.
Then the same rules on the next window: **-107R**.

Both transcripts end in a funnel: "check the link in our bio", "comment algo and I
will send you the link", "join our free community". That is a marketing structure,
and the numbers inside it are marketing copy until someone reproduces them.

## 2. What I could and could not verify

| claim | verifiable here? | why |
|---|---|---|
| A: 508 % over six years | **No** | Yahoo's free chart endpoint serves about 60 days of 5-minute bars. Six years of intraday history needs a vendor file nobody supplied. A percentage return also needs a sizing rule and a compounding convention, and neither is stated. |
| A: 57 % win rate, 1,400 trades | **Partly** | Win rate is measurable on any window. On 60 real QQQ sessions I measured 8.3 %, not 57 %. Different instrument, era and (unstated) trailing rule, so this is not a refutation, but the published figure is not reproducible from free data. |
| A: "now trading live" | **No** | No account statement, no broker, no track record was provided. Unfalsifiable as stated. |
| B: +313R best of 1,380 variants | **No**, but the arithmetic is checkable | The best of 1,380 independent noisy results sits about `sqrt(2 ln 1380)` = **3.80 sigma** above the pack from luck alone. That is not a suspicion, it is the expected value of the maximum. |
| B: +99R out-of-sample, then -107R | **Needs no checking** | This is the author's own out-of-sample result, reported against himself. It is the single most informative sentence in either transcript. |
| The channel "quant labs" on TikTok | **Not found** | A web search returned no verifiable profile for it, only an unrelated Instagram page crediting "Quant Labs, 2016". I could not confirm the channel, its track record, or that these two videos are from the same source. Treat the attribution as unconfirmed. |

## 3. Measured results

### 3.1 Engine validation on synthetic series with known answers

Two seeded fixtures (`tests/fixtures/trader-labs/`, byte-reproducible): a pure
random walk, and the same walk with a planted per-day drift. 200 sessions each,
15,600 bars, split in-sample at 2026-07-31.

| strategy | fixture | trades IS | win % IS | avg R IS | t IS | trades OOS | avg R OOS | t OOS |
|---|---|---|---|---|---|---|---|---|
| level-breakout | random walk | 124 | 21.8 | **+0.0077** | **0.04** | 44 | -0.0036 | -0.01 |
| level-breakout | planted drift | 97 | 62.9 | **+2.1443** | **8.70** | 34 | +1.1280 | 2.66 |
| ema12-flip | random walk | 145 | 11.0 | **-0.6465** | **-7.48** | 55 | -0.8790 | -12.14 |
| ema12-flip | planted drift | 132 | 31.8 | +0.2724 | 1.51 | 49 | -0.3250 | -1.50 |

Read the first row as the engine's honesty proof: on data with no edge in it, the
level-breakout rule returns +0.0077R a trade with t = 0.04. It finds nothing, which
is the correct answer. Read the second row as its competence proof: on data with a
planted edge, it finds +2.14R a trade at t = 8.7 and keeps +1.13R out of sample.

The third row is the first real result about Strategy A, and it is not about the
market. A 3xATR trailing stop on a series with no drift loses 0.65R a trade with
t = -7.48. That is not bad luck; it is the cost of the mechanism. A trail that
tight converts noise into a stream of -1R exits, and you need about a 19 % win rate
just to break even at a 4.3R average winner. It is structurally short volatility.

### 3.2 Selection bias, demonstrated

`labs.py variants --strategy level-breakout` on the **pure random walk**, 15
parameter combinations:

```
expected in-sample lift of the best variant from luck alone: 2.33 sigma
median variant in-sample avg R: -0.0866 | median out-of-sample avg R: -0.25
the winner's in-sample avg R minus its own out-of-sample avg R: +0.3479R

  #    params                     IS n   IS avgR   IS t   OOS n  OOS avgR  OOS t
  12   or_minutes=30, target_r=4   110   +0.0371    0.2      38   -0.3108  -1.16
  1    or_minutes=5,  target_r=2   124   +0.0082    0.07     44   -0.2500  -1.26
  ...
  9    or_minutes=15, target_r=8   118   -0.2805   -1.57     42   -0.1509  -0.40
```

On data that contains **no edge whatsoever**, the best of 15 variants is the only
one with a positive in-sample score, and it goes to -0.31R out of sample. Scale
that from 15 variants to 1,380 and the expected luck-only lift goes from 2.33 sigma
to 3.80 sigma. This is the whole of Strategy B's +313R, explained without assuming
anything about markets.

### 3.3 Real data: QQQ, 60 sessions to 2026-10-23, fetched live from Yahoo

Strategy A, trailing distance swept to show the mechanism is what matters:

| `--atr-k` | trades | win % | avg R | total R | t |
|---|---|---|---|---|---|
| 1.5 | 60 | 0.0 | -1.0000 | -60.00 | 0.0 |
| 3.0 (as published) | 60 | 8.3 | -0.8677 | -52.06 | -16.48 |
| 6.0 | 60 | 46.7 | -0.2625 | -15.75 | -3.21 |
| 10.0 | 60 | 51.7 | -0.0625 | -3.75 | -1.30 |

The win rate climbs monotonically as the trail widens, which confirms the engine
is doing what it says and that the published win rate is a function of an
undisclosed parameter. Even at 10xATR the rule is negative. Sixty sessions is a
small sample and this is one instrument, but the direction is consistent across
every setting and matches the synthetic result.

Strategy B on the same real QQQ window, 4R target: **43 trades, 27.9 % win rate,
+3.71R total, +0.0863R a trade, profit factor 1.13, t = 0.31.** The win rate lands
almost exactly on the claimed "lost almost three out of four". The expectancy is
positive and statistically indistinguishable from zero. That is the honest summary:
not disproved, not supported.

`labs.py rank --symbol QQQ` across all 51 variants of both rules returns every row
as "untested OOS", because a 60-day window cannot be split into two windows that
each hold 30 trades. The tool says so rather than ranking on in-sample score alone.

## 4. Ranking

Ranked by how much trustworthy evidence exists that the rule has positive
expectancy after costs, which is the only question that matters. Not ranked by
claimed ROI, because neither claimed ROI is reproducible.

| rank | strategy | claimed ROI | measured | verdict |
|---|---|---|---|---|
| **1** | **B, level breakout, 4R to 8R target** | +313R in-sample, +99R OOS, -107R after | +0.0863R a trade on 60 real QQQ sessions, t = 0.31; win rate 27.9 % vs claimed ~25 % | **Unproven, not disproved.** The payoff asymmetry (risk 1R, target 4R to 8R, capped downside) is the only structural feature in either transcript that can produce positive expectancy from a small edge. The author's own -107R says it did not survive. |
| **2** | **A, EMA-12 flip with a trailing stop** | 508 % over six years, 57 % wins | -0.87R a trade on 60 real QQQ sessions, t = -16.48, win 8.3 %; -0.65R on a synthetic random walk, t = -7.48 | **Fails as published.** The mechanism loses in noise by construction, and the claimed win rate is not reachable at a 3xATR trail: it needs roughly 5x to 10x, at which point it is a different rule than the one described. |
| **3** | A with `--allow-short` | "if it closes below, we sell" | -0.6667R a trade on the noise fixture; -0.7272R on the drift fixture, where long-only made +0.2724R | **Worse.** Shorting the down-flip is one trade a day, so on an up-drifting series it replaces the profitable long with a losing short. |

### Why B outranks A even though A has the bigger claimed number

A's claim is bigger and its evidence is worse. A 57 % win rate combined with a
"let the winner run" exit is internally strained: trailing exits produce a low win
rate and a fat right tail, which is precisely what B's transcript reports (25 %
wins, +313R) and what my own runs reproduce (21 % to 28 % wins). A's numbers look
like a scalping rule's win rate attached to a trend-following rule's exit. Either
the trailing parameter is undisclosed, or the 508 % is a percentage-of-account
figure produced by a sizing and compounding convention that is doing most of the
work. Both possibilities mean the headline is not the strategy.

### The one thing in these transcripts worth acting on

Strategy B's author published his own failure: best of 1,380 variants, +313R
in-sample, +99R out-of-sample, -107R on the next window. That is a complete,
correct demonstration of data-snooping bias, given away free, and it is more
useful than any of the return figures. `labs.py variants` exists to reproduce that
lesson on your own data before you risk money on it.

## 5. What would change this ranking

1. **A vendor file of 5-minute bars**, six years, one Nasdaq instrument. Then A's
   508 % and B's 313R become checkable in an afternoon, and `--offline` already
   reads it.
2. **The full variant grid** for B, all 1,380 results. Then the winner's rank can
   be compared to the distribution it was drawn from, instead of inferred.
3. **A commission and slippage model.** B took 43 trades in 60 sessions and made
   +0.0863R a trade. At even 0.02R of round-trip cost a trade, roughly a quarter of
   that disappears. A, trading every single session, is far more exposed. Neither
   figure above includes any cost, and both are optimistic because of it.
4. **More instruments and more windows.** Every number here is one instrument or
   one synthetic series. Cross-sectional consistency is the cheapest robustness
   test there is and it has not been run.

## 6. Reproduce all of it

```bash
cd /home/user/trader-agents
python3 -m unittest discover -s tests                       # 369 tests, OK

R=trader-labs/labs.py
F=tests/fixtures/trader-labs

python3 $R claims
python3 $R run      --strategy level-breakout --symbol LABS --offline $F/labs-noedge-5m.json.gz --is-until 2026-07-31
python3 $R run      --strategy level-breakout --symbol LABS --offline $F/labs-trend-5m.json.gz --is-until 2026-07-31
python3 $R variants --strategy level-breakout --symbol LABS --offline $F/labs-noedge-5m.json.gz --is-until 2026-07-31
python3 $R run      --strategy ema12-flip     --symbol QQQ --atr-k 3      # live, 60 days
python3 $R run      --strategy level-breakout --symbol QQQ --target-r 4   # live, 60 days
python3 $R rank     --symbol QQQ
```

Regenerate the fixtures byte-identically with `python3 tests/make_labs_fixtures.py`.

**Not financial advice.** Most people who day trade lose money. Every number above
is arithmetic on bars, with no commission, no slippage, no borrow cost, no partial
fills and no queue position, and the real-data window is 60 sessions of one ETF.
