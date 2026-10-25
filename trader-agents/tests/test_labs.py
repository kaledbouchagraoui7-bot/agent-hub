"""Tests for trader-labs. Offline, deterministic, no network.

The two fixtures are synthetic and seeded (tests/make_labs_fixtures.py):
  labs-noedge-5m.json.gz  a pure random walk. Nothing may find an edge here.
  labs-trend-5m.json.gz   the same walk plus a persistent per-day drift, so a
                          trend-following rule should be able to see something.
That pair is what makes these tests meaningful: an engine that finds an edge in
noise is broken, and an engine that cannot find a planted one is broken too.
"""

import datetime
import gzip
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from _load import load, FIX

labs = load("trader-labs", "labs")

LABS_FIX = os.path.join(FIX, "trader-labs")
NOEDGE = os.path.join(LABS_FIX, "labs-noedge-5m.json.gz")
TREND = os.path.join(LABS_FIX, "labs-trend-5m.json.gz")
SPLIT = "2026-07-31"


def chart(path):
    return labs.load_offline(path)


class Indicators(unittest.TestCase):
    def test_ema_seeds_with_sma_and_is_lagged(self):
        got = labs.ema([1.0, 2.0, 3.0, 4.0], 3)
        self.assertIsNone(got[0])
        self.assertIsNone(got[1])
        self.assertAlmostEqual(got[2], 2.0, places=10)      # SMA of 1,2,3
        self.assertAlmostEqual(got[3], 3.0, places=10)      # 4*0.5 + 2*0.5

    def test_ema_of_a_flat_series_is_that_flat_value(self):
        got = labs.ema([5.0] * 30, 12)
        self.assertTrue(all(abs(v - 5.0) < 1e-12 for v in got[11:]))

    def test_ema_rejects_a_silly_period(self):
        with self.assertRaises(labs.LabsError):
            labs.ema([1.0, 2.0], 0)

    def test_atr_equals_the_range_when_every_bar_is_identical(self):
        bars = [{"high": 11.0, "low": 10.0, "close": 10.5} for _ in range(30)]
        got = labs.atr(bars, 14)
        self.assertIsNone(got[12])
        self.assertAlmostEqual(got[13], 1.0, places=10)
        self.assertAlmostEqual(got[29], 1.0, places=10)

    def test_atr_uses_the_previous_close_in_true_range(self):
        bars = [{"high": 11.0, "low": 10.0, "close": 10.5}] * 14
        bars.append({"high": 20.0, "low": 19.0, "close": 19.5})   # gaps away from 10.5
        got = labs.atr(bars, 14)
        self.assertGreater(got[14], 1.0)                          # TR of the gap bar is 9.5

    def test_t_stat_and_selection_inflation(self):
        self.assertAlmostEqual(labs.selection_inflation_sigma(1380), 3.8026, delta=0.001)
        self.assertEqual(labs.selection_inflation_sigma(1), 0.0)
        self.assertEqual(labs.t_stat([1.0] * 10), 0.0)   # zero variance -> no t, not a crash
        self.assertEqual(labs.t_stat([]), 0.0)
        self.assertGreater(labs.t_stat([0.5, 0.6, 0.4, 0.55, 0.45, 0.5, 0.52, 0.48]), 2.0)


