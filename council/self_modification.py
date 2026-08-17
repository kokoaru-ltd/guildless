"""Lets Guildless change its own code, but only to clear a measured blockage.

A system allowed to improve itself freely will improve itself forever. It is
far more engaging to refactor an architecture than to sell anything, and the
resulting work is real, defensible, and produces no money. So the gate is not
"is this a good change" — it is "is something in the current run measurably
stuck on this".

Every change has to pass the tests and be revertible. An autonomous edit that
breaks the company and cannot be undone is worse than the bottleneck it was
trying to clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable

from council.discovery import Bottleneck


#: Rationales that sound like progress and are not tied to anything blocked.
VANITY_PATTERNS: tuple[str, ...] = (
    "もっと良い", "きれいに", "リファクタ", "将来のため", "一般化",
    "better architecture", "cleanup", "refactor", "future-proof", "generalise",
)

#: The boundary the system may never edit. A company that can widen its own
#: permissions, raise its own spending limits, or reclassify work a person is
#: legally required to do has no limits at all -- and every guarantee above
#: rests on these staying beyond reach.
PROTECTED_MODULES: frozenset[str] = frozenset({
    "council/grant.py",
    "council/human_role.py",
    "council/capital.py",
    "council/gates.py",
    "council/self_modification.py",
    # The definition of success. An agent able to edit this would eventually
    # widen it, and a system that can redefine winning always wins.
    "council/ignition.py",
    "council/sender_identity.py",
})


@dataclass
class ModificationRequest:
    bottleneck: Bottleneck
    #: What the change does, in terms of the blockage it clears.
    rationale: str
    apply: Callable[[], None]
    revert: Callable[[], None]
    #: Files the change would touch. Anything protected ends the request.
    targets: tuple[str, ...] = ()


@dataclass
class ModificationResult:
    allowed: bool
    applied: bool
    reason: str
    reverted: bool = False


@dataclass
class ModificationLog:
    entries: list[dict[str, str]] = field(default_factory=list)

    def record(self, request: ModificationRequest, result: ModificationResult) -> None:
        self.entries.append({
            "at": datetime.now(UTC).isoformat(),
            "capability": request.bottleneck.capability,
            "strategy": request.bottleneck.blocked_strategy,
            "rationale": request.rationale,
            "allowed": str(result.allowed),
            "applied": str(result.applied),
            "reverted": str(result.reverted),
            "reason": result.reason,
        })


class SelfModificationPolicy:
    """Decides whether a code change to Guildless itself is permitted."""

    def __init__(self, *, log: ModificationLog | None = None):
        self.log = log or ModificationLog()

    def evaluate(self, request: ModificationRequest) -> ModificationResult:
        bottleneck = request.bottleneck

        # Checked before anything else, including whether the bottleneck is
        # real. A perfectly justified reason to widen one's own permissions is
        # still a reason to widen one's own permissions.
        protected = [
            path for path in request.targets
            if _normalise(path) in PROTECTED_MODULES
        ]
        if protected:
            return ModificationResult(
                False, False,
                f"権限・資金・人間境界に関わる{', '.join(protected)}は自己改造できません",
            )

        if not bottleneck.actionable:
            return ModificationResult(
                False, False,
                "具体的なボトルネックが示されていないため自己改造を許可しません",
            )
        if not bottleneck.blocked_strategy.strip():
            return ModificationResult(
                False, False,
                "どの戦略が止まっているのか特定されていません",
            )
        lowered = request.rationale.lower()
        if any(pattern.lower() in lowered for pattern in VANITY_PATTERNS):
            return ModificationResult(
                False, False,
                "改善一般を目的とする変更は許可しません。止まっている処理の解消のみ許可します",
            )
        return ModificationResult(True, False, "計測されたボトルネックの解消に該当します")

    def apply(
        self,
        request: ModificationRequest,
        *,
        run_tests: Callable[[], tuple[bool, str]],
    ) -> ModificationResult:
        """Apply the change, and undo it if the tests do not pass."""
        verdict = self.evaluate(request)
        if not verdict.allowed:
            self.log.record(request, verdict)
            return verdict

        try:
            request.apply()
        except Exception as exc:  # noqa: BLE001 - a failed edit must never be left half-done
            request.revert()
            result = ModificationResult(
                True, False, f"適用に失敗したため元に戻しました: {type(exc).__name__}", True
            )
            self.log.record(request, result)
            return result

        passed, detail = run_tests()
        if not passed:
            request.revert()
            result = ModificationResult(
                True, False, f"テストが失敗したため元に戻しました: {detail[:160]}", True
            )
            self.log.record(request, result)
            return result

        result = ModificationResult(True, True, "テスト通過。変更を採用しました")
        self.log.record(request, result)
        return result


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")
