#!/usr/bin/env bash
# Publish the workshop to the public GitHub repo (run AFTER Code Defender
# approval lands). Preserves any existing repo content on a backup branch,
# then force-pushes the workshop to main.
#
#   scripts/publish-to-github.sh
set -euo pipefail

REPO_URL="${GITHUB_REPO_URL:-https://github.com/anuradhajayanthi1/security-agent.git}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git remote remove github 2>/dev/null || true
git remote add github "$REPO_URL"
git fetch github -q || true

# Preserve whatever is on the remote main today (best-effort).
if git rev-parse --verify -q refs/remotes/github/main >/dev/null; then
  echo "==> backing up existing remote content to branch 'original-content'"
  git push github refs/remotes/github/main:refs/heads/original-content 2>&1 | tail -2 || true
fi

echo "==> pushing workshop to main"
git push -f github main

echo
echo "Done. Public clone URL for the workshop:"
echo "  $REPO_URL"
