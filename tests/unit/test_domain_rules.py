from datetime import UTC, datetime

import pytest

from docket import config, deadlines, domain
from docket.domain import zone_names


def test_domain_values_are_literal_and_immutable() -> None:
    assert domain.STATES == ("open", "in_progress", "done", "cancelled")
    assert domain.OPEN_STATES == ("open", "in_progress")
    assert domain.ENDED_STATES == ("done", "cancelled")
    assert domain.SOURCES == ("email", "agent", "proposal", "owner")
    assert domain.CORE_CLIENTS == ("email", "agent")
    assert domain.ACTORS == ("owner", "agent", "email")
    assert domain.STATE_ACTIONS == ("start", "done", "cancel", "reopen")
    assert domain.AUDIT_ACTIONS == (
        "create",
        "start",
        "done",
        "cancel",
        "reopen",
        "retitle",
        "deadline",
        "work_time",
    )
    assert domain.PROVIDERS == ("gmail", "outlook", "yahoo")
    assert domain.SOURCE_ACTORS == {
        "email": "email",
        "agent": "agent",
        "proposal": "owner",
        "owner": "owner",
    }
    assert domain.STATE_LABELS == {
        "open": "open",
        "in_progress": "in progress",
        "done": "done",
        "cancelled": "cancelled",
    }
    assert domain.FORBIDDEN_TEXT_CATEGORIES == frozenset({"Cc", "Cf", "Zl", "Zp"})
    assert (domain.TITLE_MAX, domain.REQUEST_KEY_MAX) == (100, 200)
    assert (domain.WORK_MINUTES_MIN, domain.WORK_MINUTES_MAX) == (5, 720)
    assert (deadlines.WORK_MINUTES_MIN, deadlines.WORK_MINUTES_MAX) == (5, 720)
    for mapping in (domain.SOURCE_ACTORS, domain.STATE_LABELS):
        with pytest.raises(TypeError):
            mapping["synthetic"] = "synthetic"


def test_zone_names_are_loaded_once_and_never_case_folded(monkeypatch: pytest.MonkeyPatch) -> None:
    import zoneinfo

    calls = []

    def supplied():
        calls.append("read")
        return {"UTC", "America/New_York"}

    zone_names.cache_clear()
    try:
        monkeypatch.setattr(zoneinfo, "available_timezones", supplied)
        first = zone_names()
        assert first == frozenset({"UTC", "America/New_York"})
        assert zone_names() is first
        assert calls == ["read"]
        assert "america/new_york" not in first
    finally:
        zone_names.cache_clear()


def test_settings_and_deadlines_use_the_same_zone_function(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def supplied():
        calls.append("read")
        return frozenset({"UTC"})

    monkeypatch.setattr(domain, "zone_names", supplied)
    assert config.Settings(time_zone="UTC").time_zone == "UTC"
    deadlines.Deadline(datetime(2026, 11, 17, 14, tzinfo=UTC), "UTC", True)
    assert calls == ["read", "read"]
    with pytest.raises(config.ValidationError):
        config.Settings(time_zone="America/New_York")
    with pytest.raises(deadlines.DeadlineError, match="^unknown time zone$"):
        deadlines.Deadline(datetime(2026, 11, 17, 14, tzinfo=UTC), "America/New_York", True)
