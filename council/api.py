from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from council.autonomous import GuildlessAutonomousRunner
from council.config import Settings
from council.guildless import GuildlessOrchestrator
from council.orchestrator import CouncilOrchestrator
from council.sales_oss import SalesOssError, SalesOssRegistry
from council.schemas import (
    CouncilRunAccepted,
    CouncilRunRequest,
    GuildlessJobRequest,
    GuildlessRunRequest,
    SalesLeadScoreRequest,
)
from council.security import COUNCIL_ROOT, validate_output_root
from council.storage import write_json
from council.transcription import LocalWhisperTranscriber


TERMINAL_STATES = {"completed", "degraded", "partial", "awaiting_approval", "failed"}
LEGACY_UI_ROOT = Path(__file__).resolve().parent / "ui"
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
UI_ROOT = FRONTEND_DIST if (FRONTEND_DIST / "index.html").exists() else LEGACY_UI_ROOT
WORKSPACE_ROOT = Path("D:/guildless_workspaces").resolve()
PREVIEWABLE_SUFFIXES = {".md", ".txt", ".json", ".py", ".ts", ".tsx", ".js", ".css", ".html", ".toml", ".yaml", ".yml"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg",
    "audio/mp4", "video/webm", "application/octet-stream",
}


class CouncilRunManager:
    def __init__(
        self,
        settings: Settings,
        *,
        output_boundary: Path = COUNCIL_ROOT,
        orchestrator_factory: Callable[[Settings], CouncilOrchestrator] | None = None,
    ):
        self.settings = settings
        self.output_boundary = output_boundary
        self.output_root = validate_output_root(settings.output_dir, output_boundary)
        self.orchestrator_factory = orchestrator_factory
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
            raise KeyError(run_id)
        path = self.output_root / run_id
        if not path.is_dir():
            raise KeyError(run_id)
        return path

    async def create(self, request: CouncilRunRequest) -> CouncilRunAccepted:
        run_id = uuid.uuid4().hex
        run_dir = self.output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        self.locks[run_id] = asyncio.Lock()
        write_json(
            run_dir / "api_request.json",
            {
                **request.model_dump(mode="json"),
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "automatic_promotion_supported": False,
            },
        )
        await self._record_event(run_id, "queued", {"message": "run accepted"})
        task = asyncio.create_task(self._execute(run_id, request), name=f"council-{run_id}")
        self.tasks[run_id] = task
        task.add_done_callback(lambda _task, key=run_id: self.tasks.pop(key, None))
        return CouncilRunAccepted(
            run_id=run_id,
            status="queued",
            run_url=f"/v1/council/runs/{run_id}",
            events_url=f"/v1/council/runs/{run_id}/events",
        )

    async def _execute(self, run_id: str, request: CouncilRunRequest) -> None:
        orchestrator = (
            self.orchestrator_factory(self.settings)
            if self.orchestrator_factory
            else CouncilOrchestrator(self.settings, output_boundary=self.output_boundary)
        )

        async def emit(run_status: str, details: dict) -> None:
            await self._record_event(run_id, run_status, details)

        try:
            await orchestrator.ask(
                question=request.question,
                task_type=request.task_type,
                mode=request.mode,
                inline_context=request.context,
                allowed_providers=list(request.allowed_providers),
                output_dir=self.output_root,
                run_id=run_id,
                event_callback=emit,
            )
        except Exception as exc:
            await self._record_event(
                run_id,
                "failed",
                {"error": f"{type(exc).__name__}: {str(exc)[:500]}"},
            )
        finally:
            await orchestrator.aclose()

    async def _record_event(self, run_id: str, run_status: str, details: dict) -> None:
        run_dir = self.output_root / run_id
        lock = self.locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            events_path = run_dir / "events.json"
            events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
            now = datetime.now(UTC).isoformat()
            event = {
                "sequence": len(events) + 1,
                "run_id": run_id,
                "status": run_status,
                "occurred_at": now,
                "details": details,
            }
            events.append(event)
            write_json(events_path, events)
            status_path = run_dir / "run_status.json"
            current = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            write_json(
                status_path,
                {
                    **current,
                    "run_id": run_id,
                    "status": run_status,
                    "record_type": "assistant_council_candidate",
                    "promotion_status": "unconfirmed",
                    "automatic_promotion_supported": False,
                    "updated_at": now,
                    "details": details,
                },
            )

    def get_run(self, run_id: str) -> dict:
        run_dir = self.run_dir(run_id)
        status_payload = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
        candidate_path = run_dir / "candidate_record.json"
        error_path = run_dir / "run_error.json"
        return {
            "run_id": run_id,
            "status": status_payload["status"],
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "automatic_promotion_supported": False,
            "final_result": json.loads(candidate_path.read_text(encoding="utf-8")) if candidate_path.exists() else None,
            "error": json.loads(error_path.read_text(encoding="utf-8")) if error_path.exists() else status_payload.get("details", {}).get("error"),
        }

    def get_events(self, run_id: str, after: int = 0) -> dict:
        run_dir = self.run_dir(run_id)
        events_path = run_dir / "events.json"
        events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
        selected = [event for event in events if event["sequence"] > after]
        current_status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))["status"]
        return {
            "run_id": run_id,
            "events": selected,
            "next_after": events[-1]["sequence"] if events else after,
            "terminal": current_status in TERMINAL_STATES,
            "poll_after_ms": 500,
        }


