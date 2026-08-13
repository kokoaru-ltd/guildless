from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SALES_OSS_ROOT = Path(__file__).resolve().parent.parent / "third_party" / "sales"


UPSTREAM_PACKS = (
    {
        "id": "b2b-sdr-pipeline",
        "name": "B2B SDR Pipeline",
        "repository": "iPythoning/b2b-sdr-agent-template",
        "commit": "e71bfd4da4a56153ab5ef05a4bd684d370b8c90c",
        "license": "MIT",
        "role": "営業パイプライン・定期フォロー・承認ゲート",
        "path": "b2b-sdr-agent-template",
    },
    {
        "id": "ai-sales-team",
        "name": "AI Sales Team",
        "repository": "zubair-trabzada/ai-sales-team-claude",
        "commit": "efef8b8a4ce8c93d8d6b4af9d1423db38f0de2ce",
        "license": "MIT",
        "role": "BANT/MEDDIC採点・企業調査・営業Skill",
        "path": "ai-sales-team-claude",
    },
    {
        "id": "salesgpt-conversation",
        "name": "SalesGPT",
        "repository": "filip-michalsky/SalesGPT",
        "commit": "7cd1d4f9fae2a5610fac76e1c0edc38a2fafd388",
        "license": "MIT",
        "role": "会話ステージ・反論対応・次アクション",
        "path": "SalesGPT",
    },
    {
        "id": "gtm-marketing",
        "name": "GTM Skills",
        "repository": "gtm-skills/gtm",
        "commit": "6e42775af8900c1a98669db2a6ad2943132b8ac3",
        "license": "MIT",
        "role": "市場調査・営業文・コンテンツ・GTMチーム",
        "path": "gtm",
    },
)


class SalesOssError(RuntimeError):
    pass


class SalesOssRegistry:
    """Read-only adapter over fixed-commit sales and marketing OSS packs."""

    def __init__(self, root: Path = SALES_OSS_ROOT):
        self.root = root.resolve()

    def _pack_path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if self.root != path and self.root not in path.parents:
            raise SalesOssError("sales OSS path escaped the configured root")
        return path

    def packs(self) -> list[dict[str, Any]]:
        result = []
        for pack in UPSTREAM_PACKS:
            path = self._pack_path(pack["path"])
            result.append(
                {
                    **pack,
                    "installed": path.is_dir(),
                    "source_url": f"https://github.com/{pack['repository']}/tree/{pack['commit']}",
                }
            )
        return result

    def _require(self, relative: str) -> Path:
        path = self._pack_path(relative)
        if not path.is_file():
            raise SalesOssError(
                "Sales OSS packs are not installed. Run: git submodule update --init --recursive"
            )
        return path

    def sales_pipeline(self) -> list[dict[str, Any]]:
        source = self._require("b2b-sdr-agent-template/workspace/AGENTS.md")
        text = source.read_text(encoding="utf-8")
        stages = []
        for match in re.finditer(r"^### Stage\s+(\d+):\s+(.+?)\s*$", text, re.MULTILINE):
            number = int(match.group(1))
            title = match.group(2).strip()
            stages.append(
                {
                    "order": number,
                    "title": title,
                    "source": "iPythoning/b2b-sdr-agent-template:workspace/AGENTS.md",
                }
            )
        if not stages:
            raise SalesOssError("the pinned B2B SDR pipeline contains no stages")
        return stages

    def heartbeat_checks(self) -> list[str]:
        source = self._require("b2b-sdr-agent-template/workspace/HEARTBEAT.md")
        text = source.read_text(encoding="utf-8")
        return [
            match.group(1).strip()
            for match in re.finditer(r"^##\s+\d+\.\s+(.+?)\s*$", text, re.MULTILINE)
        ]

    def conversation_stages(self) -> list[dict[str, str]]:
        source = self._require("SalesGPT/salesgpt/stages.py")
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        stages: dict[str, str] | None = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "CONVERSATION_STAGES"
                for target in node.targets
            ):
                stages = ast.literal_eval(node.value)
                break
        if not stages:
            raise SalesOssError("the pinned SalesGPT stages could not be read")
        return [
            {
                "id": key,
                "description": value,
                "source": "filip-michalsky/SalesGPT:salesgpt/stages.py",
            }
            for key, value in sorted(stages.items(), key=lambda item: int(item[0]))
        ]

    def marketing_team(self) -> list[dict[str, str]]:
        base = self._pack_path("gtm/openclaw-skills")
        roles = (
            ("scout", "市場と見込み客を調査", "調査"),
            ("rep", "接触案と反論対応を作成", "営業"),
            ("closer", "提案・条件・次アクションを整理", "商談"),
            ("writer", "メール・記事・フォロー列を作成", "マーケ"),
        )
        result = []
        for role, description, lane in roles:
            source = base / role / "SKILL.md"
            if not source.is_file():
                raise SalesOssError(f"missing pinned GTM skill: {role}")
            result.append(
                {
                    "id": role,
                    "name": role.capitalize(),
                    "lane": lane,
                    "description": description,
                    "source": f"gtm-skills/gtm:openclaw-skills/{role}/SKILL.md",
                }
            )
        return result

    def score_lead(self, payload: dict[str, Any]) -> dict[str, Any]:
        script = self._require("ai-sales-team-claude/scripts/lead_scorer.py")
        # Keep the pinned upstream script untouched while making its JSON stream
        # deterministic on Windows, where the inherited console encoding is CP932.
        child_env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        completed = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            cwd=str(script.parent),
            env=child_env,
            check=False,
        )
        if completed.returncode != 0:
            raise SalesOssError(completed.stderr.strip() or "upstream lead scorer failed")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise SalesOssError("upstream lead scorer returned invalid JSON") from exc
        return {
            **result,
            "mode": "shadow",
            "external_actions_performed": False,
            "source": {
                "repository": "zubair-trabzada/ai-sales-team-claude",
                "commit": "efef8b8a4ce8c93d8d6b4af9d1423db38f0de2ce",
                "file": "scripts/lead_scorer.py",
            },
        }

    def overview(self) -> dict[str, Any]:
        packs = self.packs()
        installed = all(pack["installed"] for pack in packs)
        result: dict[str, Any] = {
            "status": "ready" if installed else "setup_required",
            "mode": "shadow",
            "external_sending_enabled": False,
            "automatic_contract_enabled": False,
            "automatic_payment_enabled": False,
            "packs": packs,
        }
        if installed:
            result.update(
                {
                    "pipeline": self.sales_pipeline(),
                    "heartbeat_checks": self.heartbeat_checks(),
                    "conversation_stages": self.conversation_stages(),
                    "marketing_team": self.marketing_team(),
                }
            )
        return result
