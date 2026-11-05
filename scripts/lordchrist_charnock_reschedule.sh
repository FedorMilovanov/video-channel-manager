#!/usr/bin/env bash
# Schedule-only recovery of owner-deleted 2026-11-05 messages. Never re-create Telegraph.
set -euo pipefail
state_dir=".state/lordchrist"
ledger_rel="content/telegram/lordchrist/telegraph-v1/publication-ledger.json"

current_main_ci() {
  [[ "$GITHUB_EVENT_NAME" == "schedule" && "$GITHUB_RUN_ATTEMPT" == "1" ]] || exit 3
  [[ "$GITHUB_REF" == "refs/heads/main" ]] || exit 3
  [[ "$(gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha)" == "$GITHUB_SHA" ]] || exit 3
  python -m video_channel_manager.telegram_github_quality_gate --workflow ci.yml --sha "$GITHUB_SHA"
}

stage() {
  python -m video_channel_manager.lordchrist_charnock_reschedule "$1" \
    --publication-id "$PUBLICATION_ID" \
    --ledger "$LEDGER_PATH" \
    --run-id "$GITHUB_RUN_ID" \
    --run-attempt "$GITHUB_RUN_ATTEMPT" \
    --github-sha "$GITHUB_SHA"
}

persist() {
  git -C "$state_dir" add -- "$ledger_rel"
  if git -C "$state_dir" diff --cached --quiet; then
    echo "Charnock incident state has no new record: $1" >&2
    exit 3
  fi
  git -C "$state_dir" commit -m "chore(lordchrist): Charnock scheduled reissue $PUBLICATION_ID ($1)"
  git -C "$state_dir" push origin HEAD:state/lordchrist-telegram
  local local_sha remote_sha
  local_sha="$(git -C "$state_dir" rev-parse HEAD)"
  remote_sha="$(git ls-remote origin refs/heads/state/lordchrist-telegram | cut -f1)"
  [[ "$local_sha" == "$remote_sha" ]] || exit 3
}

current_main_ci
git fetch origin state/lordchrist-telegram:refs/remotes/origin/state/lordchrist-telegram
git worktree add "$state_dir" origin/state/lordchrist-telegram
test -f "$LEDGER_PATH"
git -C "$state_dir" config user.name "lordchrist-charnock-schedule[bot]"
git -C "$state_dir" config user.email "lordchrist-charnock-schedule@users.noreply.github.com"

stage prepare
persist "prepare"
current_main_ci
stage send
persist "provider-receipt"
sleep 10
stage verify
persist "public-readback"
