from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from council.config import Settings
from council.prompts import PROMPT_VERSION, critique_prompts, judge_prompts, proposal_prompts
from council.providers import ClaudeProvider, DeepSeekProvider, OpenAIProvider, SakanaProvider
from council.providers.base import BaseProvider, ProviderResult, ProviderUnavailable
from council.schemas import Critique, FinalDecision, Proposal
from council.security import COUNCIL_ROOT, ContextPolicy, validate_output_root
from council.storage import write_json


ROLES = {
    "general": ("claude", "deepseek", "codex"),
    "architecture": ("claude", "deepseek", "codex"),
    "implementation": ("deepseek", "codex", "claude"),
    "evaluation_design": ("codex", "claude", "deepseek"),
}
VALID_MODES = {"fast", "local", "thorough", "benchmark"}


@dataclass(frozen=True)
class CouncilRunResult:
    run_id: str
    run_dir: Path
    request_hash: str
    final_decision: dict[str, Any]
    total_cost_usd: float
    status: str


RunEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def default_provider_factory(settings: Settings) -> dict[str, BaseProvider]:
    kwargs = {
        "timeout_seconds": settings.timeout_seconds,
        "max_retries": settings.max_retries,
        "runtime_dir": settings.runtime_dir,
    }
    return {
        "claude": ClaudeProvider(settings.providers["claude"], **kwargs),
        "deepseek": DeepSeekProvider(settings.providers["deepseek"], **kwargs),
        "codex": OpenAIProvider(settings.providers["codex"], **kwargs),
        "sakana": SakanaProvider(settings.providers["sakana"], **kwargs),
    }


