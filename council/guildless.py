from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from council.config import Settings
from council.github_scout import GitHubScout
from council.guildless_prompts import (
    PROMPT_VERSION,
    criticism_prompt,
    judge_prompt,
    proposal_prompt,
    rebuttal_prompt,
)
from council.orchestrator import default_provider_factory
from council.providers.base import BaseProvider, ProviderResult, ProviderUnavailable
from council.schemas import (
    CouncilCriticism,
    GitHubSelectionConstraints,
    GuildlessDecision,
    RoleProposal,
    RoleRebuttal,
)
from council.security import COUNCIL_ROOT, validate_output_root
from council.storage import write_json


ROLE_ORDER = ("research", "sales", "finance")
JUDGE_PREFERENCE = ("codex", "sakana", "claude", "deepseek")
RunEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class GuildlessState(TypedDict, total=False):
    goal: str
    github_queries: list[str]
    context: dict[str, Any]
    constraints: dict[str, Any]
    max_rounds: int
    confidence_threshold: float
    github_snapshot: dict[str, Any]
    proposals: dict[str, dict[str, Any]]
    criticism: dict[str, Any]
    rebuttals: dict[str, dict[str, Any]]
    final_decision: dict[str, Any]
    round_number: int
    rounds_history: list[dict[str, Any]]
    unavailable: list[dict[str, Any]]
    call_audit: list[dict[str, Any]]
    controller_status: Literal["ready", "additional_research", "hold"]


@dataclass(frozen=True)
class GuildlessRunResult:
    run_id: str
    run_dir: Path
    request_hash: str
    status: str
    final_decision: dict[str, Any]


