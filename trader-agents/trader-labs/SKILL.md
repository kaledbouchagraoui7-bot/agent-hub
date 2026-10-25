---
name: trader-labs
description: >-
  Strategy Lab. Takes a trading rule someone published in a video, a post or a
  course, runs it on your own bars, and tells you what it actually did instead
  of what it claimed. Two rules ship with it: the 12 EMA flip on the first
  5-minute candle after the New York open with a stop that trails the trend, and
  the opening-level breakout with the stop behind the signal candle and a 4R
  target so the winner runs. Every run is split in-sample and out-of-sample, and
  the variants command runs the whole parameter grid so you can see the best of
  1,380 variants next to the median variant, which is the only honest comparison.
  Results come back in R per trade with a t statistic, a profit factor, a maximum
  drawdown and one plain verdict. It places nothing and cannot place anything.
  Use when the user says "I saw this strategy on TikTok", "test this rule",
  "does this actually work", "backtest my strategy", "is this overfitted", "what
  is the win rate really", "rank these strategies", "EMA 12 strategy", "opening
  range breakout with 4R target", "best of N variants", "walk forward this",
  "did it hold up out of sample", or whenever anyone quotes a return figure
  without the data behind it.
argument-hint: "[run | variants | rank | claims] [--strategy NAME] [--symbol T]"
---

# trader-labs

The Strategy Lab is the twelfth skill in this pack, and it is the one that argues
with the other eleven. Everything upstream of it finds a trade and plans it. This
one asks whether the rule that found the trade is worth anything at all.

