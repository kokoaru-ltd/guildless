from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from council.config import ProviderConfig, Settings
from council.orchestrator import CouncilOrchestrator
from council.providers.base import AttemptLog, ProviderResult, ProviderUnavailable
from council.schemas import Critique, FinalDecision, Proposal


@dataclass
class FakeProvider:
    config: ProviderConfig
    calls: list[str] = field(default_factory=list)

    async def aclose(self):
        return None

    async def generate_json(self, *, schema_model, **kwargs):
        self.calls.append(schema_model.__name__)
        if schema_model is Proposal:
            parsed = {
                "position": f"{self.config.name}の提案",
                "assumptions": ["段階導入できる"],
                "recommendations": ["影モードで再分類し差分を監査する"],
                "risks": ["分類誤り"],
                "rejected_options": ["全件手作業"],
                "needs_external_fact": [],
                "confidence": 0.8,
            }
        elif schema_model is Critique:
            parsed = {
                "supported_points": ["影モード"],
                "errors": [],
                "missing_considerations": ["ロールバック基準"],
                "conflicts": [],
                "revised_recommendation": "影モードと差分監査を行う",
            }
        elif schema_model is FinalDecision:
            parsed = {
                "decision": "影モードで再分類し、差分監査後にreference候補だけ提示する",
                "consensus": ["元データを変更しない", "差分ログを保存する"],
                "disagreements": ["サンプル率は実測で調整する"],
                "rejected_options": ["全件手作業: 工数が大きい"],
                "risks": ["分類境界の偏り"],
                "evidence": ["既存namespaceは3種類に偏っている"],
                "assumptions": ["再分類は自動化できる"],
                "unknowns": ["境界事例の実数"],
                "next_action": "固定評価セットと停止基準を作成する",
                "experiment": None,
                "user_question": None,
                "confidence": 0.84,
            }
        else:
            raise AssertionError(schema_model)
        validated = schema_model.model_validate(parsed).model_dump(mode="json")
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            response_id=f"{self.config.name}-id",
            raw_text=json.dumps(validated, ensure_ascii=False),
            parsed=validated,
            usage={"input_tokens": 100, "cached_input_tokens": 0, "cache_write_tokens": 0, "output_tokens": 50},
            estimated_cost_usd=0.0,
            latency_ms=10,
            attempts=[AttemptLog(1, 200, 10, None)],
            billing_mode=self.config.billing_mode,
        )


@dataclass
class UnavailableProvider(FakeProvider):
    reason: str = "usage_limit"

    async def generate_json(self, *, schema_model, **kwargs):
        self.calls.append(schema_model.__name__)
        raise ProviderUnavailable(
            f"{self.config.name} unavailable",
            provider=self.config.name,
            model=self.config.model,
            reason=self.reason,
            stderr="subscription limit",
        )


def setup(tmp_path: Path, *, local_repetitions: int = 3):
    configs = {
        "claude": ProviderConfig("claude", "opus", billing_mode="subscription"),
        "deepseek": ProviderConfig("deepseek", "deepseek-r1:14b", billing_mode="local"),
        "codex": ProviderConfig("codex", "default", billing_mode="subscription"),
        "sakana": ProviderConfig("sakana", "fugu-ultra", "key", billing_mode="subscription"),
    }
    settings = Settings(
        configs,
        tmp_path / "runs",
        10,
        0,
        100_000,
        tmp_path / ".runtime",
        local_repetitions,
    )
    providers = {name: FakeProvider(config) for name, config in configs.items()}
    return settings, providers