class GuildlessOrchestrator:
    """Guildless MVP graph: research -> independent proposals -> attack -> rebut -> judge."""

    def __init__(
        self,
        settings: Settings,
        providers: dict[str, BaseProvider] | None = None,
        *,
        github_scout: GitHubScout | None = None,
        output_boundary: Path = COUNCIL_ROOT,
    ):
        self.settings = settings
        self.providers = providers or default_provider_factory(settings)
        self.github_scout = github_scout or GitHubScout(timeout_seconds=settings.timeout_seconds)
        self.output_boundary = output_boundary
        self._run_dir: Path | None = None
        self._request_hash = ""
        self._event_callback: RunEventCallback | None = None
        self._allowed: tuple[str, ...] = ()
        self._judge_provider = ""
        self._proposer_providers: tuple[str, ...] = ()
        self.graph = self._build_graph()

    async def aclose(self) -> None:
        await asyncio.gather(
            *(provider.aclose() for provider in self.providers.values()),
            self.github_scout.aclose(),
        )

    def _build_graph(self):
        builder = StateGraph(GuildlessState)
        builder.add_node("research_github", self._research_github)
        builder.add_node("independent_proposals", self._independent_proposals)
        builder.add_node("devils_advocate", self._devils_advocate)
        builder.add_node("rebuttals", self._rebuttals)
        builder.add_node("judge", self._judge)
        builder.add_edge(START, "research_github")
        builder.add_edge("research_github", "independent_proposals")
        builder.add_edge("independent_proposals", "devils_advocate")
        builder.add_edge("devils_advocate", "rebuttals")
        builder.add_edge("rebuttals", "judge")
        builder.add_conditional_edges(
            "judge",
            self._after_judge,
            {"debate_again": "devils_advocate", "finish": END},
        )
        return builder.compile(checkpointer=InMemorySaver())

    async def run(
        self,
        *,
        goal: str,
        github_queries: list[str],
        context: dict[str, Any],
        constraints: GitHubSelectionConstraints,
        allowed_providers: list[str],
        max_rounds: int = 3,
        confidence_threshold: float = 0.8,
        output_dir: Path | None = None,
        run_id: str | None = None,
        event_callback: RunEventCallback | None = None,
    ) -> GuildlessRunResult:
        goal = goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")
        allowed = tuple(dict.fromkeys(allowed_providers))
        if len(allowed) < 2:
            raise ValueError("Guildless requires at least two allowed providers for an independent Judge")
        unknown = set(allowed) - set(self.providers)
        if unknown:
            raise ValueError(f"Unknown allowed providers: {sorted(unknown)}")
        self._judge_provider = next(name for name in JUDGE_PREFERENCE if name in allowed)
        self._proposer_providers = tuple(name for name in allowed if name != self._judge_provider)
        if not self._proposer_providers:
            raise ValueError("No proposer remains after reserving the independent Judge")
        self._allowed = allowed
        self._event_callback = event_callback

        canonical_core = {
            "schema_version": "1.0",
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "prompt_version": PROMPT_VERSION,
            "goal": goal,
            "github_queries": github_queries,
            "context": context,
            "constraints": constraints.model_dump(mode="json"),
            "allowed_providers": list(allowed),
            "max_rounds": max_rounds,
            "confidence_threshold": confidence_threshold,
        }
        canonical_bytes = json.dumps(
            canonical_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self._request_hash = hashlib.sha256(canonical_bytes).hexdigest()
        safe_output = validate_output_root(output_dir or self.settings.output_dir, self.output_boundary)
        run_name = run_id or (
            "guildless_"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ_")
            + self._request_hash[:12]
        )
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", run_name):
            raise ValueError("run_id contains unsafe characters")
        self._run_dir = safe_output / run_name
        write_json(
            self._run_dir / "request.json",
            {
                **canonical_core,
                "request_hash": self._request_hash,
                "created_at": datetime.now(UTC).isoformat(),
                "automatic_external_actions": False,
            },
        )
        await self._emit("preparing_context", {"stage": "github_research"})
        initial: GuildlessState = {
            "goal": goal,
            "github_queries": github_queries,
            "context": context,
            "constraints": constraints.model_dump(mode="json"),
            "max_rounds": max_rounds,
            "confidence_threshold": confidence_threshold,
            "round_number": 0,
            "rounds_history": [],
            "unavailable": [],
            "call_audit": [],
        }
        try:
            final_state = await self.graph.ainvoke(
                initial,
                config={"configurable": {"thread_id": run_name}},
            )
        except Exception as exc:
            failure = {
                "status": "failed",
                "request_hash": self._request_hash,
                "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                "automatic_external_actions": False,
            }
            write_json(self._run_dir / "run_error.json", failure)
            write_json(self._run_dir / "run_status.json", failure)
            await self._emit("failed", {"error": failure["error"]})
            raise

        final_decision = final_state["final_decision"]
        unavailable = final_state.get("unavailable", [])
        status = "degraded" if unavailable else "completed"
        blackboard = {
            "goal": goal,
            "evidence": final_state["github_snapshot"],
            "hypotheses": {
                role: proposal.get("hypotheses", [])
                for role, proposal in final_state["proposals"].items()
            },
            "proposals": final_state["proposals"],
            "objections": final_state["criticism"],
            "rebuttals": final_state["rebuttals"],
            "decision": final_decision,
            "actions": [],
            "results": [],
        }
        write_json(self._run_dir / "blackboard.json", blackboard)
        write_json(self._run_dir / "final_decision.json", final_decision)
        write_json(
            self._run_dir / "candidate_record.json",
            {
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "confirmed_decision": False,
                "automatic_promotion_supported": False,
                "automatic_external_actions": False,
                "run_id": run_name,
                "request_hash": self._request_hash,
                "controller_status": final_state["controller_status"],
                "final_decision": final_decision,
            },
        )
        write_json(
            self._run_dir / "audit.json",
            {
                "request_hash": self._request_hash,
                "github_snapshot_sha256": final_state["github_snapshot"]["snapshot_sha256"],
                "graph": [
                    "research_github",
                    "independent_proposals",
                    "devils_advocate",
                    "rebuttals",
                    "judge",
                ],
                "rounds": final_state.get("rounds_history", []),
                "provider_calls": final_state.get("call_audit", []),
                "provider_unavailable": unavailable,
                "judge_provider": self._judge_provider,
                "judge_was_not_proposer": self._judge_provider not in self._proposer_providers,
                "external_actions": [],
            },
        )
        write_json(
            self._run_dir / "run_status.json",
            {
                "status": status,
                "request_hash": self._request_hash,
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "controller_status": final_state["controller_status"],
                "automatic_external_actions": False,
            },
        )
        await self._emit(status, {"controller_status": final_state["controller_status"]})
        return GuildlessRunResult(run_name, self._run_dir, self._request_hash, status, final_decision)

    async def _research_github(self, state: GuildlessState) -> dict[str, Any]:
        constraints = GitHubSelectionConstraints.model_validate(state["constraints"])
        snapshot = await self.github_scout.research(state["github_queries"], constraints)
        self._write("github_selection.json", snapshot)
        return {"github_snapshot": snapshot}

    async def _independent_proposals(self, state: GuildlessState) -> dict[str, Any]:
        await self._emit("proposing", {"roles": list(ROLE_ORDER), "independent": True})

        async def run_role(index: int, role: str):
            provider_name = self._proposer_providers[index % len(self._proposer_providers)]
            system, user = proposal_prompt(
                role, state["goal"], state["github_snapshot"], state["context"]
            )
            return role, await self._generate(
                provider_name,
                stage="independent_proposals",
                call_id=f"proposal_{role}",
                system_prompt=system,
                user_prompt=user,
                schema_model=RoleProposal,
                schema_name=f"guildless_{role}_proposal",
                deterministic=False,
            )

        completed = await asyncio.gather(
            *(run_role(index, role) for index, role in enumerate(ROLE_ORDER)),
            return_exceptions=True,
        )
        proposals: dict[str, dict[str, Any]] = {}
        unavailable = list(state.get("unavailable", []))
        call_audit = list(state.get("call_audit", []))
        for item in completed:
            if isinstance(item, Exception):
                unavailable.append(self._unavailable_record(item, "independent_proposals"))
                continue
            role, result = item
            proposals[role] = result.parsed
            call_audit.append(self._call_record(f"proposal_{role}", result))
        if len(proposals) < 2:
            raise RuntimeError("Fewer than two independent specialist proposals completed")
        self._write("proposals.json", proposals)
        return {"proposals": proposals, "unavailable": unavailable, "call_audit": call_audit}

    async def _devils_advocate(self, state: GuildlessState) -> dict[str, Any]:
        round_number = int(state.get("round_number", 0)) + 1
        await self._emit("criticizing", {"round": round_number, "stage": "devils_advocate"})
        aliases = self._anonymize(state["proposals"])
        system, user = criticism_prompt(
            state["goal"], aliases, state["github_snapshot"]
        )
        provider_name = self._proposer_providers[0]
        result = await self._generate(
            provider_name,
            stage="devils_advocate",
            call_id=f"critic_round_{round_number}",
            system_prompt=system,
            user_prompt=user,
            schema_model=CouncilCriticism,
            schema_name="guildless_council_criticism",
            deterministic=True,
        )
        self._write(f"criticism_round_{round_number}.json", result.parsed)
        return {
            "round_number": round_number,
            "criticism": result.parsed,
            "call_audit": [*state.get("call_audit", []), self._call_record(f"critic_round_{round_number}", result)],
        }

    async def _rebuttals(self, state: GuildlessState) -> dict[str, Any]:
        round_number = state["round_number"]

        async def run_role(index: int, role: str, proposal: dict[str, Any]):
            provider_name = self._proposer_providers[index % len(self._proposer_providers)]
            system, user = rebuttal_prompt(
                role,
                state["goal"],
                proposal,
                state["criticism"],
                state["github_snapshot"],
            )
            return role, await self._generate(
                provider_name,
                stage="rebuttals",
                call_id=f"rebuttal_{role}_round_{round_number}",
                system_prompt=system,
                user_prompt=user,
                schema_model=RoleRebuttal,
                schema_name=f"guildless_{role}_rebuttal",
                deterministic=False,
            )

        completed = await asyncio.gather(
            *(
                run_role(index, role, proposal)
                for index, (role, proposal) in enumerate(state["proposals"].items())
            ),
            return_exceptions=True,
        )
        rebuttals: dict[str, dict[str, Any]] = {}
        unavailable = list(state.get("unavailable", []))
        call_audit = list(state.get("call_audit", []))
        for item in completed:
            if isinstance(item, Exception):
                unavailable.append(self._unavailable_record(item, "rebuttals"))
                continue
            role, result = item
            rebuttals[role] = result.parsed
            call_audit.append(self._call_record(f"rebuttal_{role}_round_{round_number}", result))
        self._write(f"rebuttals_round_{round_number}.json", rebuttals)
        return {"rebuttals": rebuttals, "unavailable": unavailable, "call_audit": call_audit}

    async def _judge(self, state: GuildlessState) -> dict[str, Any]:
        round_number = state["round_number"]
        await self._emit("judging", {"round": round_number, "judge": self._judge_provider})
        aliases = self._anonymize(state["proposals"])
        rebuttal_aliases = self._anonymize(state.get("rebuttals", {}))
        system, user = judge_prompt(
            state["goal"],
            aliases,
            state["criticism"],
            rebuttal_aliases,
            state["github_snapshot"],
        )
        result = await self._generate(
            self._judge_provider,
            stage="judge",
            call_id=f"judge_round_{round_number}",
            system_prompt=system,
            user_prompt=user,
            schema_model=GuildlessDecision,
            schema_name="guildless_final_decision",
            deterministic=True,
        )
        confidence = float(result.parsed["confidence"])
        if confidence >= state["confidence_threshold"]:
            controller_status: Literal["ready", "additional_research", "hold"] = "ready"
        elif confidence >= 0.5:
            controller_status = "additional_research"
        else:
            controller_status = "hold"
        history = [
            *state.get("rounds_history", []),
            {
                "round": round_number,
                "criticism": state["criticism"],
                "rebuttals": state.get("rebuttals", {}),
                "judge": result.parsed,
                "controller_status": controller_status,
            },
        ]
        self._write(f"decision_round_{round_number}.json", result.parsed)
        return {
            "final_decision": result.parsed,
            "controller_status": controller_status,
            "rounds_history": history,
            "call_audit": [*state.get("call_audit", []), self._call_record(f"judge_round_{round_number}", result)],
        }

    @staticmethod
    def _after_judge(state: GuildlessState) -> str:
        if (
            state["controller_status"] == "additional_research"
            and state["round_number"] < state["max_rounds"]
        ):
            return "debate_again"
        return "finish"

    async def _generate(
        self,
        provider_name: str,
        *,
        stage: str,
        call_id: str,
        **kwargs,
    ) -> ProviderResult:
        provider = self.providers[provider_name]
        try:
            return await provider.generate_json(**kwargs)
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise ProviderUnavailable(
                f"Unexpected provider failure: {type(exc).__name__}: {str(exc)[:300]}",
                provider=provider_name,
                model=provider.config.model,
                reason="provider_error",
            ) from exc

    @staticmethod
    def _anonymize(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {
            chr(ord("A") + index): value
            for index, (_, value) in enumerate(sorted(items.items()))
        }

    @staticmethod
    def _call_record(call_id: str, result: ProviderResult) -> dict[str, Any]:
        return {"call_id": call_id, **result.audit_dict()}

    @staticmethod
    def _unavailable_record(exc: Exception, stage: str) -> dict[str, Any]:
        if isinstance(exc, ProviderUnavailable):
            return exc.audit_dict(stage)
        return {
            "status": "provider_unavailable",
            "stage": stage,
            "reason": "provider_error",
            "message": f"{type(exc).__name__}: {str(exc)[:300]}",
            "automatic_api_fallback": False,
        }

    def _write(self, name: str, value: Any) -> None:
        if self._run_dir is None:
            raise RuntimeError("run directory is not initialized")
        write_json(self._run_dir / name, value)

    async def _emit(self, status: str, details: dict[str, Any]) -> None:
        if self._event_callback is not None:
            await self._event_callback(status, details)
