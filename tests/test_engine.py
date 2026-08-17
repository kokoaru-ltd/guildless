"""A screen may only say "running" when something is actually running."""

import time
from datetime import UTC, datetime, timedelta

import pytest

from council.engine import STALE_AFTER, Engine, Heartbeat


@pytest.fixture
def engine(tmp_path):
    made = Engine(tmp_path / "engine.json", interval_seconds=0.05)
    yield made
    made.stop()


# --- the regression: nothing running must not read as running --------------

def test_a_fresh_engine_is_not_running(engine):
    assert engine.running is False
    assert engine.status()["state"] == "stopped"
    assert engine.status()["alive"] is False


def test_a_recorded_running_state_without_a_heartbeat_is_a_crash(tmp_path):
    """The exact defect: state said running, nothing was executing."""
    stale = Engine(tmp_path / "engine.json")
    stale.heartbeat = Heartbeat(
        state="running",
        at=(datetime.now(UTC) - STALE_AFTER - timedelta(seconds=5)).isoformat(),
    )
    assert stale.running is False
    assert stale.status()["state"] == "crashed"


def test_an_unparseable_heartbeat_is_not_alive(tmp_path):
    engine = Engine(tmp_path / "engine.json")
    engine.heartbeat = Heartbeat(state="running", at="いつか")
    assert engine.running is False


def test_status_never_reports_a_current_step_when_dead(tmp_path):
    engine = Engine(tmp_path / "engine.json")
    engine.heartbeat = Heartbeat(state="running", at="", step="顧客を探しています")
    assert engine.status()["current_step"] == ""


# --- it actually runs -------------------------------------------------------

def test_starting_makes_it_run_and_tick(engine):
    seen = []
    engine.steps = [("discovery", lambda: seen.append(1) or "1社検査しました")]
    assert engine.start() is True

    deadline = time.time() + 5
    while time.time() < deadline and not seen:
        time.sleep(0.05)

    assert seen, "step never executed"
    assert engine.running is True
    assert engine.status()["ticks"] > 0


def test_work_appears_in_the_activity_log(engine):
    engine.steps = [("discovery", lambda: "22社を検査し、適格0社")]
    engine.start()
    deadline = time.time() + 5
    while time.time() < deadline and not engine.activity:
        time.sleep(0.05)

    recent = engine.recent()
    assert recent and recent[0]["step"] == "discovery"
    assert "22社" in recent[0]["detail"]


def test_a_second_start_does_not_create_a_second_worker(engine):
    engine.steps = [("noop", lambda: "")]
    assert engine.start() is True
    assert engine.start() is False


def test_stopping_ends_it(engine):
    engine.steps = [("noop", lambda: "")]
    engine.start()
    time.sleep(0.2)
    engine.stop()
    assert engine.running is False
    assert engine.status()["state"] == "stopped"


# --- failures are visible, not fatal ---------------------------------------

def test_a_failing_step_is_recorded_and_the_loop_survives(engine):
    calls = {"n": 0}

    def broken():
        calls["n"] += 1
        raise RuntimeError("provider down")

    engine.steps = [("discovery", broken), ("other", lambda: "続行しました")]
    engine.start()
    deadline = time.time() + 5
    while time.time() < deadline and len(engine.activity) < 2:
        time.sleep(0.05)

    details = [item["detail"] for item in engine.recent()]
    assert any("provider down" in d for d in details)
    assert any("続行しました" in d for d in details)
    assert engine.running is True


# --- it survives a restart --------------------------------------------------

def test_activity_and_heartbeat_persist(tmp_path):
    path = tmp_path / "engine.json"
    first = Engine(path, interval_seconds=0.05)
    first.record("discovery", "3社を検査")
    first.stop()

    reopened = Engine(path)
    assert reopened.recent()[0]["detail"] == "3社を検査"
    # Reading a file is not being alive.
    assert reopened.running is False


def test_external_actions_are_marked_as_such(engine):
    engine.record("outreach", "1社へ送信", external=True)
    engine.record("research", "検索した")
    marks = {item["step"]: item["external"] for item in engine.recent()}
    assert marks["outreach"] is True
    assert marks["research"] is False