@pytest.mark.asyncio
async def test_fast_is_claude_and_deepseek_with_codex_judge(tmp_path: Path):
    settings, providers = setup(tmp_path)
    result = await CouncilOrchestrator(settings, providers=providers, output_boundary=tmp_path).ask(
        mode="fast", task_type="evaluation_design", question="テスト"
    )
    transcript = json.loads((result.run_dir / "full_transcript.json").read_text(encoding="utf-8"))
    assert transcript["routing"]["requested_proposers"] == ["claude", "deepseek"]
    assert transcript["routing"]["judge"] == "codex"
    assert transcript["rounds_used"] == 1
    assert set(transcript["post_anonymization"]) == {"A", "B"}
    assert transcript["routing"]["automatic_api_fallback"] is False
    assert (result.run_dir / "final_decision.json").exists()
    assert (result.run_dir / "cost_report.json").exists()
    assert (result.run_dir / "disagreements.json").exists()


@pytest.mark.asyncio
async def test_local_runs_deepseek_multiple_times_and_one_codex_judge(tmp_path: Path):
    settings, providers = setup(tmp_path, local_repetitions=3)
    result = await CouncilOrchestrator(settings, providers=providers, output_boundary=tmp_path).ask(
        mode="local", task_type="architecture", question="ローカル検証"
    )
    transcript = json.loads((result.run_dir / "full_transcript.json").read_text(encoding="utf-8"))
    assert transcript["routing"]["requested_proposers"] == ["deepseek", "deepseek", "deepseek"]
    assert providers["deepseek"].calls.count("Proposal") == 3
    assert providers["codex"].calls.count("FinalDecision") == 1
    assert providers["claude"].calls == []


@pytest.mark.asyncio
async def test_unavailable_proposer_is_recorded_and_remaining_models_continue(tmp_path: Path):
    settings, providers = setup(tmp_path)
    providers["claude"] = UnavailableProvider(settings.providers["claude"], reason="usage_limit")
    result = await CouncilOrchestrator(settings, providers=providers, output_boundary=tmp_path).ask(
        mode="fast", task_type="architecture", question="縮退運転"
    )
    transcript = json.loads((result.run_dir / "full_transcript.json").read_text(encoding="utf-8"))
    assert transcript["routing"]["successful_proposers"] == ["deepseek"]
    assert transcript["provider_unavailable"][0]["reason"] == "usage_limit"
    assert transcript["provider_unavailable"][0]["automatic_api_fallback"] is False
    assert transcript["routing"]["judge"] == "codex"


@pytest.mark.asyncio
async def test_unavailable_codex_judge_uses_preconfigured_sakana_subscription(tmp_path: Path):
    settings, providers = setup(tmp_path)
    providers["codex"] = UnavailableProvider(settings.providers["codex"], reason="login_expired")
    result = await CouncilOrchestrator(settings, providers=providers, output_boundary=tmp_path).ask(
        mode="fast", task_type="architecture", question="Judge縮退"
    )
    transcript = json.loads((result.run_dir / "full_transcript.json").read_text(encoding="utf-8"))
    assert transcript["routing"]["judge"] == "sakana"
    assert transcript["routing"]["judge_fallback_used"] is True
    assert transcript["routing"]["automatic_api_fallback"] is False


@pytest.mark.asyncio
async def test_thorough_is_bounded_to_two_rounds(tmp_path: Path):
    settings, providers = setup(tmp_path)
    result = await CouncilOrchestrator(settings, providers=providers, output_boundary=tmp_path).ask(
        mode="thorough",
        task_type="architecture",
        question="Founder Memoryのnamespace再分類を、人間作業を最小化しつつ検証可能にする方法",
    )
    transcript = json.loads((result.run_dir / "full_transcript.json").read_text(encoding="utf-8"))
    candidate = json.loads((result.run_dir / "candidate_record.json").read_text(encoding="utf-8"))
    assert transcript["rounds_used"] == 2
    assert transcript["round_limit"] == 2
    assert transcript["routing"]["judge_was_not_proposer"] is True
    assert candidate["record_type"] == "assistant_council_candidate"
    assert candidate["promotion_status"] == "unconfirmed"
    assert candidate["confirmed_founder_decision"] is False
    FinalDecision.model_validate(result.final_decision)
