# -*- coding: utf-8 -*-
"""Guildless Zero-to-Revenue v0 engine.

A deterministic, local-first state machine that turns a founder intent into a
business plan, a campaign-level permission envelope, shadow execution, a
revenue/cost ledger and an explicit SCALE / MODIFY / KILL decision.

Design intent (v0):
- The search space is fixed so the first benchmark cannot be gamed by choice.
- Human approval is granted once per campaign (Permission Envelope), not per
  action.
- Outreach results are shadow-simulated and clearly labelled; real revenue is
  only recorded through human-entered orders (payments stay a human action).
- The loop always terminates in an explicit decision. KILL is a first-class
  outcome, not a failure of the system.

This module is intentionally self-contained (standard library only) so it can
be unit-tested without providers, network access or the rest of the council
package.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Fixed v0 search space (first product conditions are system-side, not chosen
# by a human or by the model).
# ---------------------------------------------------------------------------

V0_CONSTRAINTS: list[dict[str, str]] = [
    {"id": "digital_delivery", "name": "デジタル納品", "detail": "物の配送を伴わない成果物を納品する"},
    {"id": "no_inventory", "name": "在庫なし", "detail": "仕入れ・在庫リスクを持たない"},
    {"id": "budget_cap", "name": "初期費用3万円以下", "detail": "営業費・道具代を含む初期投資を3万円以内に収める"},
    {"id": "no_license", "name": "免許不要", "detail": "宅建・古物商など許認可を必要としない"},
    {"id": "b2b", "name": "BtoB", "detail": "企業を相手にした販売である"},
    {"id": "price_band", "name": "3,000〜10,000円", "detail": "決済リンクで即購入できる価格帯"},
    {"id": "instant_checkout", "name": "決済リンクで即購入", "detail": "見積・請求の長期化を避け、即決済できる"},
    {"id": "fast_delivery", "name": "24〜48時間以内に納品", "detail": "受注から納品まで2日以内"},
    {"id": "no_professional_license", "name": "専門資格が不要", "detail": "人間の専門資格を前提としない"},
]

# Candidate product catalog. ``keywords`` are loose intent hints; the engine
# falls back to a deterministic default set when nothing matches.
CANDIDATE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "website_fix_report",
        "name": "ホームページ改善診断レポート",
        "price_yen": 5000,
        "delivery_hours": 24,
        "summary": "自社サイトの改善点を箇条書きで整理したPDFを納品",
        "channels": ["email"],
        "keywords": ["web", "サイト", "ホームページ", "lp", "ランディング", "seo"],
    },
    {
        "id": "gbp_improvement",
        "name": "Googleビジネスプロフィール改善",
        "price_yen": 5000,
        "delivery_hours": 30,
        "summary": "地図検索での見つかりやすさを高める改善案を納品",
        "channels": ["email", "phone"],
        "keywords": ["google", "マップ", "地図", "集客", "ローカル"],
    },
    {
        "id": "prospect_list",
        "name": "営業リスト作成",
        "price_yen": 8000,
        "delivery_hours": 48,
        "summary": "対象エリア・業種から見込み企業を洗い出したCSVを納品",
        "channels": ["email"],
        "keywords": ["リスト", "営業", "見込み", "顧客", "企業", "卸", "仕入"],
    },
    {
        "id": "competitor_report",
        "name": "競合調査レポート",
        "price_yen": 8000,
        "delivery_hours": 48,
        "summary": "競合の価格・訴求・弱点を整理した調査レポートを納品",
        "channels": ["email"],
        "keywords": ["競合", "調査", "市場", "マーケット", "リサーチ"],
    },
    {
        "id": "recruiting_page_plan",
        "name": "採用ページ改善案",
        "price_yen": 5000,
        "delivery_hours": 36,
        "summary": "求職者視点で採用ページの改善案を整理して納品",
        "channels": ["email", "dm"],
        "keywords": ["採用", "求人", "人材", "中途"],
    },
    {
        "id": "sns_content_plan",
        "name": "SNS投稿プラン",
        "price_yen": 3000,
        "delivery_hours": 24,
        "summary": "1ヶ月分の投稿テーマと文案をまとめた表を納品",
        "channels": ["dm"],
        "keywords": ["sns", "投稿", "コンテンツ", "宣伝", "フォロワー"],
    },
    {
        "id": "seo_diagnosis",
        "name": "SEO診断レポート",
        "price_yen": 5000,
        "delivery_hours": 24,
        "summary": "検索流入の現状を診断し、優先改善項目を整理したレポートを納品",
        "channels": ["email"],
        "keywords": ["seo", "検索", "流入", "集客", "対策"],
    },
    {
        "id": "lp_improvement",
        "name": "ランディングページ改善案",
        "price_yen": 5000,
        "delivery_hours": 36,
        "summary": "コンバージョンを上げるLP構成・文言・導線の改善案を納品",
        "channels": ["email", "dm"],
        "keywords": ["lp", "ランディング", "コンバージョン", "広告"],
    },
    {
        "id": "direct_mail_plan",
        "name": "DM営業セット作成",
        "price_yen": 8000,
        "delivery_hours": 48,
        "summary": "郵送DMの宛先リストと送付状・チラシ原稿を一式作成して納品",
        "channels": ["dm"],
        "keywords": ["dm", "ダイレクトメール", "郵送", "チラシ"],
    },
]

# Deterministic shadow response model per channel:
# (response_rate, purchase_rate_of_responders). Only used for labelled
# simulation until a human enters a real order.
CHANNEL_MODEL: dict[str, tuple[float, float]] = {
    "email": (0.020, 0.10),
    "phone": (0.035, 0.12),
    "dm": (0.040, 0.08),
}

# Built-in capability catalog resolved by Capability Resolver.
CAPABILITY_CATALOG: list[dict[str, str]] = [
    {"id": "find_b2b_prospects", "name": "企業・担当者調査", "owner": "auto", "note": "公開情報から見込み企業を抽出する"},
    {"id": "generate_offer", "name": "提案文作成", "owner": "auto", "note": "商品ごとの提案文と見積を生成する"},
    {"id": "contact_prospect", "name": "接触（メール・電話）", "owner": "envelope", "note": "承認されたCampaignの範囲内でのみ実行"},
    {"id": "follow_up", "name": "再接触", "owner": "envelope", "note": "承認された回数まで自動再接触"},
    {"id": "collect_payment", "name": "決済リンク作成", "owner": "human", "note": "決済の実行は人間が行う"},
    {"id": "deliver_digital", "name": "デジタル納品物作成", "owner": "auto", "note": "受注後の成果物ファイルを生成する"},
]

STAGE_LABELS: dict[str, str] = {
    "goal": "目標化",
    "plan": "事業案",
    "constraint": "制約確認",
    "experiment": "実験設計",
    "envelope": "実行許可",
    "capability": "能力確保",
    "execute": "実行",
    "observe": "観測",
    "decide": "判定",
    "killed": "停止",
}

STAGE_ORDER: list[str] = [
    "goal", "plan", "constraint", "experiment", "envelope",
    "capability", "execute", "observe", "decide", "killed",
]

TERMINAL_DECISIONS = {"SCALE", "MODIFY", "KILL"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _stable_seed(loop_id: str) -> int:
    return int(hashlib.sha256(loop_id.encode("utf-8")).hexdigest()[:12], 16)


def _binomial(rng: random.Random, trials: int, probability: float) -> int:
    """Deterministic binomial sample using only the stdlib RNG."""
    if trials <= 0:
        return 0
    return sum(1 for _ in range(trials) if rng.random() < probability)


def _clean_intent(intent: str) -> str:
    return re.sub(r"\s+", " ", intent.strip())


def _match_candidates(intent: str) -> list[dict[str, Any]]:
    lowered = intent.casefold()
    hits: list[dict[str, Any]] = []
    for candidate in CANDIDATE_CATALOG:
        if any(keyword in lowered for keyword in candidate["keywords"]):
            hits.append(candidate)
    # Always present enough candidates to make the selection meaningful:
    # intent-matched candidates come first, then deterministic fillers.
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in hits + CANDIDATE_CATALOG:
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        chosen.append(candidate)
        if len(chosen) >= 6:
            break
    return chosen


# ---------------------------------------------------------------------------
# Public value objects (plain dicts keep the module dependency-free).
# ---------------------------------------------------------------------------


@dataclass
class V0Loop:
    loop_id: str
    state: dict[str, Any] = field(default_factory=dict)


class V0EngineError(ValueError):
    """Raised for invalid transitions or malformed state."""


class V0LoopManager:
    """Persists one active Zero-to-Revenue loop under ``output_root/v0``."""

    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)
        self.v0_dir = self.output_root / "v0"
        self.v0_dir.mkdir(parents=True, exist_ok=True)

    # -- persistence -------------------------------------------------------

    def _state_path(self, loop_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", loop_id):
            raise V0EngineError(f"invalid loop id: {loop_id!r}")
        return self.v0_dir / f"{loop_id}.json"

    def save(self, state: dict[str, Any]) -> None:
        path = self._state_path(state["loop_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def load(self, loop_id: str) -> dict[str, Any]:
        try:
            return json.loads(self._state_path(loop_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise V0EngineError(f"loop not found: {loop_id}") from exc

    def latest_id(self) -> str | None:
        candidates = [path.stem for path in self.v0_dir.glob("*.json")]
        if not candidates:
            return None
        # loop ids start with v0_YYYYMMDDTHHMMSS_... so lexicographic max is
        # the most recently created loop.
        return max(candidates)

    def latest(self) -> dict[str, Any] | None:
        loop_id = self.latest_id()
        return self.load(loop_id) if loop_id else None

    # -- lifecycle ---------------------------------------------------------

    def start(self, intent: str, budget_yen: int = 30_000, deadline_days: int = 14) -> dict[str, Any]:
        cleaned = _clean_intent(intent)
        if not cleaned:
            raise V0EngineError("事業の目的を入力してください")
        if not 1000 <= budget_yen <= 100_000:
            raise V0EngineError("予算は1,000円以上100,000円以下にしてください")
        if not 1 <= deadline_days <= 90:
            raise V0EngineError("期間は1日以上90日以下にしてください")

        loop_id = f"v0_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
        state: dict[str, Any] = {
            "loop_id": loop_id,
            "intent": cleaned,
            "budget_yen": budget_yen,
            "deadline_days": deadline_days,
            "created_at": _now(),
            "stage": "goal",
            "furthest_stage": "goal",
            "status": "running",
            "mode": "shadow",
            "cycles": 1,
            "goal": None,
            "candidates": [],
            "selected_business": None,
            "constraint_checks": [],
            "experiments": [],
            "envelope": None,
            "capabilities": [],
            "execution": None,
            "ledger": {"cost_yen": 0, "revenue_yen": 0, "orders": [], "entries": []},
            "decision": None,
            "cycle_history": [],
            "checkins": [],
        }
        self.save(state)
        # Generate the goal and the business candidate list, then stop at the
        # plan stage so the founder can choose from the candidates. The engine
        # does not silently pick a business for the founder.
        state = self.advance(loop_id)  # goal -> plan (goal compiled)
        state = self.advance(loop_id)  # plan -> plan (candidates generated)
        state["status"] = "awaiting_selection"
        state["furthest_stage"] = state["stage"]
        self.save(state)
        return state

    def advance(self, loop_id: str) -> dict[str, Any]:
        """Run the next stage. Idempotent at awaiting_approval / terminal.

        Review navigation: when a later stage was already computed, moving
        forward again fast-forwards one stage at a time through the existing
        data instead of re-running stage builders, so costs are never
        double-counted.
        """
        state = self.load(loop_id)
        stage = state["stage"]
        if stage == "killed":
            return state
        if stage == "decide":
            if state.get("status") != "KILL":
                state["decision"] = self._decide(state)
                state["status"] = state["decision"]["verdict"]
                self.save(state)
            return state
        if stage == "envelope" and not state.get("envelope", {}).get("approved_at"):
            return state

        try:
            current_index = STAGE_ORDER.index(stage)
        except ValueError:
            raise V0EngineError("unexpected stage in loop state") from None

        next_stage = STAGE_ORDER[current_index + 1]
        furthest = self._effective_furthest(state)
        if (
            furthest
            and STAGE_ORDER.index(next_stage) <= STAGE_ORDER.index(furthest)
            and self._stage_has_data(state, next_stage)
        ):
            state["stage"] = next_stage
            self.save(state)
            return state

        if stage == "goal":
            state["goal"] = self._compile_goal(state)
            state["stage"] = "plan"
        elif stage == "plan":
            candidates = _match_candidates(state["intent"])
            state["candidates"] = candidates
            if state.get("selected_business") is None:
                # Await the founder's choice. advance() before a selection
                # refreshes the candidate list without moving on.
                state["status"] = "awaiting_selection"
                self.save(state)
                return state
            state["stage"] = "constraint"
        elif stage == "constraint":
            state["constraint_checks"] = self._check_constraints(state["selected_business"])
            state["stage"] = "experiment"
        elif stage == "experiment":
            state["experiments"] = self._plan_experiments(state)
            state["stage"] = "envelope"
            state["envelope"] = self._build_envelope(state)
            state["status"] = "awaiting_approval"
        elif stage == "envelope":
            # Approved envelope resumes into capability after a review visit.
            state["status"] = "approved"
            state["stage"] = "capability"
        elif stage == "capability":
            state["capabilities"] = self._resolve_capabilities(state)
            state["stage"] = "execute"
        elif stage == "execute":
            state["execution"] = self._execute_shadow(state)
            state["stage"] = "observe"
        elif stage == "observe":
            self._observe(state)
            state["stage"] = "decide"
        else:
            raise V0EngineError(f"unexpected stage: {stage}")

        state["furthest_stage"] = state["stage"]
        self.save(state)
        return state

    def approve(self, loop_id: str) -> dict[str, Any]:
        """Human approves the Permission Envelope once, then shadow execution runs."""
        state = self.load(loop_id)
        if state["stage"] != "envelope":
            raise V0EngineError("実行許可の段階ではありません")
        if not state.get("envelope"):
            raise V0EngineError("実行許可が未作成です")
        envelope = dict(state["envelope"])
        envelope["approved_at"] = _now()
        envelope["approved_by"] = "human"
        state["envelope"] = envelope
        state["status"] = "approved"
        state["stage"] = "capability"
        self.save(state)
        state = self.advance(loop_id)  # capability
        state = self.advance(loop_id)  # execute
        state = self.advance(loop_id)  # observe
        return self.advance(loop_id)  # decide

    def record_order(self, loop_id: str, company: str, amount_yen: int) -> dict[str, Any]:
        """Human-entered real order. Payments and delivery stay human actions."""
        state = self.load(loop_id)
        company = company.strip()
        if not company:
            raise V0EngineError("注文企業名を入力してください")
        if not 100 <= amount_yen <= 10_000_000:
            raise V0EngineError("金額が不正です")

        selected = state.get("selected_business") or {}
        expected = int(selected.get("price_yen", 0))
        if expected and amount_yen != expected:
            raise V0EngineError(f"この商品の価格は{expected:,}円です")

        order = {
            "order_id": uuid.uuid4().hex[:12],
            "company": company,
            "amount_yen": amount_yen,
            "recorded_at": _now(),
            "recorded_by": "human",
            "source": "human_entered",
            "delivered": False,
        }
        state["ledger"]["orders"].append(order)
        state["ledger"]["revenue_yen"] = sum(item["amount_yen"] for item in state["ledger"]["orders"])
        state["ledger"]["entries"].append(
            {
                "kind": "revenue",
                "amount_yen": amount_yen,
                "label": f"{company} 注文",
                "at": _now(),
            }
        )
        self.save(state)
        return state

    def select(self, loop_id: str, candidate_id: str) -> dict[str, Any]:
        """Founder chooses one business candidate from the generated list.

        Selecting invalidates everything downstream of the plan stage and
        rebuilds constraint checks, experiments and the permission envelope
        for the chosen business. Already-approved campaigns and recorded
        orders cannot be overwritten.
        """
        state = self.load(loop_id)
        if state["stage"] not in ("plan", "constraint", "experiment", "envelope"):
            raise V0EngineError("この段階では事業を選び直せません")
        if (state.get("envelope") or {}).get("approved_at"):
            raise V0EngineError("承認済みCampaignがあるため事業を変更できません")
        if state.get("ledger", {}).get("orders"):
            raise V0EngineError("実入金が記録されているため事業を変更できません")
        candidates = state.get("candidates") or []
        selected = next((item for item in candidates if item["id"] == candidate_id), None)
        if selected is None:
            raise V0EngineError("候補が見つかりません")
        state["selected_business"] = selected
        # Choosing a different business invalidates everything downstream.
        state["constraint_checks"] = []
        state["experiments"] = []
        state["envelope"] = None
        state["capabilities"] = []
        state["execution"] = None
        state["decision"] = None
        state["ledger"] = {"cost_yen": 0, "revenue_yen": 0, "orders": [], "entries": []}
        state["stage"] = "constraint"
        state["furthest_stage"] = "constraint"
        state["status"] = "running"
        self.save(state)
        # Rebuild the plan downstream up to the approval gate.
        state = self.advance(loop_id)  # constraint
        state = self.advance(loop_id)  # experiment
        return self.advance(loop_id)  # envelope (awaiting_approval)

    def daily_confirm(self, loop_id: str, note: str = "") -> dict[str, Any]:
        """Founder stamps that today's contents were reviewed (daily check-in).

        The stamp is an audit trail on top of the loop state: it records the
        stage that was on screen and an optional note, so "who checked what
        when" stays visible even after the loop advances.
        """
        state = self.load(loop_id)
        checkins = state.get("checkins") or []
        checkins.append(
            {
                "id": f"chk_{uuid.uuid4().hex[:8]}",
                "confirmed_at": _now(),
                "stage": state["stage"],
                "note": (note or "").strip()[:300],
                "by": "human",
            }
        )
        state["checkins"] = checkins
        self.save(state)
        return state

    def deliver(self, loop_id: str, order_id: str) -> dict[str, Any]:
        """Mark a paid order as delivered by creating a digital deliverable file."""
        state = self.load(loop_id)
        order = next((item for item in state["ledger"]["orders"] if item["order_id"] == order_id), None)
        if order is None:
            raise V0EngineError("注文が見つかりません")
        if order["delivered"]:
            return state
        # Create an actual deliverable artifact under the loop's run directory.
        run_dir = self.v0_dir / loop_id / "deliverables"
        run_dir.mkdir(parents=True, exist_ok=True)
        selected = state.get("selected_business") or {}
        name = selected.get("name", "成果物")
        content = (
            f"Guildless v0 納品物\n"
            f"------------------\n"
            f"注文: {order['company']}\n"
            f"商品: {name}\n"
            f"注文ID: {order_id}\n"
            f"納品日時: {_now()}\n"
        )
        deliverable = run_dir / f"{order_id}.txt"
        deliverable.write_text(content, encoding="utf-8")
        order["delivered"] = True
        order["delivered_at"] = _now()
        order["deliverable"] = str(deliverable)
        state["ledger"]["entries"].append(
            {"kind": "delivery", "amount_yen": 0, "label": f"{order['company']} 納品完了", "at": _now()}
        )
        self.save(state)
        return state

    def decide(self, loop_id: str) -> dict[str, Any]:
        state = self.load(loop_id)
        if state["stage"] not in ("decide", "observe"):
            raise V0EngineError("判定できる段階ではありません")
        state["decision"] = self._decide(state)
        state["status"] = state["decision"]["verdict"]
        self.save(state)
        return state

    def kill(self, loop_id: str, reason: str = "") -> dict[str, Any]:
        """Human can always stop a business, even after a SCALE/MODIFY verdict."""
        state = self.load(loop_id)
        if state["status"] == "KILL":
            return state
        state["decision"] = {
            "verdict": "KILL",
            "summary": reason.strip() or "条件を満たさないため事業を停止します",
            "decided_at": _now(),
            "spend_yen": state["ledger"]["cost_yen"],
            "revenue_yen": state["ledger"]["revenue_yen"],
        }
        state["stage"] = "killed"
        state["status"] = "KILL"
        self.save(state)
        return state

    # -- review navigation & part adoption --------------------------------

    def goto(self, loop_id: str, stage: str) -> dict[str, Any]:
        """Move to any stage the loop has already reached so the founder can review it.

        Backward jumps review existing data. Forward jumps are allowed only
        up to the furthest stage actually reached, so the approval gate and
        execution cannot be skipped. After a terminal KILL every stage stays
        reviewable.
        """
        state = self.load(loop_id)
        if stage not in STAGE_ORDER:
            raise V0EngineError(f"不明なステージです: {stage}")
        furthest = self._effective_furthest(state)
        if state["stage"] != "killed" and STAGE_ORDER.index(stage) > STAGE_ORDER.index(furthest):
            raise V0EngineError("まだ到達していないステージには移動できません")
        state["stage"] = stage
        state["status"] = self._status_for_stage(state, stage)
        self.save(state)
        return state

    def add_capability(self, loop_id: str, name: str, source: str = "") -> dict[str, Any]:
        """Adopt a part from the capability library into the loop.

        Idempotent by name: adopting the same part twice does not duplicate it.
        """
        state = self.load(loop_id)
        name = name.strip()
        if not name:
            raise V0EngineError("部品名を入力してください")
        if len(name) > 200:
            raise V0EngineError("部品名が長すぎます")
        capabilities = state.get("capabilities") or []
        if any(item.get("name") == name for item in capabilities):
            return state
        capabilities.append(
            {
                "id": f"part_{uuid.uuid4().hex[:10]}",
                "name": name,
                "note": (source or "").strip()[:240] or "部品ライブラリから採用",
                "source": (source or "").strip()[:240],
                "status": "準備可",
                "added_at": _now(),
                "added_by": "human",
            }
        )
        state["capabilities"] = capabilities
        self.save(state)
        return state

    @staticmethod
    def _status_for_stage(state: dict[str, Any], stage: str) -> str:
        if stage == "killed":
            return "KILL"
        if stage == "envelope":
            envelope = state.get("envelope") or {}
            return "approved" if envelope.get("approved_at") else "awaiting_approval"
        if stage == "decide":
            decision = state.get("decision")
            return decision["verdict"] if decision else "running"
        if state.get("status") == "KILL":
            return "KILL"
        return "running"

    @staticmethod
    def _stage_has_data(state: dict[str, Any], stage: str) -> bool:
        if stage == "goal":
            return state.get("goal") is not None
        if stage == "plan":
            return bool(state.get("candidates"))
        if stage == "constraint":
            return bool(state.get("constraint_checks"))
        if stage == "experiment":
            return bool(state.get("experiments"))
        if stage == "envelope":
            return state.get("envelope") is not None
        if stage == "capability":
            return bool(state.get("capabilities"))
        if stage in ("execute", "observe"):
            return state.get("execution") is not None
        if stage == "decide":
            return state.get("decision") is not None
        if stage == "killed":
            return state.get("status") == "KILL"
        return False

    @staticmethod
    def _effective_furthest(state: dict[str, Any]) -> str:
        """Furthest stage, falling back to data for legacy loops.

        Loops saved before ``furthest_stage`` existed may lack the field.
        Deriving it from the data that is present keeps review navigation
        from re-running stage builders and double-counting campaign costs.
        """
        if state.get("status") == "KILL":
            return "killed"
        furthest = state.get("furthest_stage")
        if furthest and furthest in STAGE_ORDER:
            return furthest
        if state.get("decision") is not None:
            return "decide"
        if state.get("execution") is not None:
            return "observe"
        if state.get("envelope", {}).get("approved_at"):
            return "capability"
        if state.get("envelope") is not None:
            return "envelope"
        if state.get("experiments"):
            return "experiment"
        if state.get("constraint_checks"):
            return "constraint"
        if state.get("candidates"):
            return "plan"
        if state.get("goal") is not None:
            return "goal"
        return "goal"

    # -- stage builders ----------------------------------------------------

    @staticmethod
    def _compile_goal(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "final_goal": "利益を出す",
            "intermediate_goal": "第三者から初回売上を発生させる",
            "budget_yen": state["budget_yen"],
            "deadline_days": state["deadline_days"],
            "intent": state["intent"],
            "human_involvement": "承認のみ",
        }

    @staticmethod
    def _check_constraints(selected: dict[str, Any]) -> list[dict[str, str]]:
        results = []
        for rule in V0_CONSTRAINTS:
            results.append(
                {
                    "id": rule["id"],
                    "name": rule["name"],
                    "detail": rule["detail"],
                    "pass": True,
                    "note": "この挑戦では変更しない条件",
                }
            )
        return results

    @staticmethod
    def _plan_experiments(state: dict[str, Any]) -> list[dict[str, Any]]:
        selected = state["selected_business"]
        channels = selected.get("channels") or ["email"]
        seed = _stable_seed(state["intent"])
        rng = random.Random(seed)
        budget = state["budget_yen"]
        experiments = [
            {
                "id": "exp_a",
                "label": "仮説A: 対象を広く浅く接触",
                "channel": channels[0],
                "tactic": "リスト営業（メール・架電）",
                "tactic_detail": "業界・規模で絞った見込み企業リストを用意し、承認済みCampaign内で一括接触する",
                "rationale": "まず市場の反応の幅を測り、反応率が高いセグメントを特定する",
                "target_count": 80,
                "budget_yen": int(budget * 0.4),
                "status": "planned",
            },
            {
                "id": "exp_b",
                "label": "仮説B: 対象を絞って深く接触",
                "channel": channels[-1],
                "tactic": "絞り込みDM・個別提案",
                "tactic_detail": "サイト・地図情報から顕在ニーズがありそうな30社に絞り、個別に合わせた提案文を送る",
                "rationale": "広く浅くより、反応しやすい相手への密な接触で成約率を試す",
                "target_count": 30,
                "budget_yen": int(budget * 0.35),
                "status": "planned",
            },
            {
                "id": "exp_c",
                "label": "仮説C: 高単価化して少数に提案",
                "channel": channels[0],
                "tactic": "高単価パッケージ提案",
                "tactic_detail": "商品をセット化して単価を引き上げ、競合との差別化点を明確にして少数社へ提案する",
                "rationale": "単価を上げれば少ない件数でも黒字に近づくかを試す",
                "target_count": 20,
                "budget_yen": int(budget * 0.25),
                "status": "planned",
            },
        ]
        # Slight deterministic jitter so repeated runs differ only by intent.
        for exp in experiments:
            exp["target_count"] = max(5, int(exp["target_count"] * (0.9 + 0.2 * rng.random())))
        return experiments

    def _build_envelope(self, state: dict[str, Any]) -> dict[str, Any]:
        selected = state["selected_business"] or {}
        channels = list(dict.fromkeys(selected.get("channels") or ["email"]))
        total_targets = sum(int(exp["target_count"]) for exp in state["experiments"])
        return {
            "channel": channels,
            "target_count_cap": total_targets,
            "budget_cap_yen": state["budget_yen"],
            "period_hours": state["deadline_days"] * 24,
            "follow_up_max": 1,
            "prohibited": ["契約締結", "値引き", "支払い", "虚偽表示"],
            "status": "pending",
            "summary": (
                f"{selected.get('name', '事業')}を{total_targets}社へ"
                f"（{ '・'.join(channels) }）で接触します。"
                f"予算上限{state['budget_yen']:,}円・期間{state['deadline_days']}日・再接触最大1回。"
            ),
        }

    def _resolve_capabilities(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        existing = {item.get("id"): item for item in (state.get("capabilities") or [])}
        for capability in CAPABILITY_CATALOG:
            owner = capability["owner"]
            if owner == "envelope":
                approved = bool(state.get("envelope", {}).get("approved_at"))
                status = "承認済み" if approved else "要承認"
            elif owner == "human":
                status = "人間操作"
            else:
                status = "準備可"
            existing[capability["id"]] = {
                "id": capability["id"],
                "name": capability["name"],
                "note": capability["note"],
                "status": status,
            }
        return list(existing.values())

    def _execute_shadow(self, state: dict[str, Any]) -> dict[str, Any]:
        """Deterministic, clearly-labelled shadow simulation of a campaign.

        No external action happens. The numbers are produced by a seeded model
        so the loop can be exercised end-to-end until a human enters a real
        order. Funnel stages (contact -> reply -> interest -> purchase) and a
        per-tactic cost breakdown are shown so the marketing side is not
        treated as a single opaque number.
        """
        seed = _stable_seed(state["intent"]) + state["cycles"] * 7919
        rng = random.Random(seed)
        price = int(state["selected_business"].get("price_yen", 5000))
        results = []
        total_contacts = 0
        total_replied = 0
        total_interested = 0
        total_purchases = 0
        total_cost = 0
        total_revenue = 0
        total_breakdown: dict[str, int] = {}

        for exp in state["experiments"]:
            channel = exp["channel"]
            response_rate, purchase_rate = CHANNEL_MODEL.get(channel, CHANNEL_MODEL["email"])
            contacts = int(exp["target_count"])
            replied = _binomial(rng, contacts, response_rate)
            interested = _binomial(rng, replied, 0.5)
            purchases = _binomial(rng, interested, min(1.0, purchase_rate * 2))
            cost = int(contacts * 12 * (0.8 + 0.4 * rng.random()))
            tool_cost = max(1, int(cost * 0.35))
            labour_cost = max(0, cost - tool_cost)
            revenue = purchases * price
            total_contacts += contacts
            total_replied += replied
            total_interested += interested
            total_purchases += purchases
            total_cost += cost
            total_revenue += revenue
            total_breakdown["ツール・リスト費"] = total_breakdown.get("ツール・リスト費", 0) + tool_cost
            total_breakdown["作業・架電費"] = total_breakdown.get("作業・架電費", 0) + labour_cost
            results.append(
                {
                    "experiment_id": exp["id"],
                    "label": exp.get("label", exp["id"]),
                    "channel": channel,
                    "tactic": exp.get("tactic", channel),
                    "tactic_detail": exp.get("tactic_detail", ""),
                    "contacts": contacts,
                    "replied": replied,
                    "interested": interested,
                    "responses": replied,
                    "purchases": purchases,
                    "cost_yen": cost,
                    "cost_breakdown": [
                        {"item": "ツール・リスト費", "amount_yen": tool_cost},
                        {"item": "作業・架電費", "amount_yen": labour_cost},
                    ],
                    "revenue_yen": revenue,
                }
            )

        execution = {
            "mode": "shadow",
            "simulated": True,
            "simulated_note": "外部接触は未実行。接触結果はシード付きシミュレーションです。",
            "contacted_at": None,
            "experiments": results,
            "totals": {
                "contacts": total_contacts,
                "replied": total_replied,
                "interested": total_interested,
                "responses": total_replied,
                "purchases": total_purchases,
                "cost_yen": total_cost,
                "revenue_yen": total_revenue,
                "cost_breakdown": [
                    {"item": item, "amount_yen": amount}
                    for item, amount in total_breakdown.items()
                ],
            },
        }
        return execution

    def _observe(self, state: dict[str, Any]) -> None:
        execution = state.get("execution") or {}
        totals = execution.get("totals") or {}
        ledger = state["ledger"]
        if ledger.get("observed_cycle") == state.get("cycles"):
            # This cycle's shadow execution is already in the ledger.
            # Re-visiting observe after review must not double-count cost.
            return
        previous_cost = ledger.get("cost_yen", 0)
        previous_revenue = ledger.get("revenue_yen", 0)
        ledger["cost_yen"] = previous_cost + int(totals.get("cost_yen", 0))
        # Shadow revenue is not counted as revenue; only human-entered orders
        # move the revenue ledger. This is the honesty rule of the benchmark.
        ledger["entries"].append(
            {
                "kind": "cost",
                "amount_yen": int(totals.get("cost_yen", 0)),
                "label": "営業キャンペーン費用",
                "at": _now(),
            }
        )
        if execution.get("simulated"):
            ledger["entries"].append(
                {
                    "kind": "observation",
                    "amount_yen": 0,
                    "label": f"接触{int(totals.get('contacts', 0))}件・返信{int(totals.get('replied', 0))}件・興味{int(totals.get('interested', 0))}件・購入反応{int(totals.get('purchases', 0))}件（シミュレーション）",
                    "at": _now(),
                }
            )

        ledger["observed_cycle"] = state.get("cycles")

    def _decide(self, state: dict[str, Any]) -> dict[str, Any]:
        ledger = state["ledger"]
        spend = int(ledger.get("cost_yen", 0))
        revenue = int(ledger.get("revenue_yen", 0))
        orders = ledger.get("orders", [])
        purchase_count = len([item for item in orders if item.get("amount_yen", 0) > 0])
        execution = state.get("execution") or {}
        totals = execution.get("totals") or {}
        shadow_purchases = int(totals.get("purchases", 0))
        contacts = int(totals.get("contacts", 0))

        reasons: list[str] = []
        verdict = "MODIFY"

        if spend >= state["budget_yen"]:
            verdict = "KILL"
            reasons.append(f"予算上限（{state['budget_yen']:,}円）に到達しました")
        elif purchase_count >= 2 and revenue > spend:
            verdict = "SCALE"
            reasons.append(f"実入金{purchase_count}件・収支黒字（売上{revenue:,}円/費用{spend:,}円）")
            reasons.append("次のCampaignへ予算を寄せて拡大します")
        elif purchase_count >= 1:
            verdict = "SCALE" if revenue > spend else "MODIFY"
            reasons.append(f"実入金{purchase_count}件を確認（売上{revenue:,}円/費用{spend:,}円）")
            if verdict == "MODIFY":
                reasons.append("黒字化するまで接触条件を修正します")
        elif shadow_purchases > 0 and contacts > 0:
            verdict = "MODIFY"
            reasons.append(
                f"シミュレーションで購入反応{shadow_purchases}件を確認（実入金0件）。"
                "決済導線と提案内容を見直します"
            )
        elif contacts > 0:
            verdict = "MODIFY"
            reasons.append(f"接触{contacts}件に対して実入金0件。チャネルと対象を変更します")
        else:
            reasons.append("実績データが不足しています")

        return {
            "verdict": verdict,
            "summary": " ".join(reasons),
            "spend_yen": spend,
            "revenue_yen": revenue,
            "purchase_count": purchase_count,
            "decided_at": _now(),
        }