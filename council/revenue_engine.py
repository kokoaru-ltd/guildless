# -*- coding: utf-8 -*-
"""Guildless Revenue Engine v0.1.

会社が儲かるまでの工程を「再利用可能な部品(Skill)」に分解し、既存Capability・
API/MCP・信頼できるOSS・小さく自作の優先順で実装候補を解決し、実行計画
(Workflow)を作るオフライン動作のエンジン。

v0.1 のスコープ:
  商材1つを入れる
  -> 売上までの工程を自動分解
  -> GitHub/MCP/OSSから使える部品を探す
  -> 実行計画を作る

このモジュールは標準ライブラリだけで完結し、ネットワークなしでユニットテスト
できる。GitHub探索は discover_from_github() に分離し、API層からのみ呼ぶ。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REVENUE_STAGES: list[dict[str, str]] = [
    {"stage_id": "market", "label": "市場を探す", "kpi": "業界・課題の仮説", "unit": "市場", "note": "商材が刺さる市場と課題を特定する"},
    {"stage_id": "prospect", "label": "見込み企業を特定", "kpi": "候補企業数", "unit": "社", "note": "理想顧客条件から母集団を絞る"},
    {"stage_id": "list", "label": "リスト作成", "kpi": "連絡先取得率", "unit": "社", "note": "企業名・URL・担当者・連絡先をCSV化する"},
    {"stage_id": "contact", "label": "接触", "kpi": "返信率", "unit": "社", "note": "メール・架電・問い合わせフォームで接触する"},
    {"stage_id": "interest", "label": "興味判定", "kpi": "興味件数", "unit": "社", "note": "返信からニーズの有無を分類する"},
    {"stage_id": "proposal", "label": "提案・見積", "kpi": "商談数", "unit": "商談", "note": "個別提案と見積を提示する"},
    {"stage_id": "checkout", "label": "決済", "kpi": "受注数", "unit": "件", "note": "決済リンクで即購入できる状態にする"},
    {"stage_id": "delivery", "label": "納品", "kpi": "納品率", "unit": "件", "note": "デジタル成果物を納品する"},
    {"stage_id": "retention", "label": "継続・紹介", "kpi": "継続率・紹介数", "unit": "件", "note": "再購入と紹介を促す"},
]

FUNNEL_ASSUMPTIONS: dict[str, Any] = {
    "close_rate": 0.20,
    "meeting_rate": 0.05,
    "response_rate": 0.02,
    "note": "初期の基準値。実行後の実測値で差し替える。",
}

# ---------------------------------------------------------------------------
# Skill catalog（skill.yaml スキーマ）: 1工程 = 1つの再利用可能な部品
# ---------------------------------------------------------------------------

SKILL_CATALOG: list[dict[str, Any]] = [
    {
        "skill_id": "market_research",
        "name": "市場調査",
        "goal": "商材が刺さる市場と課題仮説を特定する",
        "inputs": ["商材", "地域", "業界"],
        "required_capabilities": ["web_search", "structured_extraction"],
        "available_implementations": [
            {"name": "gtm_marketing", "type": "oss", "detail": "GTM Skills（市場調査・営業文）"},
            {"name": "firecrawl", "type": "oss", "detail": "Web検索・抽出・構造化"},
            {"name": "mcp_search", "type": "mcp", "detail": "標準化された検索ツール"},
            {"name": "custom_research", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"market_hypotheses": ">= 3", "data_sources": ">= 3"},
        "cost_limit_yen": 200,
        "funnel_stage": "market",
        "owner": "auto",
        "kpi": "業界・課題の仮説",
        "gap_query": "market research agent web search structured extraction",
    },
    {
        "skill_id": "lead_generation",
        "name": "見込み企業の発見",
        "goal": "条件に合う企業を発見する",
        "inputs": ["商材", "理想顧客条件", "地域", "目標件数"],
        "required_capabilities": ["web_search", "browser", "structured_extraction"],
        "available_implementations": [
            {"name": "guildless_prospect_search", "type": "existing", "detail": "Guildless内蔵（公開情報から見込み企業を抽出）"},
            {"name": "ai_sales_team", "type": "oss", "detail": "企業調査・BANT/MEDDIC採点"},
            {"name": "firecrawl", "type": "oss", "detail": "Web検索・抽出・構造化"},
            {"name": "browser_use", "type": "oss", "detail": "ブラウザ操作で企業探索"},
            {"name": "custom_scraper", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"valid_lead_rate": "> 0.8", "duplicate_rate": "< 0.05"},
        "cost_limit_yen": 300,
        "funnel_stage": "prospect",
        "owner": "auto",
        "kpi": "候補企業数",
        "gap_query": "b2b lead generation company search scraper",
    },
    {
        "skill_id": "prospect_enrichment",
        "name": "連絡先・課題仮説の付与",
        "goal": "見込み企業にURL・従業員数・課題仮説・連絡先を付与する",
        "inputs": ["企業リスト", "商材"],
        "required_capabilities": ["web_search", "structured_extraction"],
        "available_implementations": [
            {"name": "ai_sales_team", "type": "oss", "detail": "企業調査・担当者特定"},
            {"name": "firecrawl", "type": "oss", "detail": "ページをJSON/スキーマで抽出"},
            {"name": "custom_enricher", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"contact_acquire_rate": "> 0.6", "enrichment_cost": "< 30円/社"},
        "cost_limit_yen": 400,
        "funnel_stage": "list",
        "owner": "auto",
        "kpi": "連絡先取得率",
        "gap_query": "b2b contact enrichment email finder",
    },
    {
        "skill_id": "offer_generation",
        "name": "提案文・見積の生成",
        "goal": "企業ごとの提案文と見積を生成する",
        "inputs": ["商材", "価格", "企業の課題仮説"],
        "required_capabilities": ["llm_routing"],
        "available_implementations": [
            {"name": "guildless_offer", "type": "existing", "detail": "Guildless内蔵（提案文と見積を生成）"},
            {"name": "salesgpt", "type": "oss", "detail": "会話ステージ・反論対応・次アクション"},
            {"name": "gtm_marketing", "type": "oss", "detail": "営業文・コンテンツ作成"},
            {"name": "custom_offer", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"offer_rate": "> 0.8", "edit_time": "< 5分/件"},
        "cost_limit_yen": 100,
        "funnel_stage": "proposal",
        "owner": "auto",
        "kpi": "商談数",
        "gap_query": "sales proposal generator personalized offer",
    },
    {
        "skill_id": "outreach_email",
        "name": "メール接触",
        "goal": "承認済みCampaignの範囲内で営業メールを送信する",
        "inputs": ["企業リスト", "提案文", "送信上限", "再接触回数"],
        "required_capabilities": ["email_send"],
        "available_implementations": [
            {"name": "guildless_contact", "type": "existing", "detail": "Guildless内蔵（承認範囲内でのみ接触）"},
            {"name": "b2b_sdr_pipeline", "type": "oss", "detail": "営業パイプライン・定期フォロー・承認ゲート"},
            {"name": "gtm_marketing", "type": "oss", "detail": "メール・フォロー列を作成"},
            {"name": "custom_sender", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"reply_rate": ">= 0.02", "spam_rate": "< 0.01"},
        "cost_limit_yen": 120,
        "funnel_stage": "contact",
        "owner": "envelope",
        "kpi": "返信率",
        "gap_query": "cold email outreach automation sales",
    },
    {
        "skill_id": "outreach_phone",
        "name": "架電",
        "goal": "承認済みCampaignの範囲内で電話営業を実行する",
        "inputs": ["企業リスト", "担当者名", "架電上限"],
        "required_capabilities": ["telephony"],
        "available_implementations": [
            {"name": "vapi", "type": "api", "detail": "電話AIエージェントAPI"},
            {"name": "twilio", "type": "api", "detail": "電話・SMS API"},
            {"name": "custom_dialer", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"connect_rate": "> 0.3", "appointment_rate": "> 0.03"},
        "cost_limit_yen": 500,
        "funnel_stage": "contact",
        "owner": "envelope",
        "kpi": "返信率",
        "gap_query": "ai phone sales call agent telephony",
    },
    {
        "skill_id": "outreach_form",
        "name": "問い合わせフォーム送信",
        "goal": "企業サイトの問い合わせフォームから営業文を送る",
        "inputs": ["企業リスト", "営業文"],
        "required_capabilities": ["browser", "structured_extraction"],
        "available_implementations": [
            {"name": "b2b_sdr_pipeline", "type": "oss", "detail": "営業パイプライン・承認ゲート"},
            {"name": "browser_use", "type": "oss", "detail": "ブラウザ操作でフォーム送信"},
            {"name": "custom_sender", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"submit_rate": "> 0.7", "skip_reject_rate": "< 0.05"},
        "cost_limit_yen": 200,
        "funnel_stage": "contact",
        "owner": "envelope",
        "kpi": "返信率",
        "gap_query": "inquiry form automation browser agent",
    },
    {
        "skill_id": "reply_classification",
        "name": "返信分類",
        "goal": "返信から興味・条件・失注を分類する",
        "inputs": ["返信メール", "商材"],
        "required_capabilities": ["llm_routing"],
        "available_implementations": [
            {"name": "ai_sales_team", "type": "oss", "detail": "リード採点・分類"},
            {"name": "salesgpt", "type": "oss", "detail": "会話ステージ判定"},
            {"name": "custom_classifier", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"classification_accuracy": "> 0.9"},
        "cost_limit_yen": 50,
        "funnel_stage": "interest",
        "owner": "auto",
        "kpi": "興味件数",
        "gap_query": "email reply classification lead scoring",
    },
    {
        "skill_id": "meeting_scheduling",
        "name": "日程調整",
        "goal": "興味あり企業と商談日程を調整する",
        "inputs": ["候補日程", "担当者連絡先"],
        "required_capabilities": ["calendar", "email_send"],
        "available_implementations": [
            {"name": "b2b_sdr_pipeline", "type": "oss", "detail": "定期フォロー・次アクション管理"},
            {"name": "custom_scheduler", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"booked_rate": "> 0.5"},
        "cost_limit_yen": 60,
        "funnel_stage": "proposal",
        "owner": "auto",
        "kpi": "商談数",
        "gap_query": "meeting scheduling assistant email",
    },
    {
        "skill_id": "checkout_link",
        "name": "決済リンクの作成",
        "goal": "受注企業に即購入できる決済リンクを渡す",
        "inputs": ["見積内容", "価格"],
        "required_capabilities": ["payment"],
        "available_implementations": [
            {"name": "guildless_payment", "type": "existing", "detail": "決済の実行は人間が行う（Stripe等）"},
        ],
        "success_metrics": {"checkout_rate": "> 0.8"},
        "cost_limit_yen": 0,
        "funnel_stage": "checkout",
        "owner": "human",
        "kpi": "受注数",
        "gap_query": "stripe payment link generator",
    },
    {
        "skill_id": "digital_delivery",
        "name": "デジタル納品物の作成",
        "goal": "受注後の成果物ファイルを生成する",
        "inputs": ["受注内容", "企業の課題"],
        "required_capabilities": ["coding", "document"],
        "available_implementations": [
            {"name": "guildless_delivery", "type": "existing", "detail": "Guildless内蔵（デジタル成果物を生成）"},
            {"name": "openhands", "type": "oss", "detail": "自律実行SDKで成果物を作成"},
            {"name": "custom_build", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"delivery_hours": "<= 48", "rework_rate": "< 0.2"},
        "cost_limit_yen": 100,
        "funnel_stage": "delivery",
        "owner": "auto",
        "kpi": "納品率",
        "gap_query": "digital document report generator automation",
    },
    {
        "skill_id": "follow_up",
        "name": "再接触",
        "goal": "承認された回数まで自動で再接触する",
        "inputs": ["未返信リスト", "再接触回数"],
        "required_capabilities": ["email_send"],
        "available_implementations": [
            {"name": "guildless_followup", "type": "existing", "detail": "Guildless内蔵（承認された回数まで再接触）"},
            {"name": "b2b_sdr_pipeline", "type": "oss", "detail": "定期フォロー列"},
            {"name": "custom_sender", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"reply_lift": "> 0.3"},
        "cost_limit_yen": 60,
        "funnel_stage": "retention",
        "owner": "envelope",
        "kpi": "継続率・紹介数",
        "gap_query": "sales follow up sequence automation",
    },
    {
        "skill_id": "referral_loop",
        "name": "継続・紹介",
        "goal": "購入企業に再購入と紹介を促す",
        "inputs": ["購入企業リスト", "成果"],
        "required_capabilities": ["email_send"],
        "available_implementations": [
            {"name": "salesgpt", "type": "oss", "detail": "次アクション管理"},
            {"name": "custom_referral", "type": "custom", "detail": "小さく自作"},
        ],
        "success_metrics": {"retention_rate": "> 0.3", "referral_rate": "> 0.1"},
        "cost_limit_yen": 60,
        "funnel_stage": "retention",
        "owner": "auto",
        "kpi": "継続率・紹介数",
        "gap_query": "customer referral upsell automation",
    },
]

# 工程 -> 担当Skill
STAGE_SKILLS: dict[str, list[str]] = {
    "market": ["market_research"],
    "prospect": ["lead_generation"],
    "list": ["prospect_enrichment"],
    "contact": ["outreach_email", "outreach_phone", "outreach_form"],
    "interest": ["reply_classification"],
    "proposal": ["offer_generation", "meeting_scheduling"],
    "checkout": ["checkout_link"],
    "delivery": ["digital_delivery"],
    "retention": ["follow_up", "referral_loop"],
}

# インストール済みSales OSSパックとSkillの対応
SALES_OSS_PACK_MAP: dict[str, list[str]] = {
    "market_research": ["gtm_marketing"],
    "lead_generation": ["ai_sales_team"],
    "prospect_enrichment": ["ai_sales_team"],
    "offer_generation": ["salesgpt", "gtm_marketing"],
    "outreach_email": ["b2b_sdr_pipeline", "gtm_marketing"],
    "outreach_phone": [],
    "outreach_form": ["b2b_sdr_pipeline"],
    "reply_classification": ["ai_sales_team", "salesgpt"],
    "meeting_scheduling": ["b2b_sdr_pipeline"],
    "checkout_link": [],
    "digital_delivery": [],
    "follow_up": ["b2b_sdr_pipeline"],
    "referral_loop": ["salesgpt"],
}

_SALES_PACK_LABELS: dict[str, str] = {
    "b2b_sdr_pipeline": "B2B SDR Pipeline（営業パイプライン・承認ゲート）",
    "ai_sales_team": "AI Sales Team（企業調査・採点）",
    "salesgpt": "SalesGPT（会話ステージ・反論対応）",
    "gtm_marketing": "GTM Skills（市場調査・営業文）",
}
# ---------------------------------------------------------------------------
# OSSアダプタ: 能力(capability) -> 実装候補。既存OSS/MCP/APIを包む薄い層。
# Guildlessはコード本体を持たず、ここで「部品市場」から実装を選べる。
# ---------------------------------------------------------------------------

OSS_ADAPTERS: dict[str, list[dict[str, str]]] = {
    "web_search": [
        {"name": "firecrawl", "type": "oss", "detail": "Web検索・抽出・構造化"},
        {"name": "mcp_search", "type": "mcp", "detail": "MCP標準化された検索ツール"},
    ],
    "browser": [
        {"name": "browser_use", "type": "oss", "detail": "LLM制御のブラウザ操作"},
        {"name": "playwright_agent", "type": "oss", "detail": "Playwrightでフォーム送信"},
    ],
    "coding": [
        {"name": "openhands", "type": "oss", "detail": "自律実行SDK（成果物作成）"},
    ],
    "workflow": [
        {"name": "n8n", "type": "oss", "detail": "ワークフロー基盤で工程を連結"},
    ],
    "llm_routing": [
        {"name": "litellm", "type": "oss", "detail": "100以上のLLMプロバイダを統一IFで利用"},
        {"name": "huggingface", "type": "oss", "detail": "モデル・データセット・Spaces"},
        {"name": "modelscope", "type": "oss", "detail": "モデル・データセット・実行例"},
    ],
    "model_registry": [
        {"name": "huggingface", "type": "oss", "detail": "能力部品倉庫（分類・OCR・音声など）"},
        {"name": "modelscope", "type": "oss", "detail": "モデル・データセット供給源"},
    ],
    "mcp_discovery": [
        {"name": "mcp_registry", "type": "mcp", "detail": "外部ツールを標準化された形で発見・接続"},
    ],
    "structured_extraction": [
        {"name": "firecrawl", "type": "oss", "detail": "ページをスキーマ付きJSONで抽出"},
    ],
    "email_send": [
        {"name": "resend", "type": "api", "detail": "営業メール送信API"},
        {"name": "sendgrid", "type": "api", "detail": "メール送信API"},
    ],
    "telephony": [
        {"name": "vapi", "type": "api", "detail": "電話AIエージェントAPI"},
        {"name": "twilio", "type": "api", "detail": "電話・SMS API"},
    ],
    "payment": [
        {"name": "stripe", "type": "api", "detail": "決済リンク・入金確認"},
    ],
    "calendar": [
        {"name": "cal_dot_com", "type": "api", "detail": "日程調整API"},
    ],
    "document": [
        {"name": "openhands", "type": "oss", "detail": "成果物ファイル生成"},
    ],
}

CAPABILITY_SOURCE_LABELS: dict[str, str] = {
    "既存": "Guildless内蔵",
    "インストール済みOSS": "導入済みOSS",
    "OSS候補": "OSS候補",
    "API/MCP": "API/MCP候補",
    "自作": "小さく自作",
}

CAPABILITY_SOURCE_PRIORITY: list[str] = [
    "既存",
    "インストール済みOSS",
    "OSS候補",
    "API/MCP",
    "自作",
]

# Sales OSSパックの実ID(third_party/sales) -> このモジュールの短いid
_PACK_ID_ALIASES: dict[str, str] = {
    "b2b-sdr-agent-template": "b2b_sdr_pipeline",
    "ai-sales-team": "ai_sales_team",
    "salesgpt-conversation": "salesgpt",
    "gtm-marketing": "gtm_marketing",
}


class RevenueEngineError(ValueError):
    """Raised for invalid plan inputs or malformed state."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _plan_id() -> str:
    return f"rev_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"

