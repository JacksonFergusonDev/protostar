"""The checks every published metric's history shares."""

from datetime import UTC, datetime

import pytest

from scripts import _publish


def test_a_missing_history_is_the_first_run(tmp_path):
    assert _publish.read_history(tmp_path / "history.json") == []


def test_a_history_that_is_not_a_list_publishes_nothing(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(_publish.PublicationError, match="not a list"):
        _publish.read_history(path)


@pytest.mark.parametrize("commit", ["a" * 39, "A" * 40, "main"])
def test_only_a_full_commit_hash_names_a_run(commit):
    with pytest.raises(_publish.PublicationError, match="full Git commit"):
        _publish.check_commit(commit)


@pytest.mark.parametrize("date", ["2026-10-02T00:00:00", "2026-10-02T00:00:00+02:00"])
def test_a_run_date_must_be_utc(date):
    with pytest.raises(_publish.PublicationError, match="UTC"):
        _publish.utc_date(date)


def test_a_run_older_than_the_last_recorded_one_is_refused():
    history = [{"date": "2026-10-05T00:00:00+00:00"}]
    _publish.check_newest(history, datetime(2026, 10, 5, tzinfo=UTC))
    with pytest.raises(_publish.PublicationError, match="older"):
        _publish.check_newest(history, datetime(2026, 10, 4, tzinfo=UTC))


def test_every_badge_shares_the_house_colors():
    assert _publish.badge("label", "5") == {
        "schemaVersion": 1,
        "label": "label",
        "message": "5",
        "color": "22d3ee",
        "labelColor": "0A0A0A",
    }
