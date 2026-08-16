"""Runs a goal to its end without handing intermediate work back to a person.

The failure this fixes is not a missing capability. Guildless could already
research, build, test and sell; it simply stopped after each step and asked
whether to continue. A system that needs a human to supply the next move is a
competent worker, not something that brings back a result, and the human ends
up supplying the product ideas, the channels, the legal reading and the tools
one at a time — which is the entire job it was meant to do.

So continuation is not a behaviour to encourage in a prompt. It is a rule with
one exception. A run may stop only for work a person is legally required to do:
identity checks, consent, signatures, irreversible high-risk approvals, and
things in the physical world. Everything else — a dead provider, a fabricated
quote, an unlawful channel, an offer nobody wants, no offer at all — is the
run's own problem, and it either routes around it or changes strategy.

Terminal conditions are money and time, not effort. Success is verified net
profit above zero. Failure is the deadline, the loss cap, or genuinely running
out of strategies. "Tried hard" is not an outcome.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Literal

from council.human_role import may_ask_human
from council.proof import FailureKind, Measurements, evaluate


TerminalState = Literal["running", "succeeded", "failed", "awaiting_human"]

FailureReason = Literal["deadline", "max_loss", "no_viable_strategy", "watchdog_stop"]


class Blocked(Exception):
    """A step could not proceed.

    ``task`` names the work that is blocked, and the policy — never the caller,
    and never a model — decides whether a human may be asked for it.
    """

    def __init__(self, task: str, detail: str = ""):
        super().__init__(detail or task)
        self.task = task
        self.detail = detail


@dataclass(frozen=True)
class Goal:
    objective: str = "real_net_profit > 0"
    capital_yen: int = 5_000
    deadline_days: int = 7
    max_loss_yen: int = 2_000
    #: How much digital work the customer may be left with. Zero means the run
    #: absorbs everything a person is not legally required to do.
    human_digital_work: int = 0


@dataclass
class HumanTask:
    task: str
    detail: str
    raised_at: str


@dataclass
class Attempt:
    strategy: str
    step: str
    ok: bool
    note: str
    at: str


@dataclass
class RunOutcome:
    state: TerminalState
    net_yen: int
    reason: str
    failure: FailureReason | None = None
    human_task: HumanTask | None = None
    strategies_tried: int = 0
    attempts: list[Attempt] = field(default_factory=list)


class ContinuationPolicy:
    """Decides what may interrupt a run. Deliberately not configurable per-step.

    ``pivot_after`` bounds persistence: repeating a strategy that has failed the
    same way three times is not diligence, it is the meltdown loop that has
    already been observed in systems like this one.
    """

    def __init__(self, *, pivot_after: int = 3):
        self.pivot_after = pivot_after

    def may_stop_for(self, task: str) -> bool:
        """Only legally-human work can pause a run."""
        return may_ask_human(task).allowed

    def should_pivot(self, failures: Counter[str]) -> bool:
        return any(count >= self.pivot_after for count in failures.values())


@dataclass
class Strategy:
    """One way of pursuing the goal: what to sell and how to reach buyers.

    ``steps`` run in order. Any of them may raise :class:`Blocked`, and the
    runner decides — without asking anyone — whether that ends the strategy or
    the run.
    """

    name: str
    steps: list[tuple[str, Callable[[], Any]]]
    #: Produces the counted results once the steps have run.
    measure: Callable[[], Measurements]


class GoalRun:
    """Drives strategies until the goal is met, the money runs out, or time is."""

    def __init__(
        self,
        goal: Goal,
        strategies: Callable[[], list[Strategy]],
        *,
        policy: ContinuationPolicy | None = None,
        spent_yen: Callable[[], int] = lambda: 0,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        watchdog: Callable[[], list[str]] = list,
    ):
        self.goal = goal
        # A callable rather than a list: when every known strategy fails, the
        # run asks for more instead of ending. Discovering new options is its
        # own work, not a question for the user.
        self.strategies = strategies
        self.policy = policy or ContinuationPolicy()
        self.spent_yen = spent_yen
        self.now = now
        self.watchdog = watchdog
        self.attempts: list[Attempt] = []
        self.started_at = self.now()

    def run(self) -> RunOutcome:
        tried = 0
        exhausted_rounds = 0

        while True:
            terminal = self._terminal_check(tried)
            if terminal is not None:
                return terminal

            batch = self.strategies()
            if not batch:
                exhausted_rounds += 1
                # One empty round means the current approach found nothing; two
                # means there is genuinely nothing left to try.
                if exhausted_rounds >= 2:
                    return self._fail("no_viable_strategy", "実行可能な戦略が尽きました", tried)
                continue
            exhausted_rounds = 0

            for strategy in batch:
                tried += 1
                terminal = self._terminal_check(tried)
                if terminal is not None:
                    return terminal

                outcome = self._run_strategy(strategy)
                if outcome is not None:
                    return outcome

    # -- one strategy --------------------------------------------------------

    def _run_strategy(self, strategy: Strategy) -> RunOutcome | None:
        """Returns a terminal outcome, or None to move to the next strategy."""
        failures: Counter[str] = Counter()

        for step_name, step in strategy.steps:
            try:
                step()
            except Blocked as blocker:
                if self.policy.may_stop_for(blocker.task):
                    self._record(strategy.name, step_name, False, f"人間必須: {blocker.task}")
                    return RunOutcome(
                        state="awaiting_human",
                        net_yen=-self.spent_yen(),
                        reason=blocker.detail or blocker.task,
                        human_task=HumanTask(
                            blocker.task, blocker.detail, self.now().isoformat()
                        ),
                        strategies_tried=1,
                        attempts=list(self.attempts),
                    )
                # Not human-only work, so it is this run's problem. Abandon the
                # strategy rather than the goal, and never ask about it.
                failures[blocker.task] += 1
                self._record(strategy.name, step_name, False, f"自律回避: {blocker.detail}")
                if self.policy.should_pivot(failures):
                    return None
                return None
            except Exception as exc:  # noqa: BLE001 - a broken step is a dead strategy, not a dead run
                failures[step_name] += 1
                self._record(strategy.name, step_name, False, f"{type(exc).__name__}: {str(exc)[:80]}")
                return None
            else:
                self._record(strategy.name, step_name, True, "完了")

        measurements = strategy.measure()
        result = evaluate(measurements)
        if result.passed:
            self._record(strategy.name, "proof", True, result.reason)
            return RunOutcome(
                state="succeeded",
                net_yen=result.net_yen,
                reason=result.reason,
                strategies_tried=1,
                attempts=list(self.attempts),
            )
        self._record(strategy.name, "proof", False, f"{result.failure}: {result.reason}")
        return None

    # -- terminal conditions -------------------------------------------------

    def _terminal_check(self, tried: int) -> RunOutcome | None:
        if self.now() - self.started_at >= timedelta(days=self.goal.deadline_days):
            return self._fail("deadline", f"期限{self.goal.deadline_days}日を超えました", tried)
        if self.spent_yen() >= self.goal.max_loss_yen:
            return self._fail(
                "max_loss",
                f"損失上限¥{self.goal.max_loss_yen:,}に到達しました",
                tried,
            )
        alarms = self.watchdog()
        if alarms:
            return self._fail("watchdog_stop", "; ".join(alarms), tried)
        return None

    def _fail(self, reason: FailureReason, message: str, tried: int) -> RunOutcome:
        return RunOutcome(
            state="failed",
            net_yen=-self.spent_yen(),
            reason=message,
            failure=reason,
            strategies_tried=tried,
            attempts=list(self.attempts),
        )

    def _record(self, strategy: str, step: str, ok: bool, note: str) -> None:
        self.attempts.append(
            Attempt(strategy, step, ok, note, self.now().isoformat())
        )

    # -- reporting -----------------------------------------------------------

    def surface(self, outcome: RunOutcome) -> dict[str, Any]:
        """What the user sees by default: outcome, money, and any human task.

        Intermediate work is deliberately absent. Reporting each step back is
        the habit this module exists to break.
        """
        return {
            "goal": self.goal.objective,
            "status": outcome.state,
            "capital_yen": self.goal.capital_yen - self.spent_yen(),
            "net_profit_yen": outcome.net_yen,
            "human_action_required": outcome.human_task.task if outcome.human_task else "NONE",
            "deadline_remaining_hours": max(
                0,
                int(
                    (
                        self.started_at
                        + timedelta(days=self.goal.deadline_days)
                        - self.now()
                    ).total_seconds()
                    // 3600
                ),
            ),
        }

    def inspect(self, outcome: RunOutcome) -> list[dict[str, Any]]:
        """The intermediate detail, available on request and not before."""
        return [
            {"strategy": a.strategy, "step": a.step, "ok": a.ok, "note": a.note, "at": a.at}
            for a in outcome.attempts
        ]
