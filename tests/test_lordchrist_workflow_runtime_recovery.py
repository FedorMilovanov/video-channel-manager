"""Regressions for provider-inert LordChrist workflow handoff failures.

These checks test workflow configuration only; they never contact Telegram.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / ".github/workflows/lordchrist-quote-v4-preflight.yml"
QUIZ = ROOT / ".github/workflows/lordchrist-quiz-series-poster.yml"


def test_quote_v4_preflight_exports_digest_to_following_steps() -> None:
    workflow = PREFLIGHT.read_text(encoding="utf-8")
    step = workflow.split(
        "      - name: Bind the exact reviewed queue digest for the read-only preflight", 1
    )[1].split("      - name: Validate queue and strict ledger (v4)", 1)[0]

    assert 'digest = selection["queue_digest"]' in step
    assert 'digest == activation["queue_digest"] == schedule["queue_digest"]' in step
    assert 'with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:' in step
    assert 'handle.write(f"LORDCHRIST_APPROVED_QUEUE_DIGEST={digest}\\n")' in step
    assert 'print(f"LORDCHRIST_APPROVED_QUEUE_DIGEST={digest}")' not in step


def test_quiz_series_creates_freshness_directory_before_redirecting_output() -> None:
    workflow = QUIZ.read_text(encoding="utf-8")
    step = workflow.split("      - name: Resolve the next due series quiz", 1)[1].split(
        "      - name: Nothing due in this run", 1
    )[0]

    mkdir = 'mkdir -p "$(dirname "$FRESHNESS_PATH")"'
    redirect = '> "$FRESHNESS_PATH"'
    assert mkdir in step
    assert step.index(mkdir) < step.index(redirect)
    # The freshness CLI intentionally returns 3 for not-due; the JSON result
    # must still be read so a non-eligible quiz is never dispatched.
    assert "set +e" in step
    assert 'decision.get("eligible") and decision.get("publication_id")' in step
