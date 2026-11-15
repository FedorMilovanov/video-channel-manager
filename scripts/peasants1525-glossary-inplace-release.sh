#!/usr/bin/env bash
# Existing-page-only 1525 Peasants War glossary revision. No createPage/sendMessage.
set -euo pipefail

state_branch=state/lordchrist-telegram
state_dir=.state/lordchrist
ledger_rel=content/telegram/lordchrist/telegraph-v1/publication-ledger.json
ledger_path="$state_dir/$ledger_rel"
publication_id=lordchrist-telegraph-peasants-1525-20261115
media_base_url="https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$GITHUB_SHA"

verify_main() {
  [[ "$GITHUB_REPOSITORY" == "FedorMilovanov/video-channel-manager" ]] || exit 3
  [[ "$GITHUB_REF" == "refs/heads/main" && "$GITHUB_RUN_ATTEMPT" == "1" ]] || exit 3
  [[ "$(gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha)" == "$GITHUB_SHA" ]] || {
    echo "Current main moved; refuse provider mutation" >&2
    exit 3
  }
  python -m video_channel_manager.telegram_github_quality_gate --workflow ci.yml --sha "$GITHUB_SHA"
}

run_stage() {
  python -m video_channel_manager.lordchrist_peasants1525_inplace "$1" \
    --ledger "$ledger_path" \
    --publication-id "$publication_id" \
    --media-base-url "$media_base_url" \
    --run-id "$GITHUB_RUN_ID" \
    --run-attempt "$GITHUB_RUN_ATTEMPT" \
    --github-sha "$GITHUB_SHA"
}

persist() {
  git -C "$state_dir" add -- "$ledger_rel"
  if git -C "$state_dir" diff --cached --quiet; then
    echo "No state change for $1; cannot advance stage" >&2
    exit 3
  fi
  git -C "$state_dir" commit -m "chore(lordchrist): in-place peasants1525-glossary-v2 $1 [skip ci]"
  git -C "$state_dir" push origin "HEAD:$state_branch"
  local local_sha remote_sha
  local_sha="$(git -C "$state_dir" rev-parse HEAD)"
  remote_sha="$(git ls-remote origin "refs/heads/$state_branch" | cut -f1)"
  [[ "$local_sha" == "$remote_sha" ]] || {
    echo "State push not confirmed; fail closed" >&2
    exit 3
  }
}

verify_main
git fetch origin "$state_branch:refs/remotes/origin/$state_branch"
git worktree add "$state_dir" "origin/$state_branch"
test -f "$ledger_path"
git -C "$state_dir" config user.name "lordchrist-inplace-revision[bot]"
git -C "$state_dir" config user.email "lordchrist-inplace-revision@users.noreply.github.com"

# Commit a page-edit intent before any provider call.
run_stage prepare-page
persist page-claimed
verify_main

# editPage at the already existing 11-15 URL only.
run_stage edit-page
persist page-verified
verify_main

# Claim the immutable original message 1619 separately.
run_stage prepare-telegram
persist telegram-claimed
verify_main

# editMessageText, never sendMessage.
run_stage edit-telegram
persist telegram-verified
