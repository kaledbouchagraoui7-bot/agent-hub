#!/usr/bin/env bash
# Restore vendored files that the workspace snapshot mechanism silently drops.
#
# The sandbox this project is built in excludes any path segment named build, dist,
# out, target, coverage, node_modules, __pycache__ and similar from its persisted
# snapshots. Upstream x-cmd legitimately contains 52 such files (mod/build/...,
# mod/version/lib/build/..., mod/zig/lib/target/...), so a vendored copy loses them
# between sessions even though nothing deleted them.
#
# They are preserved in third_party/x-cmd-excluded-paths.tar.gz. Run this after any
# fresh checkout or session restore, then verify against the manifest.
#
#   bash scripts/restore-excluded-paths.sh          # restore + verify
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XC="$ROOT/third_party/x-cmd"
TB="$ROOT/third_party/x-cmd-excluded-paths.tar.gz"

[ -d "$XC" ] || { echo "no vendored x-cmd at $XC" >&2; exit 1; }
[ -f "$TB" ] || { echo "no tarball at $TB" >&2; exit 1; }

before="$(find "$XC" -type f -not -name 'MANIFEST*' | wc -l)"
tar xzf "$TB" -C "$XC"
after="$(find "$XC" -type f -not -name 'MANIFEST*' | wc -l)"
echo "files before: $before   after: $after"

MAN="$XC/MANIFEST-upstream-git-ls-tree.txt"
if [ -f "$MAN" ]; then
  want="$(wc -l < "$MAN")"
  echo "upstream HEAD expects: $want"
  if [ "$after" -eq "$want" ]; then
    echo "OK: vendored x-cmd matches upstream HEAD file-for-file"
  else
    echo "MISMATCH: diff the listings to see what is still absent" >&2
    cut -d' ' -f2- "$MAN" | sort > /tmp/want.txt
    (cd "$XC" && find . -type f -not -name 'MANIFEST*' | sed 's|^\./||' | sort) > /tmp/have.txt
    comm -23 /tmp/want.txt /tmp/have.txt | head -20 >&2
    exit 1
  fi
fi

echo
echo "To verify CONTENT, not just paths, compare git blob SHAs against the manifest:"
echo "  cd $XC && while read -r sha path; do \\"
echo "    [ \"\$(git hash-object \"\$path\")\" = \"\$sha\" ] || echo \"DIFFERS: \$path\"; \\"
echo "  done < MANIFEST-upstream-git-ls-tree.txt"
