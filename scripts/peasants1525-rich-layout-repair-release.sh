#!/usr/bin/env bash
# One-time repair of existing @lordchrist message #1619. Never publish a new message.
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
    echo "Current main changed; refuse provider mutation" >&2
    exit 3
  }
}

stage() {
  python scripts/peasants1525_rich_layout_repair.py "$1" \
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
    echo "No state change for $1; stop" >&2
    exit 3
  fi
  git -C "$state_dir" commit -m "chore(lordchrist): original #1619 rich layout $1 [skip ci]"
  git -C "$state_dir" push origin "HEAD:$state_branch"
  local local_sha remote_sha
  local_sha="$(git -C "$state_dir" rev-parse HEAD)"
  remote_sha="$(git ls-remote origin "refs/heads/$state_branch" | cut -f1)"
  [[ "$local_sha" == "$remote_sha" ]] || {
    echo "State push not confirmed; stop without retry" >&2
    exit 3
  }
}

verify_main
python -m video_channel_manager.telegram_github_quality_gate \
  --workflow ci.yml --sha "$GITHUB_SHA" --wait-seconds 480
git fetch origin "$state_branch:refs/remotes/origin/$state_branch"
git worktree add "$state_dir" "origin/$state_branch"
test -f "$ledger"
git -C "$state_dir" config user.name "lordchrist-1619-repair[bot]"
git -C "$state_dir" config user.email "lordchrist-1619-repair@users.noreply.github.com"

verify_main
stage claim
persist claimed
verify_main
stage edit
persist verified