class GuildlessRunManager:
    def __init__(
        self,
        settings: Settings,
        *,
        output_boundary: Path = COUNCIL_ROOT,
        orchestrator_factory: Callable[[Settings], GuildlessOrchestrator] | None = None,
    ):
        self.settings = settings
        self.output_boundary = output_boundary
        self.output_root = validate_output_root(settings.output_dir, output_boundary)
        self.orchestrator_factory = orchestrator_factory
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"guildless_[A-Za-z0-9_-]{1,100}", run_id):
            raise KeyError(run_id)
        path = self.output_root / run_id
        if not path.is_dir():
            raise KeyError(run_id)
        return path

    async def create(self, request: GuildlessRunRequest) -> CouncilRunAccepted:
        run_id = "guildless_" + uuid.uuid4().hex
        run_dir = self.output_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        self.locks[run_id] = asyncio.Lock()
        write_json(
            run_dir / "api_request.json",
            {
                **request.model_dump(mode="json"),
                "record_type": "assistant_council_candidate",
                "promotion_status": "unconfirmed",
                "automatic_external_actions": False,
            },
        )
        await self._record_event(run_id, "queued", {"message": "guildless run accepted"})
        task = asyncio.create_task(self._execute(run_id, request), name=run_id)
        self.tasks[run_id] = task
        task.add_done_callback(lambda _task, key=run_id: self.tasks.pop(key, None))
        return CouncilRunAccepted(
            run_id=run_id,
            status="queued",
            run_url=f"/v1/guildless/runs/{run_id}",
            events_url=f"/v1/guildless/runs/{run_id}/events",
        )

    async def _execute(self, run_id: str, request: GuildlessRunRequest) -> None:
        orchestrator = (
            self.orchestrator_factory(self.settings)
            if self.orchestrator_factory
            else GuildlessOrchestrator(self.settings, output_boundary=self.output_boundary)
        )

        async def emit(run_status: str, details: dict) -> None:
            await self._record_event(run_id, run_status, details)

        try:
            await orchestrator.run(
                goal=request.goal,
                github_queries=request.github_queries,
                context=request.context,
                constraints=request.constraints,
                allowed_providers=list(request.allowed_providers),
                max_rounds=request.max_rounds,
                confidence_threshold=request.confidence_threshold,
                output_dir=self.output_root,
                run_id=run_id,
                event_callback=emit,
            )
        except Exception as exc:
            await self._record_event(
                run_id,
                "failed",
                {"error": f"{type(exc).__name__}: {str(exc)[:500]}"},
            )
        finally:
            await orchestrator.aclose()

    async def _record_event(self, run_id: str, run_status: str, details: dict) -> None:
        run_dir = self.output_root / run_id
        lock = self.locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            events_path = run_dir / "events.json"
            events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
            now = datetime.now(UTC).isoformat()
            events.append(
                {
                    "sequence": len(events) + 1,
                    "run_id": run_id,
                    "status": run_status,
                    "occurred_at": now,
                    "details": details,
                }
            )
            write_json(events_path, events)
            status_path = run_dir / "run_status.json"
            current = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            write_json(
                status_path,
                {
                    **current,
                    "run_id": run_id,
                    "status": run_status,
                    "record_type": "assistant_council_candidate",
                    "promotion_status": "unconfirmed",
                    "automatic_external_actions": False,
                    "updated_at": now,
                    "details": details,
                },
            )

    def get_run(self, run_id: str) -> dict:
        run_dir = self.run_dir(run_id)
        status_payload = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
        candidate_path = run_dir / "candidate_record.json"
        error_path = run_dir / "run_error.json"
        return {
            "run_id": run_id,
            "status": status_payload["status"],
            "record_type": "assistant_council_candidate",
            "promotion_status": "unconfirmed",
            "automatic_external_actions": False,
            "final_result": json.loads(candidate_path.read_text(encoding="utf-8")) if candidate_path.exists() else None,
            "error": json.loads(error_path.read_text(encoding="utf-8")) if error_path.exists() else status_payload.get("details", {}).get("error"),
        }

    def get_events(self, run_id: str, after: int = 0) -> dict:
        run_dir = self.run_dir(run_id)
        events_path = run_dir / "events.json"
        events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
        selected = [event for event in events if event["sequence"] > after]
        current_status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))["status"]
        return {
            "run_id": run_id,
            "events": selected,
            "next_after": events[-1]["sequence"] if events else after,
            "terminal": current_status in TERMINAL_STATES,
            "poll_after_ms": 500,
        }