It exists because a rule described in a 40 second video arrives with a number
attached to it: 508 %, 57 % win rate, 313R, 1,750 trades. The number is not the
evidence. The evidence is the rule, run on bars you fetched yourself, split into
a part the rule was tuned on and a part it never saw, with the number of variants
somebody tried before picking the winner written down next to it.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/labs.py" claims                       # what the videos assert, and what it would take to check it
python3 "${CLAUDE_SKILL_DIR}/labs.py" run --strategy ema12-flip --symbol QQQ
python3 "${CLAUDE_SKILL_DIR}/labs.py" run --strategy level-breakout --symbol QQQ --target-r 4 --is-until 2026-08-31
python3 "${CLAUDE_SKILL_DIR}/labs.py" run --strategy ema12-flip --symbol QQQ --offline trader/qqq-5m.json.gz --json
python3 "${CLAUDE_SKILL_DIR}/labs.py" variants --strategy level-breakout --symbol QQQ    # the whole grid, best next to median
python3 "${CLAUDE_SKILL_DIR}/labs.py" rank --symbol QQQ --offline FILE                   # every rule and variant, one table
```

Flags: `--offline PATH` (a saved Yahoo chart JSON, `.json` or `.json.gz`, or a
folder of them: no network), `--range 60d`, `--interval 5m|15m|30m|1h|1d`,
`--is-until YYYY-MM-DD` and `--oos-from YYYY-MM-DD` (the walk-forward split),
`--flat-by "15:55"`, `--allow-short` (off by default, this pack is long-only),
`--ema-period 12`, `--atr-period 14`, `--atr-k 3`, `--skip 0`, `--or-minutes 5`,
`--target-r 4`, `--variants 1380` (tell the verdict how many you tried),
`--show N`, `--json`, `--write`. Exit code 0 when there were trades to measure,
1 when there were none or the run could not happen, with one plain line saying why.

## The two rules, exactly as published

**`ema12-flip`.** Wait for the New York open. Watch the first 5-minute candle.
If it closes above the 12 EMA, buy. If it closes below, the long side stands
aside, and the short side only fires when you pass `--allow-short`. Then let the
winner run: the stop is the highest close since the entry minus `--atr-k` times
the 14-bar ATR, and it ratchets one way only. Flat at the close whatever happens.

**`level-breakout`.** Mark the level before the open: the high and low of the
first `--or-minutes`. After 9:30, the first 5-minute candle that closes through
the level is the entry, the stop sits behind that candle, and the target is
`--target-r` times that risk, so a winner runs to 4R instead of being scalped.
Out at the close if neither side came first.

Both are intraday and long-only by default, and both are measured in R, never in
percent of account, so the result does not depend on a position size you have
not chosen yet.

## What it reads and writes

| file | what |
| --- | --- |
| Yahoo chart JSON, or `--offline PATH` | 5-minute bars. Free, unofficial, delayed, and only about 60 days deep |
| `trader/labs.json` | written by `run --write`: params, window, all/in-sample/out-of-sample stats, every trade |
| `trader/labs-variants.json` | written by `variants --write`: the whole grid, ranked by in-sample score |
| `trader/config.json` | not read. This skill has no budget, no broker and no orders |

## The four rules it will not break

1. **The stop is checked before the target inside every bar.** A bar that touched
   both is a stop. That is the conservative call, and it is the only honest one
   when all you have is a 5-minute bar rather than the trades inside it.
2. **A trailing stop never uses the bar it is protecting.** The stop enforced
   during bar N was ratcheted at the close of bar N-1. Using bar N's own high to
   move the stop that bar N then hits is a free money machine and a lie.
3. **The entry is the close of the signal bar.** The rule never buys a price it
   could not have seen, and it never buys the low of the bar that triggered it.
4. **The out-of-sample window is chosen by date, before the run.** `--is-until`
   splits the file. Nothing in the run reaches across that line to tune itself.

## Read the output like this

`avg_r` is the expectancy per trade in units of the risk you took. `t` is that
average divided by its own standard error: below about 2, the sample cannot tell
an edge from noise, and no win rate rescues it. `PF` is gross wins over gross
losses. `max DD` is the deepest the cumulative R curve ever went underwater.

Then the line that matters:

* **in-sample positive, out-of-sample near zero or negative.** The rule was
  fitted to its own sample. This is the normal result, not a rare one.
* **best variant far above the median variant.** That gap is what picking the
  winner does to you. The best of N noisy results sits about `sqrt(2 ln N)`
  standard deviations above the pack from luck alone: 3.80 sigma for N = 1,380.
  `variants` prints the median so you can see the gap.
* **fewer than about 30 trades in a window.** The tool says NOT ENOUGH DATA and
  refuses to rank anything. Believe it.
* **held up out of sample.** The only result worth carrying forward, and it is
  still one window of one instrument, with no commission and no slippage in it.

## What it cannot do

Six years of 5-minute bars is not available for free. Yahoo's chart endpoint
gives about 60 days at 5 minutes, and about 7 days at 1 minute, so a claim of
"508 % over six years, 1,400 trades" cannot be checked from free data at all.
Fetch a vendor file, or a long history from your broker, save it in Yahoo's chart
shape and pass `--offline`. The tool reads as many sessions as the file holds.

It also has no commission, no slippage, no borrow cost, no partial fills and no
queue position. A rule that clears 0.02R a trade before costs can easily be
negative after them, and the more trades it takes, the more that matters. Say so
out loud whenever you quote a number from here.

## If a rule survives

Then it is a candidate, not a trade. Hand it to the rest of the pack, in order,
and each step asks you again:

`/trader-exit` writes the plan, `/trader-timemachine` replays it, `/trader-budget`
sizes it to your max loss, `/trader-risk` prints PASS or BLOCK, and only
`/trader-broker` shows a ticket, and only after you type yes for that exact
order, with Claude's own Allow once / Deny card asking one more time. This skill
never gets anywhere near that chain: it has no orders, no broker and no keys.

Education and tooling, not financial advice. Most people who day trade lose
money, and a backtest that looks strong is usually the first step of that, not
an exception to it. A number quoted in a video is marketing until you can run the
rule on bars you fetched yourself.