class EngineHonesty(unittest.TestCase):
    """The rules the SKILL.md promises, checked against hand-built bars."""

    def _bars(self, day, rows):
        out = []
        for i, (o, h, l, c) in enumerate(rows):
            minute = 9 * 60 + 30 + i * 5
            ny = datetime.datetime.combine(day, datetime.time(0, 0)) + datetime.timedelta(minutes=minute)
            out.append({"ts": 1792416600 + i * 300, "ny": ny, "date": day, "minute": minute,
                        "open": o, "high": h, "low": l, "close": c, "volume": 1000})
        return out

    def test_bar_interval_is_inferred_from_the_timestamps(self):
        day = datetime.date(2026, 10, 19)
        self.assertEqual(labs.interval_of(self._bars(day, [(1, 1, 1, 1)] * 4)), 5)

    def test_stop_is_checked_before_the_target_in_the_same_bar(self):
        day = datetime.date(2026, 10, 19)
        rows = [(100.0, 100.5, 99.5, 100.0)]               # one bar is the whole opening range
        rows.append((100.0, 100.9, 100.6, 100.8))          # closes above 100.5: the entry
        rows.append((100.8, 101.7, 100.5, 101.6))          # one bar touches target AND stop
        rows.append((101.6, 101.8, 101.0, 101.5))          # never reached
        bt_bars = self._bars(day, rows)
        tr = labs.run_level_breakout(bt_bars, or_minutes=5, target_r=4.0)
        self.assertIsNotNone(tr)
        self.assertEqual(tr["why"], "stop")
        self.assertEqual(tr["r"], -1.0)

    def test_trailing_stop_never_uses_the_bar_it_is_protecting(self):
        """A bar that spikes up and then closes back down must not raise the stop
        that the very same bar is allowed to hit."""
        day = datetime.date(2026, 10, 19)
        rows = [(100.0, 100.2, 99.8, 100.0)] * 20          # quiet, seeds EMA and ATR
        rows.append((100.0, 101.5, 99.9, 101.4))           # up flip: the entry at 101.4
        rows.append((101.4, 110.0, 90.0, 91.0))            # huge spike both ways, closes down
        tr = labs.run_ema_flip(self._bars(day, rows), ema_period=12, atr_period=14, atr_k=3.0)
        self.assertIsNotNone(tr)
        self.assertEqual(tr["side"], "buy")
        # the stop enforced during that bar was ratcheted at the ENTRY bar's close,
        # so it cannot be anywhere near the 110 high of the bar that hit it
        self.assertLess(tr["exit"], 105.0)
        self.assertEqual(tr["r"], -1.0)

    def test_entry_is_the_close_of_the_signal_bar(self):
        day = datetime.date(2026, 10, 19)
        rows = [(100.0, 100.5, 99.5, 100.0)]
        rows.append((100.0, 100.9, 100.6, 100.8))
        rows.append((100.8, 100.9, 100.7, 100.85))
        tr = labs.run_level_breakout(self._bars(day, rows), or_minutes=5, target_r=4.0)
        self.assertEqual(tr["entry"], 100.8)
        self.assertEqual(tr["stop0"], 100.6)                # the low of the signal candle
        self.assertAlmostEqual(tr["risk"], 0.2, places=6)
        self.assertAlmostEqual(tr["target"], 100.8 + 4 * 0.2, places=4)

    def test_a_doji_signal_bar_is_refused_because_r_would_be_meaningless(self):
        day = datetime.date(2026, 10, 19)
        rows = [(100.0, 100.5, 99.5, 100.0),                # the whole opening range
                (100.0, 100.6, 100.59, 100.6),              # closes above, but the candle has no body
                (100.6, 100.62, 100.4, 100.5)]              # closes back inside: no second signal
        tr = labs.run_level_breakout(self._bars(day, rows), or_minutes=5, target_r=4.0)
        self.assertIsNone(tr, "a near-zero-risk signal bar must not produce a trade with a huge R")

    def test_the_min_risk_guard_is_a_parameter_not_a_hardcode(self):
        day = datetime.date(2026, 10, 19)
        rows = [(100.0, 100.5, 99.5, 100.0),
                (100.0, 100.6, 100.59, 100.6),
                (100.6, 100.62, 100.4, 100.5)]
        bars = self._bars(day, rows)
        self.assertIsNone(labs.run_level_breakout(bars, or_minutes=5, min_risk_bps=5.0))
        tr = labs.run_level_breakout(bars, or_minutes=5, min_risk_bps=0.0)
        self.assertIsNotNone(tr)                            # same bars, guard off, trade appears
        self.assertAlmostEqual(tr["risk"], 0.01, places=6)
        self.assertEqual(tr["r"], -1.0)
        # ...and the next bar's low took out a 1bp stop at once. That is exactly why
        # the guard exists: a hair-thin signal bar makes R a number nobody can trade.

    def test_long_only_never_opens_a_short(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "ema12-flip", is_until=SPLIT)
        self.assertTrue(bt["trades"])
        self.assertEqual({t["side"] for t in bt["trades"]}, {"buy"})

    def test_allow_short_opens_the_other_side(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "ema12-flip", is_until=SPLIT, allow_short=True)
        self.assertIn("sell", {t["side"] for t in bt["trades"]})

    def test_weekends_and_holidays_are_not_sessions(self):
        ch = chart(NOEDGE)
        days = set(labs.sessions(ch))
        self.assertTrue(days)
        for d in days:
            self.assertLess(d.weekday(), 5)
            self.assertNotIn(d.isoformat(), labs.HOLIDAYS)

    def test_no_trade_is_open_past_the_close(self):
        ch = chart(TREND)
        for strat in ("ema12-flip", "level-breakout"):
            bt = labs.backtest(ch, strat, is_until=SPLIT)
            for t in bt["trades"]:
                self.assertLessEqual(labs.parse_clock(t["exit_time"], "exit"), labs.CLOSE_MIN)


