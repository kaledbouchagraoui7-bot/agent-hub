# Can you reach €3k/month in 2 months after 8 months of prep? No. Here is the arithmetic and the model that can work.

Prepared 2026-10-25. Every measured number below was produced by running the tools
in `/home/user/trader-agents` and `/home/user/trader-console` in this session, or is
quoted from a primary source named inline. Nothing is estimated where it could be
computed. **Not financial advice.**

---

## 1. The question you asked, answered directly

**No.** Not in 2 months, not in 10, and 8 months of preparation does not change it,
because the binding constraint is capital and preparation does not create capital.

€3,000/month is €36,000/year. Income from markets is `capital x return`. So:

| sustained annual return | capital required for €36k/yr | realism |
|---|---|---|
| 4% (bonds/cash today) | **€900,000** | safe, and irrelevant to you |
| 7% (global equity long run) | **€514,286** | the number a sensible planner uses |
| 10% (S&P long-run nominal) | **€360,000** | optimistic but defensible |
| 19.8% (**Buffett's lifetime record**) | **€181,818** | the best sustained record in the history of the game |
| 30% | €120,000 | top-decile fund, sustained for years |
| 50% | €72,000 | essentially nobody, sustained |
| 100%, every year, forever | €36,000 | not a thing that exists |

You said you have "near nothing to invest." Take ~€500. What €500 earns:

| return | per year | per month |
|---|---|---|
| 7% (market average) | €35 | **€2.92** |
| 20% (Buffett-level, forever) | €100 | **€8.33** |
| 50% (implausible, sustained) | €250 | **€20.83** |

And compounding €500 up to the €120,000 that would pay €3k/month at an already-elite
30%/yr takes **20.9 years**. At 20%/yr, 30.1 years. At 100%/yr, 7.9 years.

**Your 30% loss tolerance applies to ~€150.** There is no version of "highest ROI
automated investments" that turns €500 into €3,000/month. Anyone who tells you
otherwise is selling you something, and the thing they are selling is usually a
course, a signal service, a prop-firm challenge, or a token.

---

## 2. "Copy millionaires' tactics" — I tested this one properly

You named Pelosi. Your repo has a Pelosi tracker, and I found the v1 pack
(`Jakeschincariol/trader-skill`, 175 tests OK) which contains `trader-copycat`, a
13F reverse-engineer. So there are two "copy the successful" mechanisms. Both have
been studied. Both fail for the same reason: **the information is public precisely
because it is already too late.**

### 2a. Copying a legislator

The most complete study I could find is Belardi (SSRN 7479560, Sept 2026), an event
study on the **entire** Pelosi household record: 65 Periodic Transaction Reports
2014-2026, 227 transactions, 117 discretionary events after cleaning, 68 involving
long call options. Three tests:

* **Timing.** Signed abnormal returns after the trades are **nil at 5, 20 and 60
  sessions**. Over one year, purchases beat the S&P 500 by 15.9% — but the stocks
  *sold* went on to outperform by 24.5%, so **purchases and sales together earn
  nothing** against either benchmark.
* **Disclosure.** **No abnormal volume or return when filings become public**,
  including 2021-2026 when aggregators republish them within hours. That is the
  exact test a copy-trader depends on, and it is flat.
* **Proximity to legislation.** Of 88 act-ticker pairs from 42 federal acts
  affecting the traded stocks, **3** were preceded within 60 days by a trade in the
  expected direction, **against 4.4 expected under random dates**, with 8 preceded
  by a trade in the *opposite* direction. Worse than chance.

The author's conclusion: the household "buys after declines and holds a leveraged,
concentrated position in large-cap technology through a bull market; the record
contains no trace of informed timing," and with ten trades a year on a dozen
tickers that are the object of federal action several times a year, **"coincidence
is the null hypothesis, not the finding."**

Translation: what looked like genius was **leveraged Nasdaq beta during a bull
market**. You can buy that directly, cheaper, with no 45-day lag, and without
pretending it is insight. The STOCK Act allows **up to 45 days** to disclose, and
discloses **ranges, not amounts** — so even if there were signal, you would receive
it late and imprecisely.

### 2b. Copying a fund via 13F

I ran your `trader-copycat` against live SEC EDGAR. `find berkshire` works and
returns CIK `0001067983` (with the current note that Buffett is Chairman Emeritus
since 2026-09-18 and Greg Abel CEO since 2026-01-01). The `copy` command **refused
to run** because SEC policy requires a User-Agent containing *your* name and email;
I did not invent an identity for a government endpoint. Set `SEC_USER_AGENT` and it
will work.

But note what a 13F is: **due 45 calendar days after quarter end** (SEC Rule
13f-1(a)(1), confirmed on sec.gov). A position held on 30 September is disclosed by
14 November. It is a **snapshot, not a stream**: it omits short positions, non-US
holdings, cash, fixed income, and anything granted confidential treatment. You
would be cloning a portfolio as it was six weeks ago, minus every part of it that
is not a long US equity.

The genuinely useful thing `trader-copycat` gives you is not alpha. It is a
**cheap, disciplined way to hold a concentrated quality portfolio you did not have
to pick**, sized by your own `trader-budget`. That is a legitimate use. It is not a
money machine, and its expected return is the market's.

---

## 3. I ran your agents on the strategies you were shown

This is the part where your own repo earns its keep. `trader-labs` pooled each
published rule across **6 liquid instruments** on live Yahoo data (60 sessions each):

### The EMA-12 flip ("508%, 57% win rate")

| symbol | trades | win % | avg R | total R | t |
|---|---|---|---|---|---|
| QQQ | 60 | 8.3% | −0.8677 | −52.06 | −16.48 |
| SPY | 60 | 10.0% | −0.7987 | −47.92 | −10.56 |
| TSLA | 60 | 15.0% | −0.7391 | −44.35 | −9.51 |
| NVDA | 60 | 6.7% | −0.8599 | −51.59 | −12.67 |
| AMD | 60 | 6.7% | −0.8517 | −51.10 | −12.45 |
| IWM | 60 | 18.3% | −0.5976 | −35.86 | −5.44 |
| **pooled** | **360** | **10.8%** | **−0.7858** | **−282.88** | **−24.75** |

It loses on **every single instrument**, with |t| between 5.4 and 16.5 individually
and **t = −24.75 pooled**. That is not bad luck. That is a rule that reliably
destroys money, and more data will not rescue it. The claimed 57% win rate is not
reachable at a 3xATR trail: sweeping the parameter gives 0.0% → 8.3% → 46.7% → 51.7%
at k = 1.5 → 3 → 6 → 10, so the published win rate belongs to a **different rule
than the one described**.

### The level breakout ("313R, best of 1,380 variants")

| symbol | trades | win % | avg R | total R | t |
|---|---|---|---|---|---|
| QQQ | 43 | 27.9% | +0.0863 | +3.71 | 0.31 |
| SPY | 39 | 23.1% | −0.0247 | −0.96 | −0.08 |
| TSLA | 40 | 35.0% | +0.0851 | +3.40 | 0.33 |
| NVDA | 39 | 17.9% | −0.4779 | −18.64 | −2.40 |
| AMD | 42 | 23.8% | −0.1816 | −7.63 | −0.72 |
| IWM | 37 | 32.4% | +0.2366 | +8.76 | 0.75 |
| **pooled** | **240** | **26.7%** | **−0.0473** | **−11.36** | **−0.43** |

The **win rate replicates almost exactly** (26.7% measured vs "lost almost three out
of four" claimed). The **edge does not exist**: −0.0473R a trade, t = −0.43. The
mechanics are real; the profitability is not.

### And the reason "best of 1,380" is not a result

The best of N noisy results sits about `sqrt(2 ln N)` standard deviations above the
pack **from luck alone**: **3.80 sigma at N = 1,380**. Demonstrated on a pure random
walk with 15 variants: the single positive in-sample row (+0.0371R, t = 0.2) went to
**−0.3108R** out of sample. The author of that video told you this himself — +99R
out-of-sample, then **−107R** on the next window. That is the most honest sentence
in either transcript.

### The base rate, from the primary source

Chague, De-Losso & Giovannetti, *"Day Trading for a Living?"* (SSRN 3423101), which
observed **every individual who began day trading between 2013 and 2015 in the
Brazilian equity futures market** (third in the world by volume):

> "We show that it is virtually impossible for individuals to day trade for a living,
> contrary to what course providers claim... **97% of all individuals who persisted
> for more than 300 days lost money. Only 1.1% earned more than the Brazilian minimum
> wage and only 0.5% earned more than the initial salary of a bank teller** — all with
> great risk."

That is not a survey of people who complained. It is a census. Your plan is to be in
the 1.1%, part-time, with no capital, in a market where you are the counterparty to
firms that spend more on latency than you will earn in a decade.

---

## 4. The hybrid model that actually fits your inputs

You asked for a hybrid model of automated investments. Here is one that is honest.
The automation goes where automation genuinely wins (boring, disciplined,
low-decision), and your 15 hours go where hours genuinely win (services).

### Layer 1 — Income engine: services. Target: €3k/month. Owner: your hours.

This is the only layer that can produce €3,000/month on €500 of capital. Ranked in
my previous analysis: **(1) productized repo-audit / verification report,
(2) AI-agent & automation freelancing, (3) technical writing.** French micro-
entreprise BNC: ceiling €83,600 CA, social charges **25.6%** from 01/01/2026, ACRE
**12.8%** until end of Q3 after start (**but the exemption drops from 50% to 25% for
creations from 01/07/2026**), CFP 0.2%, no France Travail unemployment rights.

### Layer 2 — Automated investing: the surplus, not the engine. Owner: a standing order.

This is what "automated investments" should mean for you:
* Open a **PEA now with €10**. Its favourable tax treatment has a **5-year clock that
  starts at opening, not at contribution**, and you have a Switzerland move planned.
  This is the single highest-value financial action available to you this week and it
  costs €10.
* Then a **monthly standing order** into one diversified UCITS ETF (global equity),
  funded from Layer 1's surplus, never from borrowed money, never redirected to
  trading. Automation's real edge is behavioural: it removes the decision.
* French flat tax (PFU) on securities gains is reported at **31.4% for 2026**
  (12.8% income tax + 18.6% social levies), up from 30% — **verify the current rate
  before you rely on it.**
* Switzerland: private capital gains on movable assets are **generally tax-free** for
  genuine private investors, but there is an annual **wealth tax**, standard VAT is
  **8.1%**, and if you trade frequently enough to be classed a **professional
  securities dealer** you lose that exemption and pay income tax plus social
  contributions on it. **Active day trading is precisely what risks that
  classification.** The tax system punishes the exact plan you proposed.

### Layer 3 — The agents as a research lab. Cost: €0. Income: indirect.

Keep all 12 agents. Use them for what they are actually good at:
* **Paper trading only.** The pack defaults to `"paper": true` and cannot place an
  order without a risk PASS plus your typed yes plus Claude's Allow-once card.
* **`trader-console evidence`** across a basket before you believe any rule, ever.
  It just told you the EMA rule is −282.88R at t = −24.75. That single command is
  worth more than every trading course you will ever be sold.
* **Publish the results.** "I built a backtester and ran a viral 508% strategy across
  6 ETFs; here is the −24.75 t-statistic" is a better portfolio piece, a better
  technical-writing sample and a better lead magnet for Layer 1 than any trading P&L
  you will produce this year. **Layer 3 funds Layer 1 with reputation, not with
  market returns.**

### What I will not build, and why

An "automated investment system" that trades your money at the highest possible ROI.
It does not exist. What exists is: automated execution of a rule with a *verified*
edge (you have none — I tested two), or automated execution of a rule with no edge
(guaranteed slow loss minus costs), or leverage on top of either (faster). Building
you a polished UI for the second option would be the most harmful thing I could do
with an afternoon.

---

## 5. Eight months, month by month

| month | Layer 1 (12 h/wk) | Layer 2 (0.5 h/wk) | Layer 3 (2.5 h/wk) | exit test |
|---|---|---|---|---|
| 1 | Register micro-entreprise + ACRE. Publish the −282.88R write-up. Package the audit at €600. 30 outreach messages. | **Open the PEA with €10.** | Set `SEC_USER_AGENT`, run copycat, paper-trade one rule | none; €0 expected |
| 2 | 30 more messages. 2 published analyses. First discovery calls. | Standing order starts, any amount | `evidence` across 10 instruments; publish | **<2 calls booked → change the buyer, not the career** |
| 3 | First paid gig of any size. Raise nothing yet. | — | Publish the 13F-lag explainer | **€0 and <5 calls → shift 6 h/wk to cash work (local/part-time), keep 6 h on Layer 1** |
| 4-6 | 3 reference clients. Price to €800-1,200 per audit. | Increase standing order with surplus | One deep-dive a month; these are your samples | **€0 by month 6 after 100+ outreaches → Layer 1 is not converting; employment becomes plan A** |
| 7-9 | First retainer. First referral (the real signal). €1,500-2,500/mo. | — | Consider the honest-backtest channel; it compounds slowly | >70% of hours on delivery with no price rise → raise 25% |
| 10 | €2,000-3,000/mo run rate. Decide: Switzerland, subcontract, or productize the harness. | Review ETF/PEA before any move | — | **<€1,200/mo → the €3k target is 24 months away, not 10. Extend, do not add leverage or trading.** |

**Your "3 months of nothing and I change tactic" trigger is set in the wrong place.**
Months 1-3 are *always* nothing in services. Keep a 3-month checkpoint but measure a
**leading indicator** (calls booked, proposals sent, pieces published), and put the
revenue trigger at **month 6**.

---

## 6. Red flags, specific to what you proposed

| what you said | why it is a trap |
|---|---|
| "highest ROI possible" | ROI is a ratio. At €500 the numerator is ~€35/year at market returns. "Highest ROI" at your scale means "highest variance", and variance with no capital and no income is ruin, not upside. |
| "automated investments" | Automation removes the human from a decision. If the decision has no edge, automation makes you lose **faster and more reliably**, and it removes the pause where you would have noticed. |
| "copy millionaires' tactics" | Their tactics are visible *after* 45 days and their returns are mostly beta. Belardi: no abnormal return at disclosure, sales outperformed purchases, 3 proximity hits against 4.4 expected by chance. |
| "lower my fail rate as much as possible" | Your agents already lower it to the floor: `require_stop`, paper-by-default, risk PASS bound to the exact order and day, market-calendar refusal. The residual 97% is not a tooling problem. |
| "3k/month in 2 months" | Needs €181,818 at Buffett's lifetime rate, or €514,286 at the market's. You have ~€500. |
| "8 months to get everything ready" | Preparation is not the constraint. Pipeline is. Eight months of preparation with zero outreach produces a beautiful system and €0. |

**Also, France-specific:** publishing investment recommendations *for payment* can
require regulatory authorisation, and "conseil en investissements financiers" is a
regulated activity. Debunking with your own numbers is education and journalism.
Telling people what to buy, for money, is not. Keep the disclaimer your own SKILL.md
already enforces.

---

## 7. Reproduce every number above

```bash
cd /home/user/trader-console
python3 console.py agents
python3 console.py evidence QQQ,SPY,TSLA,NVDA,AMD,IWM --strategy ema12-flip
python3 console.py evidence QQQ,SPY,TSLA,NVDA,AMD,IWM --strategy level-breakout --target-r 4
python3 console.py pipeline TSLA --now "2026-10-19 10:16" --budget 5000
python3 console.py ask "copy buffett from his 13f"

cd /home/user/trader-agents
python3 -m unittest discover -s tests          # 369 tests
cd /home/user/trader-console
python3 -m unittest discover -s . -p test_console.py   # 24 tests
```

**Verify before relying on:** the 2026 PFU rate (31.4% per multiple 2026 sources,
confirm on impots.gouv.fr), the BNC charge rate (25.6% per economie.gouv.fr dated
06/03/2026 and URSSAF; one secondary source still said 24.6%), the ACRE change on
01/07/2026, the micro-BNC ceiling (€83,600 per URSSAF and service-public; one
secondary source claimed €37,500 and appears outdated), the Swiss professional-dealer
criteria, and whether a French micro-entreprise gives you any right to work while
Swiss-resident. All tax figures move.

**Limitations of my own testing:** 60 sessions per instrument, six instruments, no
commission, no spread, no slippage, no borrow cost, no partial fills, and Yahoo's
free endpoint is unofficial and can lag. The EMA result (t = −24.75) is far too large
for those caveats to reverse it. The level-breakout result (t = −0.43) would need a
much longer window to distinguish from zero — but "we cannot confirm an edge" is not
a reason to trade one.
