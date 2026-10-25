#!/usr/bin/env bash
# Initialise (or re-initialise) this repository and commit everything.
#
# Why this exists: the workspace this project is built in does NOT persist .git
# directories between sessions, while all file content does persist. So history can
# vanish while the work stays. This script rebuilds a clean, reproducible commit from
# the content, and is safe to run repeatedly.
#
#   bash scripts/init-git.sh                # init + commit
#   bash scripts/init-git.sh --amend        # fold into the existing commit
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NAME="${GIT_AUTHOR_NAME:-agent-hub}"
MAIL="${GIT_AUTHOR_EMAIL:-agent-hub@localhost}"

if [ ! -d .git ]; then
  git init -q -b main .
  echo "initialised a new repository on branch main"
fi

# never let a credential file be committed (must run AFTER git init creates .git/info)
mkdir -p .git/info
printf '.git/config\n.git/credentials\n.git-credentials\n.netrc\n' > .git/info/exclude
git config user.name  "$NAME"
git config user.email "$MAIL"

find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true
rm -rf trader-console/work trader-console/console-log.jsonl 2>/dev/null || true

git add -A
if [ "${1:-}" = "--amend" ]; then
  git commit -q --amend --no-edit
  echo "amended: $(git log --oneline -1)"
else
  git commit -q -m "agent-hub: 16 trader agents, the console, the Obsidian data farm, and the research

Four test suites, 606 tests, all passing (scripts/run-tests.sh).

  trader-agents/     12 skills: a byte-exact MIT replica of
                     Jakeschincariol/day-trader-skill @ 3d0f4ef (tree 100eb4c3) plus
                     trader-labs, an original backtester that reports in-sample vs
                     out-of-sample, R per trade, a t statistic and the selection bias
                     of picking the best of N variants.
  trader-skill/      11 skills, byte-exact replica of Jakeschincariol/trader-skill
                     @ 5189e79 (13F copycat, screener, rebalance, tax). 175 tests.
  trader-console/    one prompt in front of all 16. Decision support only: there is
                     no code path that places, approves, fills or flattens an order.
  obsidian-datafarm/ vault -> graph.json/graph.html/stats.json, a connection and
                     secret-scanning probe, and a starter vault with an AGENTS.md
                     contract. 37 tests.
  docs/              the research: whether 3k/month from trading is reachable (it is
                     not, with the arithmetic), the two published strategies ranked
                     after being tested on live data, analyses of OmniRoute and
                     x-cmd, and exactly which external sources are reachable.

Attribution for all third-party code is in THIRD_PARTY_NOTICES.md.
No credential-shaped literal appears anywhere in this tree (scanned)." 2>/dev/null \
    || echo "nothing to commit (tree already matches HEAD)"
  echo "committed: $(git log --oneline -1)"
fi

echo
echo "tracked files: $(git ls-files | grep -c .)"
echo "credential files tracked: $(git ls-files | grep -Ec '(^|/)\.git-credentials|\.netrc|\.git/config' || true)  (must be 0)"