class Statistics(unittest.TestCase):
    def test_no_edge_fixture_yields_no_edge(self):
        """The most important test here. A backtester that finds an edge in a pure
        random walk is lying, whatever it says afterwards."""
        ch = chart(NOEDGE)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        st = labs.stats(bt["in_sample"])
        self.assertGreater(st["trades"], 60)
        self.assertLess(abs(st["avg_r"]), 0.15)
        self.assertLess(abs(st["t_stat"]), 2.0, "a random walk must not look significant")

    def test_planted_edge_is_found_and_survives_the_split(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        i, o = labs.stats(bt["in_sample"]), labs.stats(bt["out_of_sample"])
        self.assertGreater(i["trades"], 40)
        self.assertGreater(i["avg_r"], 0.5)
        self.assertGreater(i["t_stat"], 2.0)
        self.assertGreater(o["trades"], 20)
        self.assertGreater(o["avg_r"], 0.0, "a real edge should still be positive out of sample")

    def test_r_multiples_are_exact(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        for t in bt["trades"]:
            if t["why"] == "stop":
                self.assertEqual(t["r"], -1.0)
            elif t["why"].startswith("target"):
                self.assertAlmostEqual(t["r"], 4.0, places=4)
            expected = (t["exit"] - t["entry"]) / t["risk"]
            self.assertAlmostEqual(t["r"], round(expected, 4), places=4)

    def test_profit_factor_and_drawdown_are_consistent(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        st = labs.stats(bt["in_sample"])
        self.assertAlmostEqual(st["gross_win_r"] - st["gross_loss_r"], st["total_r"], delta=0.05)
        self.assertGreaterEqual(st["max_drawdown_r"], 0.0)
        self.assertGreater(st["profit_factor"], 1.0)

    def test_empty_sample_is_reported_not_divided_by_zero(self):
        st = labs.stats([])
        self.assertEqual(st["trades"], 0)
        self.assertIsNone(st["avg_r"])
        self.assertIsNone(st["profit_factor"])
        self.assertIn("NOT ENOUGH DATA", labs.verdict(st, st))

    def test_verdict_calls_out_an_edge_that_dies_out_of_sample(self):
        # a constant series has zero variance, so t is 0 and nothing is "significant".
        # Use a realistic spread: in-sample clearly positive, out-of-sample negative.
        # 60 trades at +1R and -0.5R: mean +0.25R, sd 0.76, t = 2.26. A big payoff
        # ratio would inflate the sd and hide the significance, which is exactly how
        # a real 4R-target series behaves, so the fixture has to be built deliberately.
        is_tr = [{"r": r, "bars_held": 1} for r in ([1.0] * 30 + [-0.5] * 30)]
        oos_tr = [{"r": r, "bars_held": 1} for r in ([1.0] * 10 + [-0.5] * 50)]
        is_st, oos_st = labs.stats(is_tr), labs.stats(oos_tr)
        self.assertGreater(is_st["t_stat"], 2.0, "the fixture must actually be significant in-sample")
        self.assertLessEqual(oos_st["avg_r"], 0.0)
        v = labs.verdict(is_st, oos_st)
        self.assertIn("fitted to its own sample", v)

    def test_verdict_does_not_call_noise_overfitting(self):
        """A rule with t=0.04 in-sample has no signal. Saying it was 'fitted to its
        own sample' would be a claim about an edge that was never there."""
        ch = chart(NOEDGE)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        v = labs.verdict(labs.stats(bt["in_sample"]), labs.stats(bt["out_of_sample"]))
        self.assertNotIn("fitted to its own sample", v)
        self.assertIn("noise measured twice", v)
        self.assertIn("no edge", v)

    def test_verdict_reports_a_measurable_loss_as_a_finding(self):
        is_st = labs.stats([{"r": -0.7, "bars_held": 1}] * 60)
        oos_st = labs.stats([{"r": -0.9, "bars_held": 1}] * 60)
        v = labs.verdict(is_st, oos_st)
        self.assertIn("loses measurably", v)
        self.assertNotIn("held up", v)

    def test_verdict_flags_an_inconclusive_split(self):
        is_st = labs.stats([{"r": 0.4, "bars_held": 1}, {"r": -0.35, "bars_held": 1}] * 30)
        oos_st = labs.stats([{"r": -0.4, "bars_held": 1}, {"r": 0.45, "bars_held": 1}] * 30)
        v = labs.verdict(is_st, oos_st)
        self.assertTrue("inconclusive" in v or "noise measured twice" in v, v)

    def test_verdict_mentions_the_selection_penalty_for_1380_variants(self):
        st = labs.stats([{"r": 0.5, "bars_held": 1}] * 60)
        v = labs.verdict(st, st, n_variants=1380)
        self.assertIn("1380", v)
        self.assertIn("3.80", v)


class WalkForward(unittest.TestCase):
    def test_the_split_is_clean_and_exhaustive(self):
        ch = chart(TREND)
        bt = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        is_d = {t["date"] for t in bt["in_sample"]}
        oos_d = {t["date"] for t in bt["out_of_sample"]}
        self.assertFalse(is_d & oos_d, "a trade cannot be in both windows")
        self.assertTrue(all(d <= SPLIT for d in is_d))
        self.assertTrue(all(d > SPLIT for d in oos_d))
        self.assertEqual(len(bt["in_sample"]) + len(bt["out_of_sample"]), len(bt["trades"]))

    def test_oos_from_drops_early_out_of_sample_trades(self):
        ch = chart(TREND)
        full = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        cut = labs.backtest(ch, "level-breakout", is_until=SPLIT, oos_from="2026-09-15")
        self.assertLess(len(cut["out_of_sample"]), len(full["out_of_sample"]))
        self.assertTrue(all(t["date"] >= "2026-09-15" for t in cut["out_of_sample"]))

    def test_no_window_leak_the_in_sample_run_cannot_see_later_bars(self):
        ch = chart(TREND)
        whole = labs.backtest(ch, "level-breakout")
        split = labs.backtest(ch, "level-breakout", is_until=SPLIT)
        early_whole = [t for t in whole["trades"] if t["date"] <= SPLIT]
        self.assertEqual([ (t["date"], t["entry"], t["r"]) for t in early_whole],
                         [ (t["date"], t["entry"], t["r"]) for t in split["in_sample"]])


class SelectionBias(unittest.TestCase):
    def test_the_best_variant_beats_the_median_on_noise(self):
        """Pick the best of 27 parameter sets on a random walk and it looks great
        in-sample. That is the whole point of the variants command."""
        ch = chart(NOEDGE)
        res = labs.run_variants(ch, "ema12-flip", is_until=SPLIT)
        s = res["summary"]
        self.assertEqual(s["variants"], 36)
        best_is = s["best_in_sample"]["in_sample"]["avg_r"]
        self.assertGreater(best_is, s["median_in_sample_avg_r"])
        self.assertAlmostEqual(s["expected_luck_sigma"], 2.67, delta=0.02)   # sqrt(2 ln 36)

    def test_the_grid_matches_the_documented_shape(self):
        self.assertEqual(len(labs.variant_grid("ema12-flip")), 36)       # 3 EMAs x 3 ATRs x 4 k
        self.assertEqual(len(labs.variant_grid("level-breakout")), 15)   # 3 ranges x 5 targets
        self.assertIn({"or_minutes": 5, "target_r": 4.0}, labs.variant_grid("level-breakout"))
        self.assertIn({"ema_period": 12, "atr_period": 14, "atr_k": 3.0},
                      labs.variant_grid("ema12-flip"))


class DataLoading(unittest.TestCase):
    def test_gzip_fixture_loads_with_the_right_shape(self):
        ch = chart(TREND)
        self.assertEqual(ch["symbol"], "LABS")
        self.assertEqual(len(ch["bars"]), 15600)
        b = ch["bars"][0]
        for k in ("ts", "ny", "date", "minute", "open", "high", "low", "close", "volume"):
            self.assertIn(k, b)
        self.assertEqual(b["minute"], 9 * 60 + 30)

    def test_a_folder_of_charts_is_merged_and_deduplicated(self):
        d = tempfile.mkdtemp(prefix="labs-folder-")
        self.addCleanup(shutil.rmtree, d, True)
        with gzip.open(NOEDGE, "rt", encoding="utf-8") as fh:
            text = fh.read()
        for name in ("a.json", "b.json"):                 # the same file twice
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        ch = labs.load_offline(d)
        self.assertEqual(len(ch["bars"]), 15600)            # no duplicated bars

    def test_a_chart_for_another_symbol_is_refused(self):
        with self.assertRaises(labs.LabsError):
            labs.load_offline(NOEDGE, sym="TSLA")

    def test_garbage_input_gives_a_plain_error_not_a_traceback(self):
        d = tempfile.mkdtemp(prefix="labs-bad-")
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "x.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("this is not json")
        with self.assertRaises(labs.LabsError):
            labs.load_offline(p)
        with self.assertRaises(labs.LabsError):
            labs.load_offline(os.path.join(d, "missing.json"))

    def test_bars_with_nulls_are_skipped(self):
        payload = {"chart": {"result": [{
            "meta": {"symbol": "NUL", "dataGranularity": "5"},
            "timestamp": [1792416600, 1792416900, 1792417200],
            "indicators": {"quote": [{"open": [100.0, None, 101.0], "high": [101.0, None, 102.0],
                                      "low": [99.0, None, 100.0], "close": [100.5, None, 101.5],
                                      "volume": [1000, None, 1000]}]}}], "error": None}}
        ch = labs.parse_chart(json.dumps(payload), "NUL")
        self.assertEqual(len(ch["bars"]), 2)


class Claims(unittest.TestCase):
    def test_no_claim_is_presented_as_a_fact(self):
        self.assertTrue(labs.CLAIMS)
        for c in labs.CLAIMS:
            for k in ("id", "strategy", "claim", "source", "why", "what_would_check_it",
                      "verifiable_with_free_data"):
                self.assertIn(k, c)
            self.assertIn(c["strategy"], labs.STRATEGIES)
        ids = [c["id"] for c in labs.CLAIMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_reported_oos_collapse_is_recorded(self):
        c = [x for x in labs.CLAIMS if x["id"] == "level-oos"][0]
        self.assertIn("-107R", c["claim"])
        self.assertIn("+99R", c["claim"])


class SkillFile(unittest.TestCase):
    """The house contract, applied to the new skill on its own terms."""

    def setUp(self):
        root = os.path.dirname(FIX)
        self.path = os.path.join(os.path.dirname(root), "trader-labs", "SKILL.md")
        with open(self.path, encoding="utf-8") as fh:
            self.text = fh.read()

    def test_frontmatter_has_a_name_a_long_description_and_a_hint(self):
        import re
        m = re.match(r"^---\n(.*?)\n---\n", self.text, re.S)
        self.assertTrue(m, "SKILL.md must open with frontmatter")
        fm = m.group(1)
        self.assertIn("name: trader-labs\n", fm + "\n")
        self.assertIn("description:", fm)
        self.assertIn("argument-hint:", fm)
        self.assertGreater(len(fm), 200, "description is too thin to route on")

    def test_carries_the_safety_rule_like_every_order_path_skill(self):
        low = " ".join(self.text.lower().split())
        self.assertIn("not financial advice", low)
        self.assertIn("yes", low)

    def test_no_em_dashes(self):
        self.assertNotIn("\u2014", self.text)

    def test_documents_what_it_cannot_do(self):
        low = self.text.lower()
        self.assertIn("60 days", low)
        self.assertIn("commission", low)
        self.assertIn("places nothing", low)

    def test_is_long_enough_to_be_a_manual_not_a_stub(self):
        self.assertGreater(len(self.text.splitlines()), 60)


class Cli(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = labs.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_run_json_is_machine_readable_and_carries_the_disclaimer(self):
        rc, out, _ = self.run_cli(["run", "--strategy", "level-breakout", "--symbol", "LABS",
                                   "--offline", TREND, "--is-until", SPLIT, "--json"])
        self.assertEqual(rc, 0)
        d = json.loads(out)
        self.assertEqual(d["strategy"], "level-breakout")
        self.assertGreater(d["in_sample"]["trades"], 40)
        self.assertIn("not financial advice", d["disclaimer"].lower())
        self.assertTrue(all(not k.startswith("_") for t in d["trades"] for k in t))

    def test_run_report_mentions_it_placed_nothing(self):
        rc, out, _ = self.run_cli(["run", "--strategy", "ema12-flip", "--symbol", "LABS",
                                   "--offline", NOEDGE, "--is-until", SPLIT])
        self.assertEqual(rc, 0)
        low = out.lower()
        self.assertIn("nothing was placed", low)
        self.assertIn("not financial advice", low)

    def test_variants_prints_the_median_next_to_the_best(self):
        rc, out, _ = self.run_cli(["variants", "--strategy", "level-breakout", "--symbol", "LABS",
                                   "--offline", NOEDGE, "--is-until", SPLIT, "--show", "5"])
        self.assertEqual(rc, 0)
        self.assertIn("median", out.lower())
        self.assertIn("luck alone", out.lower())

    def test_rank_prints_a_table_for_both_strategies(self):
        rc, out, _ = self.run_cli(["rank", "--symbol", "LABS", "--offline", NOEDGE,
                                   "--is-until", SPLIT])
        self.assertEqual(rc, 0)
        self.assertIn("ema12-flip", out)
        self.assertIn("level-breakout", out)

    def test_claims_lists_the_published_numbers_with_their_caveats(self):
        rc, out, _ = self.run_cli(["claims"])
        self.assertEqual(rc, 0)
        self.assertIn("508", out)
        self.assertIn("1,380", out)
        self.assertIn("not financial advice", out.lower())

    def test_unknown_strategy_is_rejected_by_the_parser(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_cli(["run", "--strategy", "moon-shot", "--symbol", "LABS", "--offline", TREND])
        self.assertEqual(cm.exception.code, 2)

    def test_a_missing_offline_file_exits_1_with_one_plain_line(self):
        rc, _, err = self.run_cli(["run", "--strategy", "ema12-flip", "--symbol", "LABS",
                                   "--offline", os.path.join(tempfile.gettempdir(), "nope-xyz.json")])
        self.assertEqual(rc, 1)
        self.assertIn("labs.py:", err)
        self.assertEqual(len([l for l in err.strip().splitlines() if l.strip()]), 1,
                         "the house style is one plain line, not a traceback")

    def test_a_data_error_is_never_a_traceback(self):
        d = tempfile.mkdtemp(prefix="labs-err-")
        self.addCleanup(shutil.rmtree, d, True)
        bad = os.path.join(d, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{\"chart\": {\"result\": [], \"error\": {\"description\": \"no data\"}}}")
        rc, _, err = self.run_cli(["run", "--strategy", "ema12-flip", "--symbol", "LABS", "--offline", bad])
        self.assertEqual(rc, 1)
        self.assertNotIn("Traceback", err)

    def test_no_command_prints_help(self):
        rc, out, _ = self.run_cli([])
        self.assertEqual(rc, 1)
        self.assertIn("usage:", out.lower())

    def test_write_creates_the_file_and_its_folder(self):
        d = tempfile.mkdtemp(prefix="labs-out-")
        self.addCleanup(shutil.rmtree, d, True)
        target = os.path.join(d, "trader", "labs.json")
        rc, out, _ = self.run_cli(["run", "--strategy", "level-breakout", "--symbol", "LABS",
                                   "--offline", TREND, "--is-until", SPLIT, "--write", target])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.isfile(target))
        with open(target, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["strategy"], "level-breakout")
        self.assertIn("in_sample", saved)
        self.assertTrue(all(not k.startswith("_") for t in saved["trades"] for k in t))


if __name__ == "__main__":
    unittest.main(verbosity=2)