class CouncilOrchestrator:
    def __init__(
        self,
        settings: Settings,
        providers: dict[str, BaseProvider] | None = None,
        *,
        output_boundary: Path = COUNCIL_ROOT,
    ):
        self.settings = settings
        self.providers = providers or default_provider_factory(settings)
        self.output_boundary = output_boundary

    async def aclose(self) -> None:
        await asyncio.gather(*(provider.aclose() for provider in self.providers.values()))

    async def ask(
        self,
        *,
        question: str,
        task_type: str,
        mode: str,
        context_paths: list[str] | None = None,
        inline_context: dict[str, Any] | None = None,
        allowed_providers: list[str] | None = None,
        output_dir: Path | None = None,
        run_id: str | None = None,
        event_callback: RunEventCallback | None = None,
    ) -> CouncilRunResult:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")
        if task_type not in ROLES:
            raise ValueError(f"Unknown task_type: {task_type}")
        if mode not in VALID_MODES:
            raise ValueError(f"Unknown mode: {mode}")
        if context_paths and inline_context is not None:
            raise ValueError("context_paths and inline_context are mutually exclusive")
        allowed = frozenset(allowed_providers or self.providers)
        unknown_providers = allowed - set(self.providers)
        if unknown_providers:
            raise ValueError(f"Unknown allowed_providers: {sorted(unknown_providers)}")
        if not allowed:
            raise ValueError("allowed_providers must not be empty")

        await self._emit(event_callback, "preparing_context", {"context_kind": "inline" if inline_context is not None else "explicit_files"})
        policy = ContextPolicy(self.settings.max_context_bytes)
        documents = policy.read_inline(inline_context) if inline_context is not None else policy.read_explicit(context_paths or [])
        canonical_core = {
            "schema_version": "1.2",
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "prompt_version": PROMPT_VERSION,
            "mode": mode,
            "task_type": task_type,
            "question": question,
            "contexts": [asdict(document) for document in documents],
            "allowed_providers": sorted(allowed),
        }
        canonical_bytes = json.dumps(
            canonical_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        request_hash = hashlib.sha256(canonical_bytes).hexdigest()
        canonical = {
            **canonical_core,
            "request_hash": request_hash,
            "created_at": datetime.now(UTC).isoformat(),
        }
        run_name = run_id or (datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ_") + request_hash[:12])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_name):
            raise ValueError("run_id contains unsafe characters")
        safe_output_root = validate_output_root(output_dir or self.settings.output_dir, self.output_boundary)
        run_dir = safe_output_root / run_name
        write_json(run_dir / "canonical_request.json", canonical)
        write_json(
            run_dir / "run_status.json",
            {
                "status": "preparing_context",
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "request_hash": request_hash,
            },
        )

        unavailable: list[dict[str, Any]] = []
        unavailable_names: set[str] = set()
        deterministic = mode == "benchmark"
        proposal_specs, requested_judge = self._route(mode, task_type)
        proposal_specs = [spec for spec in proposal_specs if spec[1] in allowed]
        system_prompt, user_prompt = proposal_prompts(canonical)
        await self._emit(event_callback, "proposing", {"requested_providers": [provider for _, provider in proposal_specs]})
        proposal_results = await self._call_many(
            proposal_specs,
            stage="proposals",
            unavailable=unavailable,
            unavailable_names=unavailable_names,
            allowed_providers=allowed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_model=Proposal,
            schema_name="council_proposal",
            deterministic=deterministic,
        )
        if not proposal_results:
            self._write_failure(
                run_dir,
                request_hash,
                "proposals",
                RuntimeError("All proposer providers are unavailable"),
                unavailable,
            )
            raise RuntimeError("All proposer providers are unavailable")

        indexed = list(proposal_results)
        if not deterministic:
            random.SystemRandom().shuffle(indexed)
        aliases: dict[str, tuple[str, str, ProviderResult]] = {
            chr(ord("A") + index): item for index, item in enumerate(indexed)
        }
        anonymous_candidates = {alias: item[2].parsed for alias, item in aliases.items()}

        critique_results: dict[str, ProviderResult] = {}
        anonymous_critiques: dict[str, dict[str, Any]] = {}
        rounds_used = 1
        if mode in {"thorough", "benchmark"} and len(aliases) >= 2:
            await self._emit(event_callback, "criticizing", {"candidate_count": len(aliases)})
            rounds_used = 2
            alias_names = list(aliases)
            critique_specs: list[tuple[str, str, str, str, str]] = []
            for index, own_alias in enumerate(alias_names):
                other_alias = alias_names[(index + 1) % len(alias_names)]
                _, provider_name, _ = aliases[own_alias]
                critique_specs.append(
                    (f"{own_alias}_critiques_{other_alias}", provider_name, own_alias, other_alias, provider_name)
                )
            for key, provider_name, own_alias, other_alias, _ in critique_specs:
                if provider_name in unavailable_names:
                    continue
                critique_system, critique_user = critique_prompts(
                    canonical,
                    own_alias,
                    anonymous_candidates[own_alias],
                    other_alias,
                    anonymous_candidates[other_alias],
                )
                completed = await self._call_one(
                    key,
                    provider_name,
                    stage="critiques",
                    unavailable=unavailable,
                    unavailable_names=unavailable_names,
                    allowed_providers=allowed,
                    system_prompt=critique_system,
                    user_prompt=critique_user,
                    schema_model=Critique,
                    schema_name="council_critique",
                    deterministic=deterministic,
                )
                if completed:
                    critique_results[key] = completed[2]
                    anonymous_critiques[key] = completed[2].parsed

        if rounds_used > 2:
            raise RuntimeError("Council round limit exceeded")
        await self._emit(event_callback, "judging", {"candidate_count": len(aliases), "critique_count": len(anonymous_critiques)})
        judge_system, judge_user = judge_prompts(canonical, anonymous_candidates, anonymous_critiques)
        proposer_provider_names = {item[1] for item in proposal_results}
        judge_preferences = self._judge_preferences(mode, requested_judge)
        judge_completed: tuple[str, str, ProviderResult] | None = None
        for judge_name in judge_preferences:
            if judge_name not in allowed or judge_name in proposer_provider_names or judge_name in unavailable_names:
                continue
            judge_completed = await self._call_one(
                "judge",
                judge_name,
                stage="judge",
                unavailable=unavailable,
                unavailable_names=unavailable_names,
                allowed_providers=allowed,
                system_prompt=judge_system,
                user_prompt=judge_user,
                schema_model=FinalDecision,
                schema_name="council_final_decision",
                deterministic=deterministic,
            )
            if judge_completed:
                break
        if judge_completed is None:
            self._write_failure(
                run_dir,
                request_hash,
                "judge",
                RuntimeError("No independent Judge provider is available"),
                unavailable,
            )
            raise RuntimeError("No independent Judge provider is available")

        _, judge_name, judge_result = judge_completed
        final_decision = judge_result.parsed
        all_results = [item[2] for item in proposal_results] + list(critique_results.values()) + [judge_result]
        total_cost = sum(result.estimated_cost_usd for result in all_results)
        selection_trace = self._selection_trace(aliases, final_decision)
        transcript = {
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "request_hash": request_hash,
            "prompt_version": PROMPT_VERSION,
            "mode": mode,
            "task_type": task_type,
            "round_limit": 2,
            "rounds_used": rounds_used,
            "routing": {
                "requested_proposers": [provider for _, provider in proposal_specs],
                "successful_proposers": [provider for _, provider, _ in proposal_results],
                "requested_judge": requested_judge,
                "judge": judge_name,
                "judge_fallback_used": judge_name != requested_judge,
                "judge_was_not_proposer": judge_name not in proposer_provider_names,
                "automatic_api_fallback": False,
            },
            "pre_anonymization": {
                call_id: result.audit_dict() for call_id, _, result in proposal_results
            },
            "post_anonymization": {
                alias: {"candidate": result.parsed, "source_provider_redacted": True}
                for alias, (_, _, result) in aliases.items()
            },
            "criticism": {key: result.audit_dict() for key, result in critique_results.items()},
            "judge": judge_result.audit_dict(),
            "provider_unavailable": unavailable,
            "selection_trace": selection_trace,
            "errors_and_retries": [
                {
                    "provider": result.provider,
                    "model": result.model,
                    "attempts": [asdict(attempt) for attempt in result.attempts],
                }
                for result in all_results
            ] + unavailable,
        }
        cost_report = {
            "currency": "USD",
            "estimation": False,
            "billing_policy": "subscription_or_local_only; no automatic pay-as-you-go fallback",
            "request_hash": request_hash,
            "calls": [
                {
                    "provider": result.provider,
                    "model": result.model,
                    "billing_mode": result.billing_mode,
                    "usage": result.usage,
                    "usage_available": result.usage_available,
                    "latency_ms": result.latency_ms,
                    "estimated_cost_usd": round(result.estimated_cost_usd, 9),
                }
                for result in all_results
            ],
            "provider_unavailable": unavailable,
            "total_tokens": {
                key: sum(result.usage.get(key, 0) for result in all_results)
                for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens")
            },
            "total_estimated_cost_usd": round(total_cost, 9),
        }
        disagreements = {
            "request_hash": request_hash,
            "judge_disagreements": final_decision["disagreements"],
            "judge_rejected_options": final_decision["rejected_options"],
            "critic_errors": {key: result.parsed["errors"] for key, result in critique_results.items()},
            "critic_conflicts": {key: result.parsed["conflicts"] for key, result in critique_results.items()},
            "unresolved": list(dict.fromkeys(final_decision["disagreements"] + final_decision["risks"])),
        }
        candidate_record = {
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "confirmed_founder_decision": False,
            "run_id": run_name,
            "request_hash": request_hash,
            "final_decision": final_decision,
            "automatic_promotion_supported": False,
        }
        write_json(run_dir / "final_decision.json", final_decision)
        write_json(run_dir / "full_transcript.json", transcript)
        write_json(run_dir / "cost_report.json", cost_report)
        write_json(run_dir / "disagreements.json", disagreements)
        write_json(run_dir / "candidate_record.json", candidate_record)
        write_json(run_dir / "provider_status.json", {"provider_unavailable": unavailable})
        final_status = "degraded" if unavailable else "completed"
        write_json(
            run_dir / "run_status.json",
            {
                "status": final_status,
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "request_hash": request_hash,
                "degraded": bool(unavailable),
            },
        )
        await self._emit(event_callback, final_status, {"provider_unavailable_count": len(unavailable)})
        return CouncilRunResult(run_name, run_dir, request_hash, final_decision, total_cost, final_status)

    def _route(self, mode: str, task_type: str) -> tuple[list[tuple[str, str]], str]:
        if mode == "local":
            return (
                [(f"deepseek_{index + 1}", "deepseek") for index in range(self.settings.local_repetitions)],
                "codex",
            )
        if mode == "fast":
            return [("claude", "claude"), ("deepseek", "deepseek")], "codex"
        proposer_a, proposer_b, judge = ROLES[task_type]
        return [(proposer_a, proposer_a), (proposer_b, proposer_b)], judge

    @staticmethod
    def _judge_preferences(mode: str, requested: str) -> list[str]:
        if mode == "local":
            return ["codex", "claude"]
        return list(dict.fromkeys((requested, "sakana", "codex", "claude", "deepseek")))

    async def _call_many(
        self,
        specs: Iterable[tuple[str, str]],
        *,
        stage: str,
        unavailable: list[dict[str, Any]],
        unavailable_names: set[str],
        allowed_providers: frozenset[str],
        **kwargs,
    ) -> list[tuple[str, str, ProviderResult]]:
        calls = [
            self._call_one(
                call_id,
                provider_name,
                stage=stage,
                unavailable=unavailable,
                unavailable_names=unavailable_names,
                allowed_providers=allowed_providers,
                **kwargs,
            )
            for call_id, provider_name in specs
        ]
        return [item for item in await asyncio.gather(*calls) if item is not None]

    async def _call_one(
        self,
        call_id: str,
        provider_name: str,
        *,
        stage: str,
        unavailable: list[dict[str, Any]],
        unavailable_names: set[str],
        allowed_providers: frozenset[str],
        **kwargs,
    ) -> tuple[str, str, ProviderResult] | None:
        provider = self.providers.get(provider_name)
        if provider_name not in allowed_providers:
            exc = ProviderUnavailable(
                f"Provider is not allowed for this run: {provider_name}",
                provider=provider_name,
                model=getattr(provider, "config", None).model if getattr(provider, "config", None) else "unknown",
                reason="not_allowed",
            )
        elif provider is None:
            exc = ProviderUnavailable(
                f"Provider is not configured: {provider_name}",
                provider=provider_name,
                model="unknown",
                reason="not_configured",
            )
        else:
            try:
                result = await provider.generate_json(**kwargs)
                return call_id, provider_name, result
            except ProviderUnavailable as caught:
                exc = caught
            except Exception as caught:
                exc = ProviderUnavailable(
                    f"Unexpected provider failure: {type(caught).__name__}: {str(caught)[:300]}",
                    provider=provider_name,
                    model=getattr(provider, "config", None).model if getattr(provider, "config", None) else "unknown",
                    reason="provider_error",
                )
        record = exc.audit_dict(stage)
        record["call_id"] = call_id
        unavailable.append(record)
        unavailable_names.add(provider_name)
        return None

    @staticmethod
    async def _emit(
        callback: RunEventCallback | None, status: str, details: dict[str, Any]
    ) -> None:
        if callback is not None:
            await callback(status, details)

    @staticmethod
    def _write_failure(
        run_dir: Path,
        request_hash: str,
        stage: str,
        exc: Exception,
        unavailable: list[dict[str, Any]],
    ) -> None:
        failure = {
            "status": "failed",
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "request_hash": request_hash,
            "stage": stage,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "provider_unavailable": unavailable,
            "automatic_api_fallback": False,
        }
        write_json(run_dir / "provider_status.json", {"provider_unavailable": unavailable})
        write_json(run_dir / "run_error.json", failure)
        write_json(run_dir / "run_status.json", failure)

    @staticmethod
    def _selection_trace(
        aliases: dict[str, tuple[str, str, ProviderResult]], final: dict[str, Any]
    ) -> dict[str, Any]:
        final_text = json.dumps(final, ensure_ascii=False).casefold()
        traces = {}
        for alias, (_, provider_name, result) in aliases.items():
            adopted = []
            not_adopted = []
            for recommendation in result.parsed.get("recommendations", []):
                normalized = recommendation.casefold()
                similarity = SequenceMatcher(None, normalized, final_text).ratio()
                entry = {
                    "recommendation": recommendation,
                    "reason": (
                        "Judge output contains closely matching language."
                        if normalized in final_text or similarity >= 0.35
                        else "No close lexical match in the Judge output; inspect disagreements and rejected_options."
                    ),
                }
                (adopted if normalized in final_text or similarity >= 0.35 else not_adopted).append(entry)
            traces[alias] = {
                "source_provider": provider_name,
                "method": "deterministic lexical audit, not a second model judgment",
                "adopted": adopted,
                "not_adopted": not_adopted,
            }
        return traces