class RevenueEngine:
    """商材1つから売上までの実行計画(Workflow)を組み立てるオフラインエンジン。

    逆算(売上 -> 受注 -> 商談 -> 接触)と、工程ごとの再利用可能な部品
    (Skill)の解決を担当する。ネットワークや外部APIは使わない。
    """

    def __init__(self, sales_registry: Any | None = None):
        self.sales_registry = sales_registry

    # -- public -----------------------------------------------------------

    def analyze(
        self,
        *,
        product: str,
        price_yen: int,
        target_revenue_yen: int | None = None,
        budget_yen: int = 30_000,
        deadline_days: int = 14,
        region: str = "",
        industry: str = "",
    ) -> dict[str, Any]:
        product = _clean_text(product)
        if not product:
            raise RevenueEngineError("商品名を入力してください")
        if not 300 <= price_yen <= 10_000_000:
            raise RevenueEngineError("価格は300円以上1,000万円以下にしてください")
        target = target_revenue_yen if target_revenue_yen is not None else price_yen * 6
        if not 300 <= target <= 100_000_000:
            raise RevenueEngineError("目標売上は300円以上1億円以下にしてください")
        if not 1_000 <= budget_yen <= 1_000_000:
            raise RevenueEngineError("予算は1,000円以上100万円以下にしてください")
        if not 1 <= deadline_days <= 90:
            raise RevenueEngineError("期間は1日以上90日以下にしてください")

        close_rate = float(FUNNEL_ASSUMPTIONS["close_rate"])
        meeting_rate = float(FUNNEL_ASSUMPTIONS["meeting_rate"])
        response_rate = float(FUNNEL_ASSUMPTIONS["response_rate"])

        orders = max(1, math.ceil(target / price_yen))
        meetings = max(1, math.ceil(orders / close_rate))
        contacts = max(1, math.ceil(meetings / meeting_rate))
        interested = max(1, math.ceil(contacts * response_rate))

        installed_packs = self._installed_sales_packs()
        capabilities = self._resolve_capabilities(installed_packs)
        gaps = self._detect_gaps(capabilities)
        workflow = self._build_workflow(capabilities)
        funnel = self._build_funnel(contacts, interested, meetings, orders)

        return {
            "plan_id": _plan_id(),
            "created_at": _now(),
            "product": product,
            "price_yen": price_yen,
            "target_revenue_yen": target,
            "budget_yen": budget_yen,
            "deadline_days": deadline_days,
            "region": _clean_text(region),
            "industry": _clean_text(industry),
            "backward_calc": {
                "target_revenue_yen": target,
                "price_yen": price_yen,
                "required_orders": orders,
                "meeting_rate": meeting_rate,
                "required_meetings": meetings,
                "response_rate": response_rate,
                "required_contacts": contacts,
                "interested": interested,
                "note": "基準値はFUNNEL_ASSUMPTIONS。実行後の実測値で差し替える。",
            },
            "funnel": funnel,
            "capabilities": capabilities,
            "workflow": workflow,
            "gaps": gaps,
            "sources": {
                "installed_packs": installed_packs,
                "oss_adapters": {
                    capability: [item["name"] for item in items]
                    for capability, items in OSS_ADAPTERS.items()
                },
            },
            "scout": {"status": "pending", "queried_at": None, "results": []},
        }

    # -- internals --------------------------------------------------------

    def _installed_sales_packs(self) -> list[str]:
        if self.sales_registry is None:
            return []
        try:
            aliases: list[str] = []
            for pack in self.sales_registry.packs():
                if not pack.get("installed"):
                    continue
                alias = _PACK_ID_ALIASES.get(str(pack.get("id", "")))
                if alias:
                    aliases.append(alias)
            return sorted(set(aliases))
        except Exception:
            return []

    @staticmethod
    def _build_funnel(
        contacts: int, interested: int, meetings: int, orders: int
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for stage in REVENUE_STAGES:
            stage_id = stage["stage_id"]
            if stage_id == "market":
                count: int | None = None
                basis = "質的"
            elif stage_id == "prospect":
                count = contacts * 10
                basis = "想定"
            elif stage_id == "list":
                count = contacts
                basis = "目標"
            elif stage_id == "contact":
                count = contacts
                basis = "目標"
            elif stage_id == "interest":
                count = interested
                basis = "基準"
            elif stage_id == "proposal":
                count = meetings
                basis = "目標"
            elif stage_id == "checkout":
                count = orders
                basis = "目標"
            elif stage_id == "delivery":
                count = orders
                basis = "目標"
            else:  # retention
                count = orders
                basis = "想定"
            rows.append(
                {
                    "stage_id": stage_id,
                    "label": stage["label"],
                    "kpi": stage["kpi"],
                    "unit": stage["unit"],
                    "note": stage["note"],
                    "count": count,
                    "basis": basis,
                }
            )
        return rows

    def _resolve_capabilities(self, installed_packs: list[str]) -> list[dict[str, Any]]:
        installed_set = set(installed_packs)
        capabilities: list[dict[str, Any]] = []
        for skill in SKILL_CATALOG:
            candidates: list[dict[str, Any]] = []
            seen: set[str] = set()

            def add_candidate(name: str, impl_type: str, detail: str, source: str) -> None:
                if name in seen:
                    return
                seen.add(name)
                candidates.append(
                    {
                        "name": name,
                        "type": impl_type,
                        "detail": detail,
                        "source": source,
                    }
                )

            for impl in skill.get("available_implementations", []):
                impl_type = str(impl.get("type", ""))
                name = str(impl.get("name", ""))
                detail = str(impl.get("detail", ""))
                if impl_type == "existing":
                    add_candidate(name, impl_type, detail, "既存")
                elif impl_type == "oss":
                    if name in installed_set:
                        add_candidate(name, impl_type, detail, "インストール済みOSS")
                    else:
                        add_candidate(name, impl_type, detail, "OSS候補")
                elif impl_type in ("api", "mcp"):
                    add_candidate(name, impl_type, detail, "API/MCP")
                elif impl_type == "custom":
                    add_candidate(name, impl_type, detail, "自作")

            # 能力ベースのOSSアダプタをフォールバック候補として追加
            for capability in skill.get("required_capabilities", []):
                for adapter in OSS_ADAPTERS.get(capability, []):
                    adapter_type = str(adapter["type"])
                    source = "OSS候補" if adapter_type == "oss" else "API/MCP"
                    add_candidate(
                        str(adapter["name"]), adapter_type, str(adapter["detail"]), source
                    )

            candidates.sort(
                key=lambda item: CAPABILITY_SOURCE_PRIORITY.index(item["source"])
            )
            primary = candidates[0] if candidates else None

            has_existing = any(c["source"] == "既存" for c in candidates)
            has_installed = any(c["source"] == "インストール済みOSS" for c in candidates)
            status = self._status_for(skill, has_existing, has_installed)

            capabilities.append(
                {
                    "skill_id": skill["skill_id"],
                    "name": skill["name"],
                    "goal": skill["goal"],
                    "owner": skill.get("owner", "auto"),
                    "kpi": skill.get("kpi", ""),
                    "cost_limit_yen": skill.get("cost_limit_yen", 0),
                    "required_capabilities": skill.get("required_capabilities", []),
                    "status": status,
                    "primary": primary,
                    "candidates": candidates,
                }
            )
        return capabilities

    @staticmethod
    def _status_for(
        skill: dict[str, Any], has_existing: bool, has_installed: bool
    ) -> str:
        owner = str(skill.get("owner", "auto"))
        if owner == "human":
            return "人間操作"
        if owner == "envelope":
            return "承認範囲" if (has_existing or has_installed) else "要確保"
        if has_existing or has_installed:
            return "確保済み"
        return "要確保"

    @staticmethod
    def _detect_gaps(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {cap["skill_id"]: cap for cap in capabilities}
        gaps: list[dict[str, Any]] = []
        for skill in SKILL_CATALOG:
            cap = by_id.get(skill["skill_id"])
            if cap is None or cap["status"] != "要確保":
                continue
            gaps.append(
                {
                    "skill_id": skill["skill_id"],
                    "name": skill["name"],
                    "required_capabilities": skill.get("required_capabilities", []),
                    "suggested_query": skill.get("gap_query", ""),
                    "discovered_candidates": [],
                }
            )
        return gaps

    @staticmethod
    def _build_workflow(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {cap["skill_id"]: cap for cap in capabilities}
        workflow: list[dict[str, Any]] = []
        step = 0
        for stage in REVENUE_STAGES:
            stage_id = stage["stage_id"]
            for skill_id in STAGE_SKILLS.get(stage_id, []):
                cap = by_id.get(skill_id)
                if cap is None:
                    continue
                step += 1
                workflow.append(
                    {
                        "step": step,
                        "stage_id": stage_id,
                        "stage_label": stage["label"],
                        "skill_id": skill_id,
                        "name": cap["name"],
                        "goal": cap["goal"],
                        "owner": cap["owner"],
                        "status": cap["status"],
                        "primary": cap["primary"],
                        "cost_limit_yen": cap["cost_limit_yen"],
                    }
                )
        return workflow

class RevenuePlanManager:
    """Revenue Engineの実行計画を output_root/revenue に永続化する。"""

    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)
        self.plans_dir = self.output_root / "revenue"
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, plan_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", plan_id):
            raise RevenueEngineError(f"invalid plan id: {plan_id!r}")
        return self.plans_dir / f"{plan_id}.json"

    def save(self, plan: dict[str, Any]) -> None:
        path = self._state_path(str(plan["plan_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(plan, handle, ensure_ascii=False, indent=2, sort_keys=True)
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

    def load(self, plan_id: str) -> dict[str, Any]:
        try:
            return json.loads(self._state_path(plan_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RevenueEngineError(f"plan not found: {plan_id}") from exc

    def latest_id(self) -> str | None:
        candidates = [path.stem for path in self.plans_dir.glob("*.json")]
        if not candidates:
            return None
        return max(candidates)

    def latest(self) -> dict[str, Any] | None:
        plan_id = self.latest_id()
        return self.load(plan_id) if plan_id else None

    def list_plans(self) -> list[dict[str, Any]]:
        plan_ids = sorted((path.stem for path in self.plans_dir.glob("*.json")), reverse=True)
        return [self.load(plan_id) for plan_id in plan_ids]


async def discover_from_github(
    plan: dict[str, Any],
    scout: Any,
    *,
    max_per_query: int = 3,
) -> dict[str, Any]:
    """不足Skill(gaps)ごとにGitHubから実装候補を探索してplanに反映する。

    scout は GitHubScout 互換（research(queries, constraints) を返す）。
    テストではFakeを注入し、本番は実GitHub APIを使う。
    """
    from council.github_scout import GitHubScoutError
    from council.schemas import GitHubSelectionConstraints

    gaps = plan.get("gaps", [])
    results: list[dict[str, Any]] = []
    for gap in gaps:
        query = str(gap.get("suggested_query", "")).strip()
        if not query:
            continue
        constraints = GitHubSelectionConstraints(
            max_candidates=max_per_query,
            min_stars=5,
            active_within_days=1095,
        )
        try:
            snapshot = await scout.research([query], constraints)
        except GitHubScoutError as exc:
            plan["scout"] = {
                "status": "error",
                "queried_at": _now(),
                "error": str(exc),
                "results": results,
            }
            raise
        accepted = snapshot.get("accepted", [])[: max_per_query]
        gap["discovered_candidates"] = [
            {
                "full_name": str(item.get("full_name", "")),
                "html_url": str(item.get("html_url", "")),
                "description": str(item.get("description", "")),
                "stars": int(item.get("stars", 0) or 0),
                "score": float(item.get("score", 0.0) or 0.0),
                "capabilities": item.get("capabilities", []),
            }
            for item in accepted
        ]
        results.append(
            {
                "skill_id": gap["skill_id"],
                "query": query,
                "found": len(accepted),
            }
        )
    plan["scout"] = {
        "status": "done",
        "queried_at": _now(),
        "results": results,
    }
    return plan
