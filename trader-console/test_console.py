"""Tests for the trader console. The safety ones matter more than the rest."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import console  # noqa: E402

# tests must never append to the real audit log
_TMPLOG = tempfile.mkdtemp(prefix="console-tests-")
console.LOG = os.path.join(_TMPLOG, "test-log.jsonl")


def call(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = console.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


class Discovery(unittest.TestCase):
    def test_paths_are_derived_not_hardcoded(self):
        """Regression, tested as a PROPERTY not as a syntax shape: no absolute
        workspace path may be baked into the file. A hardcoded literal silently
        stops resolving when the tree is moved, mounted or copied, and discovery
        then reports 'nothing installed' instead of the truth."""
        with open(os.path.join(HERE, "console.py"), encoding="utf-8") as fh:
            src = fh.read()
        root = os.path.dirname(os.path.dirname(HERE))       # the workspace, at runtime
        code = [l for l in src.splitlines()
                if l.strip() and not l.strip().startswith("#")]
        offenders = [l.strip() for l in code if root in l]
        self.assertEqual(offenders, [],
                         "console.py hardcodes an absolute workspace path: %s" % offenders)
        # and the roots really are derived from this file's own location
        self.assertIn("os.path.abspath(__file__)", src)
        self.assertTrue(os.path.isabs(console.V2) and os.path.isabs(console.V1))

    def test_pack_resolution_survives_being_moved(self):
        """The resolver must find a pack root wherever the tree is copied, and must
        prefer an env override. Tested with a throwaway fake pack."""
        d = tempfile.mkdtemp(prefix="console-move-")
        self.addCleanup(shutil.rmtree, d, True)
        fake = os.path.join(d, "anywhere", "trader-agents", "trader-x")
        os.makedirs(fake)
        with open(os.path.join(fake, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: trader-x\ndescription: y\n---\n# x\n")
        found = console._first_existing([os.path.join(d, "anywhere", "trader-agents"),
                                         os.path.join(d, "nope")])
        self.assertEqual(found, os.path.join(d, "anywhere", "trader-agents"))
        # a directory that exists but holds no skills must NOT be accepted
        empty = os.path.join(d, "empty")
        os.makedirs(empty)
        self.assertEqual(console._first_existing([empty]), empty)   # falls through to candidates[0]
        self.assertEqual(console._first_existing([empty, found]), found)

    def test_both_packs_are_found_and_v2_wins_the_overlap(self):
        a = console.agents()
        self.assertIn("trader-labs", a)
        self.assertEqual(a["trader-labs"]["pack"], "v2-day-trader")
        # these names exist in BOTH packs; the newer v2 tool must be the one wired
        for s in ("trader-alerts", "trader-analyst", "trader-broker", "trader-budget",
                  "trader-news", "trader-pelosi", "trader-risk"):
            if os.path.isdir(console.V1) and os.path.isfile(
                    os.path.join(console.V1, s, "SKILL.md")):
                self.assertEqual(a[s]["pack"], "v2-day-trader",
                                 "%s must resolve to the v2 day-trading tool" % s)

    def test_v1_only_skills_are_contributed(self):
        a = console.agents()
        if os.path.isdir(console.V1):
            for s in ("trader-copycat", "trader-screener", "trader-rebalance", "trader-tax"):
                if os.path.isdir(os.path.join(console.V1, s)):
                    self.assertIn(s, a)
                    self.assertEqual(a[s]["pack"], "v1-investor")

    def test_a_missing_root_raises_instead_of_silently_returning_empty(self):
        console._CACHE = None
        old2, old1 = console.V2, console.V1
        try:
            console.V2 = os.path.join(tempfile.gettempdir(), "definitely-not-here-1")
            console.V1 = os.path.join(tempfile.gettempdir(), "definitely-not-here-2")
            with self.assertRaises(RuntimeError) as cm:
                console.agents()
            self.assertIn("no agents found", str(cm.exception))
        finally:
            console.V2, console.V1 = old2, old1
            console._CACHE = None


class Routing(unittest.TestCase):
    def test_strategy_questions_route_to_labs(self):
        for q in ("does the ema12 rule actually work", "is this overfitted",
                  "backtest this strategy", "did it hold up out of sample"):
            name, skills = console.route(q)
            self.assertEqual(name, "does-it-work", q)
            self.assertEqual(skills, ["trader-labs"], q)

    def test_congress_routes_to_pelosi(self):
        name, skills = console.route("what did pelosi file this year")
        self.assertEqual(name, "congress")
        self.assertIn("trader-pelosi", skills)

    def test_copy_investor_routes_to_copycat(self):
        name, skills = console.route("copy buffett from his 13f")
        self.assertEqual(name, "copy-investor")
        self.assertIn("trader-copycat", skills)

    def test_order_language_routes_to_the_broker_but_only_its_read_only_command(self):
        name, skills = console.route("place the order for TSLA")
        self.assertEqual(name, "ticket")
        self.assertEqual(skills, ["trader-broker"])
        argv, note = console.build_command("trader-broker", "place the order for TSLA")
        self.assertIn("show", argv)
        self.assertIn("read-only", note)

    def test_ticker_and_budget_extraction(self):
        self.assertEqual(console.extract_tickers("size TSLA and NVDA now"), ["TSLA", "NVDA"])
        self.assertEqual(console.extract_tickers("what is my R"), [])       # 'R' is a stopword
        self.assertEqual(console.extract_budget("i have $5,000 to trade"), 5000.0)
        self.assertEqual(console.extract_budget("with 2500 euros"), 2500.0)
        self.assertIsNone(console.extract_budget("no numbers here"))

    def test_an_unmatched_question_falls_back_rather_than_crashing(self):
        name, skills = console.route("hello there")
        self.assertEqual(name, "general")
        self.assertIsInstance(skills, list)


class SafetyWhitelist(unittest.TestCase):
    """The console must never be able to reach an order-mutating command."""

    def test_no_broker_command_can_carry_a_mutating_verb(self):
        mutating = ("approve", "decline", "result", "fill", "flatten", "log")
        questions = ["place the order", "approve order 1", "fill it", "flatten my position",
                     "show the ticket", "send it to my broker", "execute now",
                     "log the result", "decline that order", "buy it", "close my position"]
        for q in questions:
            argv, _ = console.build_command("trader-broker", q)
            self.assertIsNotNone(argv, q)
            for bad in mutating:
                self.assertNotIn(bad, argv, "question %r produced a mutating command: %s" % (q, argv))

    def test_the_whitelist_constant_itself_is_read_only(self):
        self.assertEqual(console.BROKER_READONLY, ("show",))
        for bad in console.FORBIDDEN_ARGS:
            self.assertNotIn(bad, console.BROKER_READONLY)

    def test_ask_never_executes_a_mutating_command_even_with_dry_run_off(self):
        """End to end: route an aggressive question, capture what WOULD run."""
        for q in ("approve my order and fill it", "flatten everything now"):
            argv, _ = console.build_command("trader-broker", q)
            self.assertEqual([a for a in argv if a in console.FORBIDDEN_ARGS], [])

    def test_no_tool_is_ever_invoked_with_a_network_mutating_subcommand(self):
        """Every command the console can build, across every agent, contains no
        mutating broker verb and no shell."""
        questions = ["scan the market", "any news on TSLA", "when to get in on TSLA",
                     "where is my stop", "what are the odds", "how many shares with $5000",
                     "risk check", "place the order", "alert me when TSLA hits 400",
                     "copy buffett", "what did pelosi buy", "does this strategy work",
                     "how did earnings look", "tax on my wash sale"]
        built = 0
        for q in questions:
            _, skills = console.route(q)
            for s in skills:
                argv, _ = console.build_command(s, q)
                if argv is None:
                    continue
                built += 1
                self.assertEqual(argv[0], sys.executable)
                self.assertNotIn("shell=True", " ".join(argv))
                for bad in console.FORBIDDEN_ARGS:
                    if s == "trader-broker":
                        self.assertNotIn(bad, argv)
        self.assertGreater(built, 10, "the console should be able to build most of these")


class CopycatIdentity(unittest.TestCase):
    def test_copycat_is_limited_to_find_and_explains_why(self):
        """'copy' needs the user's real name and email for SEC's User-Agent policy.
        The console must not invent an identity for a government endpoint."""
        argv, note = console.build_command("trader-copycat", "copy buffett from his 13f")
        self.assertIn("find", argv)
        self.assertNotIn("copy", argv)
        self.assertIn("SEC_USER_AGENT", note)
        self.assertIn("will not invent an identity", note)


class Output(unittest.TestCase):
    def test_agents_lists_every_pack_and_the_overlap(self):
        rc, out, _ = call(["agents"])
        self.assertEqual(rc, 0)
        self.assertIn("agents wired up", out)
        self.assertIn("trader-labs", out)
        self.assertIn("trader-copycat", out)
        self.assertIn("show only", out)
        self.assertIn("cannot approve, fill or flatten", out)

    def test_ask_dry_run_prints_commands_without_running_them(self):
        rc, out, _ = call(["ask", "does the ema12 rule actually work on QQQ", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("intent   : does-it-work", out)
        self.assertIn("[dry run, not executed]", out)
        self.assertIn("Not financial advice", out)

    def test_ask_reports_nothing_was_placed(self):
        rc, out, _ = call(["ask", "size a trade on TSLA with a $5000 budget", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("Nothing was placed", out)

    def test_evidence_refuses_fewer_than_three_instruments(self):
        rc, out, _ = call(["evidence", "QQQ,SPY"])
        self.assertEqual(rc, 1)
        self.assertIn("at least 3", out)

    def test_pipeline_dry_run_stops_at_the_ticket(self):
        d = tempfile.mkdtemp(prefix="console-pipe-")
        self.addCleanup(shutil.rmtree, d, True)
        rc, out, _ = call(["pipeline", "TSLA", "--dry-run", "--workdir", d])
        self.assertEqual(rc, 0)
        self.assertIn("chain stops at a ticket", out)
        self.assertNotIn("approve", out)
        self.assertNotIn("flatten", out.replace("flatten one", ""))

    def test_every_chained_step_writes_the_artifact_the_next_one_reads(self):
        """Regression: without --write the chain dies at step 4 with 'no entry'."""
        d = tempfile.mkdtemp(prefix="console-w-")
        self.addCleanup(shutil.rmtree, d, True)
        rc, out, _ = call(["pipeline", "TSLA", "--dry-run", "--workdir", d])
        self.assertEqual(rc, 0)
        cmds = [l for l in out.splitlines() if "[dry run]" in l]
        self.assertTrue(cmds, "dry run should print the command lines")
        for label, tool, flag in (("entry", "entry.py", "--write"),
                                  ("exit", "exit.py", "--write"),
                                  ("size", "size.py", "--write")):
            line = [l for l in cmds if l.strip().startswith(label) and tool in l]
            self.assertTrue(line, "no dry-run line for %s/%s in %s" % (label, tool, cmds))
            self.assertIn(flag, line[0], "%s must write its artifact: %s" % (label, line[0]))

    def test_pipeline_defaults_to_the_packs_example_rules_so_it_can_finish(self):
        d = tempfile.mkdtemp(prefix="console-cfg-")
        self.addCleanup(shutil.rmtree, d, True)
        rc, out, _ = call(["pipeline", "TSLA", "--dry-run", "--workdir", d])
        self.assertEqual(rc, 0)
        if os.path.isfile(os.path.join(console.V2, "trader-budget", "config.example.json")):
            self.assertIn("config.example.json", out)

    def test_the_audit_log_is_written_and_is_valid_jsonl(self):
        d = tempfile.mkdtemp(prefix="console-log-")
        self.addCleanup(shutil.rmtree, d, True)
        old = console.LOG
        try:
            console.LOG = os.path.join(d, "console-log.jsonl")
            call(["ask", "does the ema12 rule actually work on QQQ", "--dry-run"])
            self.assertTrue(os.path.isfile(console.LOG))
            with open(console.LOG, encoding="utf-8") as fh:
                lines = [l for l in fh.read().splitlines() if l.strip()]
            self.assertTrue(lines)
            rec = json.loads(lines[-1])
            self.assertEqual(rec["intent"], "does-it-work")
            self.assertIn("question", rec)
            self.assertIn("results", rec)
        finally:
            console.LOG = old

    def test_no_command_prints_a_guaranteed_return_claim(self):
        for argv in (["agents"], ["ask", "does this strategy work", "--dry-run"],
                     ["pipeline", "TSLA", "--dry-run"]):
            d = tempfile.mkdtemp(prefix="console-out-")
            self.addCleanup(shutil.rmtree, d, True)
            if argv[0] == "pipeline":
                argv = argv + ["--workdir", d]
            _, out, _ = call(argv)
            low = out.lower()
            for banned in ("guaranteed return", "guaranteed profit", "risk free", "risk-free",
                           "sure thing", "cannot lose"):
                self.assertNotIn(banned, low, "console output must never promise a return")


if __name__ == "__main__":
    unittest.main(verbosity=2)