class GuildlessJobManager:
    def __init__(self, settings: Settings, *, output_boundary: Path = COUNCIL_ROOT):
        self.settings = settings
        self.output_boundary = output_boundary
        self.output_root = validate_output_root(settings.output_dir, output_boundary)
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"job_[A-Za-z0-9_-]{1,100}", job_id):
            raise KeyError(job_id)
        path = self.output_root / job_id
        if not path.is_dir():
            raise KeyError(job_id)
        return path

    async def create(self, request: GuildlessJobRequest) -> CouncilRunAccepted:
        job_id = f"job_{request.workspace_label}_{uuid.uuid4().hex}"
        job_dir = self.output_root / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        self.locks[job_id] = asyncio.Lock()
        write_json(job_dir / "api_request.json", request.model_dump(mode="json"))
        await self._record_event(job_id, "queued", {"message": "autonomous job accepted"})
        task = asyncio.create_task(self._execute(job_id, request), name=job_id)
        self.tasks[job_id] = task
        task.add_done_callback(lambda _task, key=job_id: self.tasks.pop(key, None))
        return CouncilRunAccepted(
            run_id=job_id,
            status="queued",
            run_url=f"/v1/guildless/jobs/{job_id}",
            events_url=f"/v1/guildless/jobs/{job_id}/events",
        )

    async def _execute(self, job_id: str, request: GuildlessJobRequest) -> None:
        runner = GuildlessAutonomousRunner(
            self.settings, output_boundary=self.output_boundary
        )

        async def emit(job_status: str, details: dict) -> None:
            await self._record_event(job_id, job_status, details)

        try:
            await runner.run(request, job_id=job_id, event_callback=emit)
        except Exception as exc:
            await self._record_event(
                job_id, "failed", {"error": f"{type(exc).__name__}: {str(exc)[:500]}"}
            )

    async def _record_event(self, job_id: str, job_status: str, details: dict) -> None:
        job_dir = self.output_root / job_id
        lock = self.locks.setdefault(job_id, asyncio.Lock())
        async with lock:
            events_path = job_dir / "events.json"
            events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
            now = datetime.now(UTC).isoformat()
            events.append(
                {
                    "sequence": len(events) + 1,
                    "job_id": job_id,
                    "status": job_status,
                    "occurred_at": now,
                    "details": details,
                }
            )
            write_json(events_path, events)
            write_json(
                job_dir / "job_status.json",
                {
                    "job_id": job_id,
                    "status": job_status,
                    "updated_at": now,
                    "external_actions_performed": False,
                    "details": details,
                },
            )

    def get_job(self, job_id: str) -> dict:
        job_dir = self.job_dir(job_id)
        result_path = job_dir / "job_result.json"
        status_path = job_dir / "job_status.json"
        result = _load_json(result_path) if result_path.exists() else None
        job_status = (
            _load_json(status_path)
            if status_path.exists()
            else {"status": result.get("status", "queued") if result else "queued"}
        )
        audit_path = job_dir / "execution_audit.json"
        return {
            "job_id": job_id,
            "status": job_status["status"],
            "result": result,
            "execution_audit": _load_json(audit_path) if audit_path.exists() else None,
            "external_actions_performed": False,
        }

    def list_jobs(self, limit: int = 20) -> dict:
        jobs: list[dict] = []
        directories = sorted(
            (
                path
                for path in self.output_root.glob("job_*")
                if path.is_dir() and re.fullmatch(r"job_[A-Za-z0-9_-]{1,100}", path.name)
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for job_dir in directories[:limit]:
            result_path = job_dir / "job_result.json"
            status_path = job_dir / "job_status.json"
            request_path = (
                job_dir / "job_request.json"
                if (job_dir / "job_request.json").exists()
                else job_dir / "api_request.json"
            )
            result = _load_json(result_path) if result_path.exists() else {}
            status_payload = _load_json(status_path) if status_path.exists() else {}
            request = _load_json(request_path) if request_path.exists() else {}
            report = result.get("execution_report") or {}
            verification = result.get("verification") or {}
            repository = result.get("selected_repository") or {}
            jobs.append(
                {
                    "job_id": job_dir.name,
                    "status": status_payload.get("status", result.get("status", "queued")),
                    "objective": result.get("objective", request.get("objective", "目的を取得中")),
                    "updated_at": status_payload.get(
                        "updated_at", datetime.fromtimestamp(job_dir.stat().st_mtime, UTC).isoformat()
                    ),
                    "repository": repository.get("full_name"),
                    "summary": report.get("summary"),
                    "passed_test_count": verification.get("passed_test_count", 0),
                    "output_file_count": verification.get("output_file_count", 0),
                    "external_actions_performed": False,
                    "approval_required": verification.get("approval_required", False),
                }
            )
        return {"jobs": jobs, "count": len(jobs)}

    def get_events(self, job_id: str, after: int = 0) -> dict:
        job_dir = self.job_dir(job_id)
        events_path = job_dir / "events.json"
        events = _load_json_list(events_path) if events_path.exists() else []
        selected = [event for event in events if event["sequence"] > after]
        status_path = job_dir / "job_status.json"
        result_path = job_dir / "job_result.json"
        current = (
            _load_json(status_path)["status"]
            if status_path.exists()
            else _load_json(result_path).get("status", "queued")
            if result_path.exists()
            else "queued"
        )
        return {
            "job_id": job_id,
            "events": selected,
            "next_after": events[-1]["sequence"] if events else after,
            "terminal": current in TERMINAL_STATES,
            "poll_after_ms": 500,
        }

    def get_council(self, job_id: str) -> dict:
        job_dir = self.job_dir(job_id)
        result_path = job_dir / "job_result.json"
        if not result_path.exists():
            return {"job_id": job_id, "available": False, "message": "Council result is not available yet."}
        result = _load_json(result_path)
        raw_analysis_dir = result.get("analysis_run_dir")
        if not raw_analysis_dir:
            return {"job_id": job_id, "available": False, "message": "No Council run is linked to this job."}
        analysis_dir = Path(raw_analysis_dir).resolve()
        output_root = self.output_root.resolve()
        if output_root not in analysis_dir.parents or not analysis_dir.name.startswith("guildless_"):
            raise ValueError("analysis run is outside the Guildless run boundary")

        def optional_json(name: str, default):
            path = analysis_dir / name
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

        return {
            "job_id": job_id,
            "available": True,
            "run_id": analysis_dir.name,
            "decision": optional_json("final_decision.json", None),
            "proposals": optional_json("proposals.json", []),
            "criticism": optional_json("criticism_round_1.json", {}),
            "rebuttals": optional_json("rebuttals_round_1.json", []),
            "promotion_status": "unconfirmed",
            "confirmed_decision_created": bool(result.get("confirmed_decision_created", False)),
        }

    def get_artifacts(self, job_id: str) -> dict:
        job_dir = self.job_dir(job_id)
        result_path = job_dir / "job_result.json"
        if not result_path.exists():
            return {"job_id": job_id, "artifacts": [], "count": 0}
        result = _load_json(result_path)
        workspace_value = result.get("workspace")
        workspace = Path(workspace_value).resolve() if workspace_value else WORKSPACE_ROOT / job_id
        expected_workspace = (WORKSPACE_ROOT / job_id).resolve()
        if workspace != expected_workspace or WORKSPACE_ROOT not in workspace.parents:
            raise ValueError("workspace is outside the Guildless workspace boundary")
        output_root = (workspace / "output").resolve()
        declared = (result.get("execution_report") or {}).get("artifacts") or []
        artifacts: list[dict] = []
        for declared_path in declared:
            relative = str(declared_path).replace("\\", "/")
            if not relative.startswith("output/") or ".." in Path(relative).parts:
                continue
            candidate = (workspace / relative).resolve()
            if output_root != candidate and output_root not in candidate.parents:
                continue
            if not candidate.is_file():
                artifacts.append({"path": relative, "exists": False, "size": 0, "sha256": None, "preview": None})
                continue
            content = candidate.read_bytes()
            preview = None
            if candidate.suffix.lower() in PREVIEWABLE_SUFFIXES and len(content) <= 200_000:
                preview = content.decode("utf-8", errors="replace")
            artifacts.append(
                {
                    "path": relative,
                    "exists": True,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "preview": preview,
                }
            )
        return {"job_id": job_id, "artifacts": artifacts, "count": len(artifacts)}

    def get_audit(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        result = job.get("result") or {}
        return {
            "job_id": job_id,
            "status": job["status"],
            "events": self.get_events(job_id).get("events", []),
            "execution": job.get("execution_audit"),
            "verification": result.get("verification"),
            "external_actions_performed": False,
            "confirmed_decision_created": bool(result.get("confirmed_decision_created", False)),
        }


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def _load_json_list(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"expected array in {path}")
    return value


def create_app(
    settings: Settings | None = None,
    *,
    output_boundary: Path = COUNCIL_ROOT,
    orchestrator_factory: Callable[[Settings], CouncilOrchestrator] | None = None,
    guildless_orchestrator_factory: Callable[[Settings], GuildlessOrchestrator] | None = None,
    voice_transcriber: Any | None = None,
    sales_registry: SalesOssRegistry | None = None,
) -> FastAPI:
    app = FastAPI(title="Council Service", version="1.0.0")
    app.mount("/ui-assets", StaticFiles(directory=UI_ROOT), name="guildless-ui-assets")
    manager = CouncilRunManager(
        settings or Settings.load(),
        output_boundary=output_boundary,
        orchestrator_factory=orchestrator_factory,
    )
    app.state.council_manager = manager
    guildless_manager = GuildlessRunManager(
        settings or manager.settings,
        output_boundary=output_boundary,
        orchestrator_factory=guildless_orchestrator_factory,
    )
    app.state.guildless_manager = guildless_manager
    job_manager = GuildlessJobManager(settings or manager.settings, output_boundary=output_boundary)
    app.state.guildless_job_manager = job_manager
    app.state.voice_transcriber = voice_transcriber or LocalWhisperTranscriber()
    app.state.sales_registry = sales_registry or SalesOssRegistry()

    @app.get("/", include_in_schema=False)
    @app.get("/guildless", include_in_schema=False)
    async def guildless_ui() -> FileResponse:
        return FileResponse(UI_ROOT / "index.html")

    @app.get("/v1/sales/overview")
    async def sales_overview() -> dict[str, Any]:
        try:
            return app.state.sales_registry.overview()
        except SalesOssError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/sales/score")
    async def sales_score(request: SalesLeadScoreRequest) -> dict[str, Any]:
        try:
            return app.state.sales_registry.score_lead(request.model_dump(mode="json"))
        except SalesOssError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/audio/transcriptions/status")
    async def transcription_status() -> dict:
        return app.state.voice_transcriber.status()

    @app.post("/v1/audio/transcriptions")
    async def transcribe_audio(
        file: UploadFile = File(...),
        language: str = Form("ja"),
    ) -> dict:
        content_type = (file.content_type or "application/octet-stream").split(";", 1)[0]
        if content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(status_code=415, detail=f"unsupported audio type: {content_type}")
        payload = await file.read(MAX_AUDIO_BYTES + 1)
        await file.close()
        if not payload:
            raise HTTPException(status_code=400, detail="audio file is empty")
        if len(payload) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="audio file exceeds 25 MB")

        suffix = Path(file.filename or "voice.webm").suffix.lower()
        if suffix not in {".webm", ".ogg", ".wav", ".mp3", ".mp4", ".m4a"}:
            suffix = ".webm"
        runtime_dir = (manager.settings.runtime_dir or (COUNCIL_ROOT / ".runtime")).resolve()
        audio_dir = runtime_dir / "voice_uploads"
        audio_dir.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=audio_dir, suffix=suffix, delete=False) as handle:
                handle.write(payload)
                temp_path = Path(handle.name)
            result = await asyncio.to_thread(
                app.state.voice_transcriber.transcribe_file,
                temp_path,
                language=language.strip() or None,
            )
            if not result.get("text"):
                raise HTTPException(status_code=422, detail="speech was not detected")
            return result
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"local transcription failed: {type(exc).__name__}: {str(exc)[:300]}",
            ) from None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @app.post(
        "/v1/council/runs",
        response_model=CouncilRunAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_run(request: CouncilRunRequest) -> CouncilRunAccepted:
        return await manager.create(request)

    @app.get("/v1/council/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        try:
            return manager.get_run(run_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="run not found") from None

    @app.get("/v1/council/runs/{run_id}/events")
    async def get_events(run_id: str, after: int = Query(0, ge=0)) -> dict:
        try:
            return manager.get_events(run_id, after)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="run not found") from None

    @app.post(
        "/v1/guildless/runs",
        response_model=CouncilRunAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_guildless_run(request: GuildlessRunRequest) -> CouncilRunAccepted:
        return await guildless_manager.create(request)

    @app.get("/v1/guildless/runs/{run_id}")
    async def get_guildless_run(run_id: str) -> dict:
        try:
            return guildless_manager.get_run(run_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="run not found") from None

    @app.get("/v1/guildless/runs/{run_id}/events")
    async def get_guildless_events(run_id: str, after: int = Query(0, ge=0)) -> dict:
        try:
            return guildless_manager.get_events(run_id, after)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="run not found") from None

    @app.post(
        "/v1/guildless/jobs",
        response_model=CouncilRunAccepted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_guildless_job(request: GuildlessJobRequest) -> CouncilRunAccepted:
        return await job_manager.create(request)

    @app.get("/v1/guildless/jobs")
    async def list_guildless_jobs(limit: int = Query(20, ge=1, le=100)) -> dict:
        return job_manager.list_jobs(limit)

    @app.get("/v1/guildless/jobs/{job_id}")
    async def get_guildless_job(job_id: str) -> dict:
        try:
            return job_manager.get_job(job_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="job not found") from None

    @app.get("/v1/guildless/jobs/{job_id}/events")
    async def get_guildless_job_events(job_id: str, after: int = Query(0, ge=0)) -> dict:
        try:
            return job_manager.get_events(job_id, after)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="job not found") from None

    @app.get("/v1/guildless/jobs/{job_id}/council")
    async def get_guildless_job_council(job_id: str) -> dict:
        try:
            return job_manager.get_council(job_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.get("/v1/guildless/jobs/{job_id}/artifacts")
    async def get_guildless_job_artifacts(job_id: str) -> dict:
        try:
            return job_manager.get_artifacts(job_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @app.get("/v1/guildless/jobs/{job_id}/audit")
    async def get_guildless_job_audit(job_id: str) -> dict:
        try:
            return job_manager.get_audit(job_id)
        except (KeyError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="job not found") from None

    return app


app = create_app()
