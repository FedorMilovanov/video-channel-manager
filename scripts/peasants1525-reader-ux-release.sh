#!/usr/bin/env bash
# One-time UX revision for the EXISTING post #1619 and the EXISTING Telegraph URL.
# No sendMessage, createPage or automatic retry after ambiguous provider effects.
set -euo pipefail

state_branch=state/lordchrist-telegram
state_dir=.state/lordchrist
ledger_rel=content/telegram/lordchrist/telegraph-v1/publication-ledger.json
ledger="$state_dir/$ledger_rel"
publication_id=lordchrist-telegraph-peasants-1525-20261115
media_base="https://raw.githubusercontent.com/FedorMilovanov/video-channel-manager/77b2087ac2e714af74fed19cb653b1a7c2ecfb68"

verify_main() {
  [[ "$GITHUB_REPOSITORY" == "FedorMilovanov/video-channel-manager" ]] || exit 3
  [[ "$GITHUB_REF" == "refs/heads/main" && "$GITHUB_RUN_ATTEMPT" == "1" ]] || exit 3
  [[ "$(gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha)" == "$GITHUB_SHA" ]] || {
    echo "Another agent advanced main: stop before provider changes" >&2
    exit 3
  }
}

stage() {
  python -m video_channel_manager.lordchrist_peasants1525_readability "$1" \
    --ledger "$ledger" \
    --publication-id "$publication_id" \
    --media-base-url "$media_base" \
    --run-id "$GITHUB_RUN_ID" \
    --run-attempt "$GITHUB_RUN_ATTEMPT" \
    --github-sha "$GITHUB_SHA"
}

persist() {
  git -C "$state_dir" add -- "$ledger_rel"
  if git -C "$state_dir" diff --cached --quiet; then
    echo "Expected durable state change absent at stage $1" >&2
    exit 3
  fi
  git -C "$state_dir" commit -m "chore(lordchrist): 1525 original-post reader UX $1 [skip ci]"
  git -C "$state_dir" push origin "HEAD:$state_branch"
  local local_sha remote_sha
  local_sha="$(git -C "$state_dir" rev-parse HEAD)"
  remote_sha="$(git ls-remote origin "refs/heads/$state_branch" | cut -f1)"
  [[ "$local_sha" == "$remote_sha" ]] || {
    echo "State push is not confirmed. Stop immediately." >&2
    exit 3
  }
}

verify_main
# The same merged main SHA must have completed all three quality matrices.
python -m video_channel_manager.telegram_github_quality_gate \
  --workflow ci.yml --sha "$GITHUB_SHA" --wait-seconds 480

git fetch origin "$state_branch:refs/remotes/origin/$state_branch"
git worktree add "$state_dir" "origin/$state_branch"
test -f "$ledger"
git -C "$state_dir" config user.name "lordchrist-reader-ux[bot]"
git -C "$state_dir" config user.email "lordchrist-reader-ux@users.noreply.github.com"

verify_main
stage prepare-page
persist page-claimed
verify_main
stage edit-page
persist page-verified
verify_main
stage prepare-telegram
persist telegram-claimed
verify_main
stage edit-telegram
persist telegram-verified
