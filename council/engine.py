"""The thing that actually runs. Until now there was only a screen describing one.

The control centre reported RUNNING and "searching for new ways to find
customers" while nothing was executing at all: the status was assembled from
files on disk, and GoalRun was never started by anything outside its own tests.
Every word on that screen was true of a system that was not there.

So status is derived from a heartbeat rather than from inference. A worker that
is not ticking cannot be described as running, whatever the files suggest, and
the only way to display work is to have done some. Each step appends to an
activity log as it happens, so "what is it doing" is answered by a record of
what it did rather than by a sentence composed for the occasion.
"""

from __future__ import annotations

import json
import threading
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

from council.storage import write_json


EngineState = Literal["stopped", "starting", "running", "paused", "crashed", "finished"]

#: A heartbeat older than this means the worker is not alive, whatever the last
#: recorded state said. Chosen well above the tick interval so a slow step is
#: not mistaken for a death.
STALE_AFTER = timedelta(seconds=90)

#: The worker's own bookkeeping. Useful for debugging, meaningless to the person
#: who asked for revenue, and repeated on every tick — so it is kept out of the
#: activity a human reads.
ROUTINE_STEPS: frozenset[str] = frozenset({
    "observe", "diagnose", "classify", "readiness", "heartbeat",
})


@dataclass
class Activity:
    at: str
    step: str
    detail: str
    #: True when this touched the outside world. Everything else is internal.
    external: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"at": self.at, "step": self.step, "detail": self.detail, "external": self.external}


@dataclass
class Heartbeat:
    """Proof of life, written by the worker and read by everything else."""

    state: EngineState = "stopped"
    at: str = ""
    step: str = ""
    tick: int = 0
    error: str = ""

    @property
    def alive(self) -> bool:
        if self.state not in ("starting", "running"):
            return False
        if not self.at:
            return False
        try:
            beat = datetime.fromisoformat(self.at)
        except ValueError:
            return False
        return datetime.now(UTC) - beat < STALE_AFTER


class Engine:
    """Drives the run in the background and records what it actually did.

    Steps are supplied rather than hardcoded so the loop can be exercised
    without contacting anyone, and so a step that turns out to be wrong can be
    replaced without touching the machinery that proves it ran.
    """

    def __init__(
        self,
        path: Path,
        *,
        steps: list[tuple[str, Callable[[], str]]] | None = None,
        interval_seconds: float = 20.0,
        max_activity: int = 200,
    ):
        self.path = Path(path)
        self.steps = steps or []
        self.interval = interval_seconds
        self.activity: deque[Activity] = deque(maxlen=max_activity)
        self.heartbeat = Heartbeat()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._load()

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> bool:
        """Begin ticking. Returns False if a worker is already alive."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self.heartbeat = Heartbeat(state="starting", at=_now(), tick=0)
            self._save()
            self._thread = threading.Thread(target=self._loop, name="guildless-engine", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self._set_state("stopped", step="")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive()) and self.heartbeat.alive

    # -- the loop ------------------------------------------------------------

    def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                for name, step in self.steps:
                    if self._stop.is_set():
                        break
                    self._beat("running", name)
                    try:
                        detail = step() or ""
                    except Exception as exc:  # noqa: BLE001 - a bad step must not kill the company
                        self.record(name, f"失敗: {type(exc).__name__}: {str(exc)[:200]}")
                        continue
                    if detail:
                        self.record(name, detail)
                if self._stop.wait(self.interval):
                    break
        except Exception:  # noqa: BLE001 - a crash must be visible, not silent
            self.heartbeat.error = traceback.format_exc()[-800:]
            self._set_state("crashed", step=self.heartbeat.step)
            return
        self._set_state("stopped", step="")

    # -- recording -----------------------------------------------------------

    def record(self, step: str, detail: str, *, external: bool = False) -> None:
        self.activity.append(Activity(_now(), step, detail, external))
        self._save()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Everything, including the internal ticks. For developer detail only."""
        return [item.as_dict() for item in list(self.activity)[-limit:]][::-1]

    def notable(self, limit: int = 20) -> list[dict[str, Any]]:
        """Only what changed.

        A person watching this wants events, not a pulse. Repeating the same
        observation every twenty seconds is the heartbeat wearing an activity
        log's clothes, so an entry identical to the last one for its step is
        dropped, and the routine internal steps never appear at all.
        """
        shown: list[Activity] = []
        last_by_step: dict[str, str] = {}
        for item in self.activity:
            if item.step in ROUTINE_STEPS and not item.external:
                continue
            if last_by_step.get(item.step) == item.detail:
                continue
            last_by_step[item.step] = item.detail
            shown.append(item)
        return [item.as_dict() for item in shown[-limit:]][::-1]

    def status(self) -> dict[str, Any]:
        """What the screen may say about execution. Never inferred from files."""
        alive = self.running
        return {
            "state": self.heartbeat.state if alive else _settled(self.heartbeat.state),
            "alive": alive,
            "last_beat": self.heartbeat.at,
            # Routine steps are filtered here for the same reason ``notable``
            # drops them: "observe" and "readiness" are the worker's own
            # bookkeeping, and reporting one as what the company is doing puts
            # an internal identifier in front of a reader who asked about their
            # business. Empty is honest -- the caller falls back to the
            # decision's own description of the work.
            "current_step": (
                self.heartbeat.step
                if alive and self.heartbeat.step not in ROUTINE_STEPS
                else ""
            ),
            "ticks": self.heartbeat.tick,
            "error": self.heartbeat.error,
        }

    # -- internals -----------------------------------------------------------

    def _beat(self, state: EngineState, step: str) -> None:
        self.heartbeat.state = state
        self.heartbeat.step = step
        self.heartbeat.at = _now()
        self.heartbeat.tick += 1
        self._save()

    def _set_state(self, state: EngineState, *, step: str) -> None:
        self.heartbeat.state = state
        self.heartbeat.step = step
        self.heartbeat.at = _now()
        self._save()

    def _save(self) -> None:
        try:
            write_json(self.path, {
                "heartbeat": {
                    "state": self.heartbeat.state, "at": self.heartbeat.at,
                    "step": self.heartbeat.step, "tick": self.heartbeat.tick,
                    "error": self.heartbeat.error,
                },
                "activity": [item.as_dict() for item in self.activity],
            })
        except OSError:
            pass

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        beat = raw.get("heartbeat") or {}
        self.heartbeat = Heartbeat(
            state=beat.get("state", "stopped"), at=beat.get("at", ""),
            step=beat.get("step", ""), tick=int(beat.get("tick", 0)),
            error=beat.get("error", ""),
        )
        for item in raw.get("activity", []):
            self.activity.append(Activity(
                at=item.get("at", ""), step=item.get("step", ""),
                detail=item.get("detail", ""), external=bool(item.get("external")),
            ))


def _settled(previous: EngineState) -> EngineState:
    """What to call a worker that is not ticking.

    A recorded "running" with no heartbeat means the process died, and calling
    that running is the exact failure this module exists to prevent.
    """
    if previous in ("starting", "running"):
        return "crashed"
    return previous


def _now() -> str:
    return datetime.now(UTC).isoformat()
