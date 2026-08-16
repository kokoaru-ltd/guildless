"""The only door to the outside world.

Everything that leaves the machine — an email, a call, a post, a payment link,
a purchase, a deploy — goes through here. Agents do not hold API clients. This
is not a style preference: an autonomous system that can reach the world
directly has no place to put the checks that stop it sending the same pitch
twice, spending money it does not have, or hammering a dead provider forever.

The checks run cheapest-and-most-certain first, so a duplicate is caught before
any budget is touched and a blown budget is caught before any provider is called.

Two properties matter more than the rest:

* An action that already happened is never repeated. The idempotency key is the
  caller's promise about identity, and a replay returns the original result
  rather than doing the thing again.
* Money is reserved before the action and settled after it. If the executor
  raises, the reservation is released, because charging the company for a send
  that never left is how a wallet quietly empties.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

from council.capital import CapitalAllocator
from council.storage import write_json


#: Everything that can reach a third party. Adding a capability means adding it
#: here, which is the point: there is no other way out.
ActionKind = Literal[
    "send_email",
    "make_call",
    "publish_post",
    "spend_money",
    "create_payment_link",
    "purchase",
    "deploy",
]

Status = Literal["executed", "denied", "duplicate", "failed"]

#: Actions that reach a person or move money. These can never be silently
#: retried and always need an explicit human envelope of approval upstream.
IRREVERSIBLE: frozenset[str] = frozenset(
    {"send_email", "make_call", "publish_post", "spend_money", "purchase", "create_payment_link"}
)


@dataclass
class ActionRequest:
    kind: ActionKind
    #: Caller's identity for this action. Same key means "the same real-world
    #: thing", so two requests sharing one must never both happen.
    idempotency_key: str
    #: Who or what it lands on. Used for per-target rate limits.
    target: str
    purpose: str
    amount_yen: int = 0
    envelope: str = "experiment"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    status: Status
    reason: str
    action_id: str = ""
    idempotency_key: str = ""
    kind: str = ""
    target: str = ""
    amount_yen: int = 0
    at: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "executed"


class ActionGateway:
    def __init__(
        self,
        path: Path,
        capital: CapitalAllocator,
        *,
        dry_run: bool = True,
        policy: Callable[[ActionRequest], str | None] | None = None,
        health: Callable[[ActionRequest], str | None] | None = None,
        max_per_target: int = 3,
    ):
        """
        ``dry_run`` defaults to True so that wiring this up cannot, by itself,
        start contacting real people. Live traffic has to be switched on
        deliberately.

        ``policy`` and ``health`` return a refusal reason, or None to allow.
        """
        self.path = Path(path)
        self.capital = capital
        self.dry_run = dry_run
        self.policy = policy
        self.health = health
        self.max_per_target = max_per_target
        self.log: list[dict[str, Any]] = self._load()

    def execute(
        self,
        request: ActionRequest,
        executor: Callable[[ActionRequest], dict[str, Any]] | None = None,
    ) -> ActionResult:
        prior = self._find(request.idempotency_key)
        if prior is not None:
            return ActionResult(
                status="duplicate",
                reason="この操作は実行済みです。二重実行はしません。",
                action_id=prior["action_id"],
                idempotency_key=request.idempotency_key,
                kind=prior["kind"],
                target=prior["target"],
                amount_yen=int(prior.get("amount_yen", 0)),
                at=prior["at"],
                detail=prior.get("detail", {}),
            )

        contacted = self._count_for_target(request.target)
        if request.kind in IRREVERSIBLE and contacted >= self.max_per_target:
            return self._record(
                request, "denied", f"{request.target}への接触が上限{self.max_per_target}回に達しています"
            )

        if self.policy is not None:
            refusal = self.policy(request)
            if refusal:
                return self._record(request, "denied", refusal)

        reservation_id = ""
        if request.amount_yen > 0:
            decision = self.capital.request(request.envelope, request.amount_yen, request.purpose)
            if not decision.approved:
                return self._record(request, "denied", decision.reason)
            reservation_id = decision.reservation.reservation_id

        # Health is checked last because it is the only check that can change
        # between now and the call, and holding a reservation across it is safe.
        if self.health is not None:
            unhealthy = self.health(request)
            if unhealthy:
                if reservation_id:
                    self.capital.release(reservation_id)
                return self._record(request, "denied", unhealthy)

        if self.dry_run or executor is None:
            if reservation_id:
                self.capital.release(reservation_id)
            return self._record(
                request,
                "denied",
                "dry_runのため外部には何も送信していません",
                detail={"dry_run": True},
            )

        try:
            detail = executor(request) or {}
        except Exception as exc:  # noqa: BLE001 - any executor failure must free the money
            if reservation_id:
                self.capital.release(reservation_id)
            return self._record(
                request, "failed", f"{type(exc).__name__}: {str(exc)[:200]}"
            )

        if reservation_id:
            self.capital.commit(reservation_id, int(detail.get("actual_cost_yen", request.amount_yen)))
        return self._record(request, "executed", "実行しました", detail=detail)

    # -- reading ------------------------------------------------------------

    def history(self, *, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        rows = [row for row in self.log if kind is None or row["kind"] == kind]
        return rows[-limit:]

    def executed_count(self, kind: str | None = None) -> int:
        return sum(
            1
            for row in self.log
            if row["status"] == "executed" and (kind is None or row["kind"] == kind)
        )

    # -- internals ----------------------------------------------------------

    def _find(self, idempotency_key: str) -> dict[str, Any] | None:
        for row in self.log:
            # Only settled attempts block a retry. A denial or a crash left no
            # trace in the world, so the caller is allowed to try again.
            if row["idempotency_key"] == idempotency_key and row["status"] == "executed":
                return row
        return None

    def _count_for_target(self, target: str) -> int:
        return sum(
            1 for row in self.log if row["target"] == target and row["status"] == "executed"
        )

    def _record(
        self,
        request: ActionRequest,
        status: Status,
        reason: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> ActionResult:
        result = ActionResult(
            status=status,
            reason=reason,
            action_id=uuid.uuid4().hex,
            idempotency_key=request.idempotency_key,
            kind=request.kind,
            target=request.target,
            amount_yen=request.amount_yen,
            at=datetime.now(UTC).isoformat(),
            detail=detail or {},
        )
        self.log.append(asdict(result))
        write_json(self.path, self.log)
        return result

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
