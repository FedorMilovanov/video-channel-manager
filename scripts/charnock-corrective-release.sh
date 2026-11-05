#!/usr/bin/env bash
# Five existing posts only; one-shot public edits with durable Git state.
set -euo pipefail
state_dir=".state/lordchrist"
ledger_rel="content/telegram/lordchrist/telegraph-v1/publication-ledger.json"

check_main_ci() {
  [[ "$GITHUB_REF" == "refs/heads/main" && "$GITHUB_RUN_ATTEMPT" == "1" ]] || exit 3
  [[ "$(gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha)" == "$GITHUB_SHA" ]] || {
    echo "main moved since correction dispatch; block provider effect" >&2
    exit 3
  }
  python -m video_channel_manager.telegram_github_quality_gate --workflow ci.yml --sha "$GITHUB_SHA"
}

persist() {
  git -C "$state_dir" add -- "$ledger_rel"
  if git -C "$state_dir" diff --cached --quiet; then
    echo "No new durable state in correction stage $1" >&2
    exit 3
  fi
  git -C "$state_dir" commit -m "chore(lordchrist): Charnock correction $PUBLICATION_ID ($1)"
  git -C "$state_dir" push origin HEAD:state/lordchrist-telegram
  local local_sha remote_sha
  local_sha="$(git -C "$state_dir" rev-parse HEAD)"
  remote_sha="$(git ls-remote origin refs/heads/state/lordchrist-telegram | cut -f1)"
  [[ "$local_sha" == "$remote_sha" ]] || {
    echo "Durable state push could not be independently confirmed" >&2
    exit 3
  }
}

run_stage() {
  python -m video_channel_manager.lordchrist_telegraph_corrections "$1" \
    --publication-id "$PUBLICATION_ID" \
    --media-base-url "$MEDIA_BASE_URL" \
    --ledger "$LEDGER_PATH" \
    --run-id "$GITHUB_RUN_ID" \
    --run-attempt "$GITHUB_RUN_ATTEMPT" \
    --github-sha "$GITHUB_SHA"
}

check_main_ci
git fetch origin state/lordchrist-telegram:refs/remotes/origin/state/lordchrist-telegram
git worktree add "$state_dir" origin/state/lordchrist-telegram
test -f "$LEDGER_PATH"
git -C "$state_dir" config user.name "lordchrist-corrections[bot]"
git -C "$state_dir" config user.email "lordchrist-corrections@users.noreply.github.com"

# Claim and commit before any potentially ambiguous createPage.
run_stage prepare-page
persist page-claimed
check_main_ci
run_stage send-page
persist page-receipt

# Separately claim the immutable identity of the already posted Telegram item.
run_stage prepare-telegram
persist telegram-claimed
check_main_ci
run_stage edit-telegram
persist telegram-receipt
