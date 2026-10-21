from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "lordchrist-telegram-poster.yml"
SCHEDULE = ROOT / "content" / "telegram" / "lordchrist" / "production-schedule.json"
HISTORICAL_CRON = "17 16 * * 1,3,6"

MOSCOW = ZoneInfo("Europe/Moscow")
CRON_PATTERN = re.compile(r'- cron: "(?P<cron>[^"]+)"')


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _schedule() -> dict[str, object]:
    return json.loads(SCHEDULE.read_text(encoding="utf-8"))


def _workflow_crons() -> list[str]:
    return [match.group("cron") for match in CRON_PATTERN.finditer(_workflow())]


def _utc_fire_time(cron: str, *, day: datetime) -> datetime:
    minute, hour = (int(part) for part in cron.split()[:2])
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _eligible_day(cron: str) -> datetime:
    """Return the first Monday-based week day matching the cron weekday field."""

    weekdays = cron.split()[4]
    allowed = {int(part) for part in weekdays.split(",")} if weekdays != "*" else set(range(7))
    day = datetime(2026, 10, 26, tzinfo=UTC)  # Monday, well past not_before
    while day.isoweekday() % 7 not in allowed:
        day += timedelta(days=1)
    return day


def test_workflow_schedule_declares_no_timezone_key() -> None:
    """Cron expressions are already the UTC form of the Moscow slot times.

    Adding ``timezone: Europe/Moscow`` would apply the offset twice. That is not
    a stylistic preference: the runtime derives the slot in Moscow time and
    enforces a bounded lease, so a double offset silently stops publication.
    """

    schedule_block = _workflow().split("permissions:", 1)[0]
    functional_lines = [
        line for line in schedule_block.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    assert [line for line in functional_lines if "timezone:" in line] == []


def test_every_workflow_cron_is_either_a_configured_slot_or_the_historical_slot() -> None:
    configured = {str(slot["cron"]) for slot in _schedule()["slots"].values()}  # type: ignore[union-attr]
    crons = _workflow_crons()

    assert len(crons) == len(set(crons)), "a duplicated cron would run twice"
    assert set(crons) == configured | {HISTORICAL_CRON}
    assert HISTORICAL_CRON not in configured


def _job_condition(job: str) -> str:
    """Return the ``if:`` expression of one job, as written in the workflow."""

    jobs = _workflow().split("\njobs:", 1)[1]
    block = jobs.split(f"\n  {job}:", 1)[1]
    block = block.split("\n    runs-on:", 1)[0]
    return block


def test_every_declared_cron_has_exactly_one_route() -> None:
    """A cron nobody routes is a silently dead schedule.

    Two routes exist, and every cron must take exactly one of them:

    * a cron that is a quote/rich slot reaches ``publish-next``, which is only
      safe because the runtime decider decides whether that slot is due;
    * a cron that is not a slot of the configured schedule must be excluded from
      ``publish-next`` and selected by its own job, otherwise it would either do
      nothing or be mistaken for a queue slot.

    ``17 16 * * 1,3,6`` is the historical rich track: it must be excluded from
    ``publish-next`` and selected by ``historical-rich``. A cron wired to the
    wrong job is indistinguishable from a missing schedule until a slot is
    missed in production.
    """

    from video_channel_manager.telegram_schedule import load_production_schedule

    crons = _workflow_crons()
    assert crons, "the publisher must keep an explicit schedule"
    assert len(crons) == len(set(crons)), "a duplicated cron would run twice"

    slot_crons = {slot.cron for slot in load_production_schedule(SCHEDULE).slots.values()}
    publish_next = _job_condition("publish-next")
    historical = _job_condition("historical-rich")
    exclusion = "&& github.event.schedule == '{cron}'"

    for cron in crons:
        excluded_from_quote = exclusion.format(cron=cron) in publish_next
        selected_elsewhere = f"github.event.schedule == '{cron}'" in historical
        if cron in slot_crons:
            assert not excluded_from_quote, f"{cron} is a queue slot and must reach publish-next"
        else:
            assert excluded_from_quote, f"{cron} is not a queue slot and must not reach publish-next"
            assert selected_elsewhere, f"{cron} is declared but no job consumes it"

    assert HISTORICAL_CRON not in slot_crons


def test_cron_fire_time_matches_the_declared_moscow_slot_time() -> None:
    """Each cron must fire exactly at the Moscow slot boundary it represents."""

    from video_channel_manager.telegram_schedule import load_production_schedule

    schedule = load_production_schedule(SCHEDULE)

    for name, slot in schedule.slots.items():
        fire = _utc_fire_time(slot.cron, day=_eligible_day(slot.cron))
        local = fire.astimezone(MOSCOW)

        assert local.strftime("%H:%M") == slot.time, (name, slot.cron, slot.time, local)
        # The cron weekday set must match the runtime ISO weekday guard.
        cron_weekdays = slot.cron.split()[4]
        if cron_weekdays != "*":
            assert local.isoweekday() in slot.iso_weekdays, (name, slot.cron)


def test_runtime_accepts_each_cron_at_its_exact_utc_fire_time() -> None:
    """The scheduled event must map to one active slot, without lateness hacks."""

    from video_channel_manager.telegram_schedule import (
        decide_scheduled_slot,
        load_production_schedule,
    )

    schedule = load_production_schedule(SCHEDULE)

    for name, slot in schedule.slots.items():
        fire = _utc_fire_time(slot.cron, day=_eligible_day(slot.cron))
        decision = decide_scheduled_slot(schedule, event_schedule=slot.cron, now=fire)

        assert decision.active is True, (name, decision.reason)
        assert decision.slot == name


def test_timezone_key_would_break_publication_at_the_shifted_fire_time() -> None:
    """Proves why the timezone key is forbidden instead of merely unused."""

    from video_channel_manager.telegram_schedule import (
        decide_scheduled_slot,
        load_production_schedule,
    )

    schedule = load_production_schedule(SCHEDULE)
    morning = schedule.slots["morning"]
    evening = schedule.slots["evening"]

    # A timezone key would fire the morning cron at 06:17 Moscow, i.e. three
    # hours earlier in UTC than the configured 09:17 boundary.
    shifted_morning = _utc_fire_time(morning.cron, day=_eligible_day(morning.cron)) - timedelta(hours=3)
    morning_decision = decide_scheduled_slot(schedule, event_schedule=morning.cron, now=shifted_morning)
    assert morning_decision.active is False
    assert "not due yet" in morning_decision.reason

    # The evening cron would move to 15:17 UTC, outside its bounded same-day
    # lease, so the run would be silently discarded as stale.
    shifted_evening = _utc_fire_time(evening.cron, day=_eligible_day(evening.cron)) - timedelta(hours=3)
    evening_decision = decide_scheduled_slot(schedule, event_schedule=evening.cron, now=shifted_evening)
    assert evening_decision.active is False
    assert evening_decision.reason
