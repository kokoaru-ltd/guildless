from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from council.action_executor import (
    CodexActionExecutor,
    GitRepositoryMaterializer,
    WorkspacePolicy,
    verify_execution,
)
from council.config import Settings
from council.guildless import GuildlessOrchestrator
from council.orchestrator import default_provider_factory
from council.schemas import GuildlessJobRequest
from council.security import COUNCIL_ROOT, validate_output_root
from council.storage import write_json


JobEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GuildlessAutonomousRunner:
    """Turns one objective into research, selection, local implementation and verification."""

    def __init__(
        self,
        settings: Settings,
        *,
        output_boundary: Path = COUNCIL_ROOT,
        workspace_policy: WorkspacePolicy | None = None,
        materializer: GitRepositoryMaterializer | None = None,
    ):
        self.settings = settings
        self.output_boundary = output_boundary
        self.output_root = validate_output_root(settings.output_dir, output_boundary)
        self.workspace_policy = workspace_policy or WorkspacePolicy()
        self.materializer = materializer or GitRepositoryMaterializer()

    async def run(
        self,
        request: GuildlessJobRequest,
        *,
        job_id: str | None = None,
        event_callback: JobEventCallback | None = None,
    ) -> dict[str, Any]:
        job_id = job_id or self._job_id(request.workspace_label)
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        write_json(job_dir / "job_request.json", request.model_dump(mode="json"))
        await self._emit(event_callback, "researching", {"job_id": job_id})
        analysis_id = f"guildless_{job_id[4:]}"
        orchestrator = GuildlessOrchestrator(self.settings, output_boundary=self.output_boundary)
        try:
            analysis = await orchestrator.run(
                goal=request.objective,
                github_queries=request.github_queries,
                context=request.context,
                constraints=request.constraints,
                allowed_providers=list(request.allowed_providers),
                max_rounds=request.max_rounds,
                output_dir=self.output_root,
                run_id=analysis_id,
                event_callback=self._analysis_event_adapter(event_callback),
            )
        finally:
            await orchestrator.aclose()
        return await self.execute_from_analysis(
            analysis_run_dir=analysis.run_dir,
            objective=request.objective,
            workspace_label=request.workspace_label,
            max_execution_minutes=request.max_execution_minutes,
            job_id=job_id,
            job_dir=job_dir,
            event_callback=event_callback,
        )

    async def execute_from_analysis(
        self,
        *,
        analysis_run_dir: Path,
        objective: str,
        workspace_label: str = "job",
        max_execution_minutes: int = 20,
        job_id: str | None = None,
        job_dir: Path | None = None,
        event_callback: JobEventCallback | None = None,
    ) -> dict[str, Any]:
        analysis_run_dir = analysis_run_dir.resolve()
        if not analysis_run_dir.is_dir() or not (analysis_run_dir / "github_selection.json").is_file():
            raise ValueError("analysis run is missing github_selection.json")
        if not (analysis_run_dir / "final_decision.json").is_file():
            raise ValueError("analysis run is missing final_decision.json")
        job_id = job_id or self._job_id(workspace_label)
        job_dir = job_dir or (self.output_root / job_id)
        job_dir.mkdir(parents=True, exist_ok=job_dir.exists())
        try:
            selection = _read_json(analysis_run_dir / "github_selection.json")
            accepted = selection.get("accepted")
            if not isinstance(accepted, list) or not accepted:
                raise RuntimeError("GitHub selection produced no accepted repository")
            selected = accepted[0]
            if not isinstance(selected, dict):
                raise RuntimeError("selected repository record is invalid")
            decision = _read_json(analysis_run_dir / "final_decision.json")
            write_json(job_dir / "selected_repository.json", selected)
            write_json(
                job_dir / "analysis_link.json",
                {
                    "analysis_run_dir": str(analysis_run_dir),
                    "github_selection_sha256": _file_sha256(analysis_run_dir / "github_selection.json"),
                    "final_decision_sha256": _file_sha256(analysis_run_dir / "final_decision.json"),
                },
            )
            workspace = self.workspace_policy.create(job_id)
            await self._emit(
                event_callback,
                "cloning",
                {"repository": selected["full_name"], "commit_sha": selected["commit_sha"]},
            )
            repository = await self.materializer.materialize(
                full_name=str(selected["full_name"]),
                commit_sha=str(selected["commit_sha"]),
                workspace=workspace,
            )
            await self._emit(event_callback, "implementing", {"workspace": str(workspace)})
            providers = default_provider_factory(self.settings)
            try:
                executor = CodexActionExecutor(providers["codex"])  # type: ignore[arg-type]
                report, audit = await executor.execute(
                    objective=objective,
                    selected_repository=selected,
                    council_decision=decision,
                    workspace=workspace,
                    max_execution_minutes=max_execution_minutes,
                    event_callback=event_callback,
                )
            finally:
                for provider in providers.values():
                    await provider.aclose()
            await self._emit(event_callback, "verifying", {"workspace": str(workspace)})
            verification = verify_execution(
                workspace=workspace, repository=repository, report=report, audit=audit
            )
            final_status = (
                "awaiting_approval"
                if verification["accepted"] and verification["approval_required"]
                else "completed"
                if verification["accepted"]
                else "partial"
            )
            write_json(job_dir / "execution_report.json", report.model_dump(mode="json"))
            write_json(job_dir / "execution_audit.json", audit)
            write_json(job_dir / "verification.json", verification)
            result = {
                "job_id": job_id,
                "status": final_status,
                "objective": objective,
                "analysis_run_dir": str(analysis_run_dir),
                "workspace": str(workspace),
                "selected_repository": selected,
                "execution_report": report.model_dump(mode="json"),
                "verification": verification,
                "external_actions_performed": False,
                "confirmed_decision_created": False,
            }
            write_json(job_dir / "job_result.json", result)
            self._write_manifest(job_dir, result)
            await self._emit(event_callback, final_status, {"accepted": verification["accepted"]})
            return result
        except Exception as exc:
            failure = {
                "job_id": job_id,
                "status": "failed",
                "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                "external_actions_performed": False,
            }
            write_json(job_dir / "job_result.json", failure)
            await self._emit(event_callback, "failed", {"error": failure["error"]})
            raise

    @staticmethod
    def _job_id(label: str) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        return f"job_{label}_{stamp}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    async def _emit(
        callback: JobEventCallback | None, status: str, details: dict[str, Any]
    ) -> None:
        if callback:
            await callback(status, details)

    @staticmethod
    def _analysis_event_adapter(
        callback: JobEventCallback | None,
    ) -> JobEventCallback | None:
        if callback is None:
            return None

        async def emit(status: str, details: dict[str, Any]) -> None:
            await callback(f"analysis_{status}", details)

        return emit

    @staticmethod
    def _write_manifest(job_dir: Path, result: dict[str, Any]) -> None:
        files: dict[str, str] = {}
        for path in sorted(job_dir.glob("*.json")):
            if path.name != "job_manifest.json":
                files[path.name] = _file_sha256(path)
        write_json(
            job_dir / "job_manifest.json",
            {
                "job_id": result["job_id"],
                "status": result["status"],
                "created_at": datetime.now(UTC).isoformat(),
                "files_sha256": files,
                "external_actions_performed": False,
                "confirmed_decision_created": False,
            },
        )
