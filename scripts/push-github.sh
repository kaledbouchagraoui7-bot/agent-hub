#!/usr/bin/env bash
# Push this repository to GitHub WITHOUT ever writing a credential to disk.
#
# The token is passed inline for a single push, so it never lands in .git/config,
# .git-credentials or the reflog. It is read from the environment only.
#
#   GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=you GITHUB_REPO=agent-hub bash scripts/push-github.sh
#
# Preconditions (do these once, in the GitHub web UI, no token needed):
#   1. New repository -> name it, keep it EMPTY (no README, no .gitignore, no licence)
#   2. Fine-grained token scoped to that one repository, Contents: Read and write
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${GITHUB_TOKEN:?set GITHUB_TOKEN to a fine-grained PAT scoped to this one repo}"
: "${GITHUB_OWNER:?set GITHUB_OWNER to your GitHub username or org}"
: "${GITHUB_REPO:?set GITHUB_REPO to the repository name you created}"
BRANCH="${GITHUB_BRANCH:-main}"
GITHUB_PRIVATE="${GITHUB_PRIVATE:-1}"   # 1 = private by default; set GITHUB_PRIVATE=0 to publish

[ -d .git ] || bash scripts/init-git.sh

echo "repository : ${GITHUB_OWNER}/${GITHUB_REPO} (branch ${BRANCH})"
echo "commit     : $(git log --oneline -1)"
echo "files      : $(git ls-files | grep -c .)"
echo "size       : $(du -sh --exclude=.git . | cut -f1)"
echo

# Create the repository if it does not exist yet. Fine-grained PATs CAN do this when
# granted the account-level "Repository creation: Read and write" permission (verified
# against the permission matrix in the token UI); a token without it gets a 403 here
# and the script tells you exactly which permission to add.
echo "checking repository ${GITHUB_OWNER}/${GITHUB_REPO} ..."
code="$(python3 - "$GITHUB_TOKEN" "$GITHUB_OWNER" "$GITHUB_REPO" "$GITHUB_PRIVATE" <<'PYEOF'
import json, sys, urllib.request, urllib.error
tok, owner, repo, priv = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
def call(method, path, body=None):
    req = urllib.request.Request("https://api.github.com" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
                 "User-Agent": "agent-hub-bootstrap/1.0", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {}
st, _ = call("GET", "/repos/%s/%s" % (owner, repo))
if st == 200:
    print("exists")
elif st == 404:
    st2, _ = call("POST", "/user/repos",
                  {"name": repo, "private": priv,
                   "description": "16 trading/verification agents, a console that routes plain "
                                  "English to them, an Obsidian knowledge-graph toolchain, and the "
                                  "research that tested a viral 508% strategy and found it loses.",
                   "has_issues": True, "has_wiki": False})
    print("created" if st2 == 201 else "create-failed:%d" % st2)
elif st == 401:
    print("auth-failed")
else:
    print("unexpected:%d" % st)
PYEOF
)"
case "$code" in
  exists)  echo "  repository already exists; pushing to it" ;;
  created) echo "  repository created" ;;
  auth-failed)
    echo "ERROR: GitHub rejected the token (401). It is revoked, expired, or belongs to" >&2
    echo "another account. Generate a fresh fine-grained token and retry. Do not reuse" >&2
    echo "a token that has been pasted into a chat; consider it burned." >&2
    exit 1 ;;
  create-failed:403)
    echo "ERROR: authenticated, but the token lacks the account-level" >&2
    echo "'Repository creation: Read and write' permission. Add it, or create the empty" >&2
    echo "repository in the web UI first and retry." >&2
    exit 1 ;;
  *)
    echo "ERROR: unexpected result: $code" >&2
    exit 1 ;;
esac

# safety: refuse to push anything that looks like a credential file
if git ls-files | grep -Eq '(^|/)(\.git-credentials|\.netrc|id_rsa|id_ed25519|.*\.pem)$'; then
  echo "ABORTING: a credential-shaped file is tracked. Remove it first." >&2
  git ls-files | grep -E '(^|/)(\.git-credentials|\.netrc|id_rsa|id_ed25519|.*\.pem)$' >&2
  exit 1
fi

# inline credential: nothing is stored, no remote is configured
git push --set-upstream \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git" \
  "${BRANCH}:refs/heads/${BRANCH}"

echo
echo "pushed. Verify at https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"
echo
echo "NOW REVOKE THE TOKEN: GitHub -> Settings -> Developer settings -> Fine-grained tokens."
echo "It was never written to disk here, but it did travel through this shell's environment."
