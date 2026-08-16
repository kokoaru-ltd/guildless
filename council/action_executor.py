from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from council.providers.openai import OpenAIProvider, _extract_codex_usage, _subscription_env
from council.execution_runtime import ExecutionRuntimeValidator, detect_runtimes
from council.schemas import (
    ExecutionReport,
    ExecutionTestResult,
    ImplementationBundle,
    strict_json_schema,
)
from council.storage import write_json


DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspaces"
FORBIDDEN_ROOTS = (Path(r"D:\guildless_sim"), Path(r"D:\founder_memory"))
IGNORED_HASH_PARTS = {".git", "node_modules", ".venv", "__pycache__"}
PROHIBITED_COMMAND_PATTERNS = (
    re.compile(r"(?:^|\s)git\s+push(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|\s)gh\s+pr\s+create(?:\s|$)", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:curl|wget|scp|ssh)(?:\.exe)?(?:\s|$)", re.IGNORECASE),
    re.compile(r"Invoke-(?:WebRequest|RestMethod)", re.IGNORECASE),
    re.compile(r"(?:railway\s+up|vercel\s+(?:deploy|--prod)|npm\s+publish)", re.IGNORECASE),
)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root)
        if any(part in IGNORED_HASH_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            digest.update(b"L\0")
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(os.readlink(path).encode("utf-8", errors="replace"))
        elif path.is_file():
            digest.update(b"F\0")
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def _command_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in {"command", "cmd", "shell_command"} and isinstance(child, str):
                found.append(child)
            else:
                found.extend(_command_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_command_strings(child))
    return found


def prohibited_commands(events_jsonl: str) -> list[str]:
    violations: list[str] = []
    for line in events_jsonl.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for command in _command_strings(event):
            if any(pattern.search(command) for pattern in PROHIBITED_COMMAND_PATTERNS):
                violations.append(command[:500])
    return violations


@dataclass(frozen=True)
class MaterializedRepository:
    full_name: str
    commit_sha: str
    source_dir: Path
    source_hash_before: str


class WorkspacePolicy:
    def __init__(self, root: Path = DEFAULT_WORKSPACE_ROOT):
        self.root = root.resolve()
        if any(_inside(self.root, forbidden) or _inside(forbidden, self.root) for forbidden in FORBIDDEN_ROOTS):
            raise ValueError("workspace root overlaps a forbidden data root")

    def create(self, job_id: str) -> Path:
        if not re.fullmatch(r"job_[A-Za-z0-9_-]{1,100}", job_id):
            raise ValueError("invalid job_id")
        self.root.mkdir(parents=True, exist_ok=True)
        workspace = (self.root / job_id).resolve()
        if not _inside(workspace, self.root):
            raise ValueError("workspace escaped the configured root")
        workspace.mkdir(parents=False, exist_ok=False)
        (workspace / "output").mkdir()
        (workspace / ".guildless").mkdir()
        return workspace


class GitRepositoryMaterializer:
    async def materialize(
        self,
        *,
        full_name: str,
        commit_sha: str,
        workspace: Path,
        timeout_seconds: float = 180.0,
    ) -> MaterializedRepository:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name):
            raise ValueError("invalid GitHub repository name")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", commit_sha):
            raise ValueError("an exact 40-character commit SHA is required")
        source_dir = workspace / "source_repo"
        url = f"https://github.com/{full_name}.git"
        await self._run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", url, str(source_dir)],
            cwd=workspace,
            timeout_seconds=timeout_seconds,
        )
        await self._run(
            ["git", "checkout", "--detach", commit_sha.lower()],
            cwd=source_dir,
            timeout_seconds=timeout_seconds,
        )
        resolved = await self._run(
            ["git", "rev-parse", "HEAD"], cwd=source_dir, timeout_seconds=30.0
        )
        if resolved.strip().casefold() != commit_sha.casefold():
            raise RuntimeError("checked out commit does not match the selected snapshot")
        # Codex anchors workspace-write to the detected repository root.  Make
        # the job workspace the outer repository so output/ stays writable;
        # source_repo remains a nested, hash-verified upstream snapshot.
        await self._run(["git", "init"], cwd=workspace, timeout_seconds=30.0)
        return MaterializedRepository(
            full_name=full_name,
            commit_sha=commit_sha.lower(),
            source_dir=source_dir,
            source_hash_before=tree_sha256(source_dir),
        )

    async def _run(
        self, command: list[str], *, cwd: Path, timeout_seconds: float
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError(f"command timed out: {command[0]}") from None
        if process.returncode:
            detail = stderr.decode("utf-8", errors="replace")[-1500:]
            raise RuntimeError(f"command failed ({command[0]}): {detail}")
        return stdout.decode("utf-8", errors="replace")


class CodexActionExecutor:
    """Uses a read-only model to design files; the host applies and tests them."""

    def __init__(self, provider: OpenAIProvider):
        self.provider = provider

    async def execute(
        self,
        *,
        objective: str,
        selected_repository: dict[str, Any],
        council_decision: dict[str, Any],
        workspace: Path,
        max_execution_minutes: int,
        event_callback: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> tuple[ExecutionReport, dict[str, Any]]:
        meta_dir = workspace / ".guildless"
        schema_path = meta_dir / "implementation-bundle.schema.json"
        events_path = meta_dir / "codex-events.jsonl"
        write_json(schema_path, strict_json_schema(ImplementationBundle))
        await self.provider._verify_subscription(meta_dir / "auth")
        if event_callback:
            await event_callback(
                "implementing",
                {"workspace": str(workspace), "executor": "codex-read-only-plus-host-applier"},
            )
        original_timeout = self.provider.timeout_seconds
        self.provider.timeout_seconds = max_execution_minutes * 60
        all_events: list[str] = []
        usage_total = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
        }
        usage_available = True
        total_latency_ms = 0
        bundle: ImplementationBundle | None = None
        test_results: list[ExecutionTestResult] = []
        try:
            feedback = ""
            for attempt in range(1, 3):
                prompt = self._prompt(
                    objective, selected_repository, council_decision, feedback=feedback
                )
                output_path = meta_dir / f"implementation-bundle-{attempt}.json"
                result = await self._call_bundle(
                    prompt=prompt,
                    schema_path=schema_path,
                    output_path=output_path,
                    workspace=workspace,
                )
                all_events.append(result.stdout)
                total_latency_ms += result.latency_ms
                usage, available = _extract_codex_usage(result.stdout)
                usage_available = usage_available and available
                for key in usage_total:
                    usage_total[key] += usage.get(key, 0)
                bundle = ImplementationBundle.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
                self._apply_bundle(workspace, bundle)
                test_results, feedback = await self._run_validation(workspace)
                if all(item.passed for item in test_results):
                    break
        finally:
            self.provider.timeout_seconds = original_timeout
        joined_events = "\n".join(all_events)
        events_path.write_text(joined_events, encoding="utf-8", newline="\n")
        if bundle is None:
            raise RuntimeError("Action Agent did not produce an implementation bundle")
        output_files = sorted(
            path.relative_to(workspace).as_posix()
            for path in (workspace / "output").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        tests_passed = bool(test_results) and all(item.passed for item in test_results)
        report = ExecutionReport(
            status="completed" if tests_passed else "partial",
            summary=bundle.summary,
            implementation_directory="output",
            changed_files=output_files,
            artifacts=output_files,
            tests=test_results,
            blockers=[] if tests_passed else ["Generated implementation did not pass host validation."],
            approval_requests=bundle.approval_requests,
            next_action="Human review before any external publication or deployment.",
        )
        audit = {
            "executor": "codex-read-only-plus-host-applier",
            "billing_mode": "subscription",
            "sandbox": "read-only",
            "network_permission_granted": False,
            "dangerous_bypass_used": False,
            "host_write_scope": "output/** only",
            "detected_runtimes": detect_runtimes(workspace / "output").names,
            "host_test_allowlist": [
                "python -m compileall",
                "python -m unittest discover",
                "node --experimental-strip-types --check",
                "node --experimental-strip-types --test",
                "local tsc --noEmit",
                "pnpm install --offline --frozen-lockfile --ignore-scripts",
                "npm ci --offline --ignore-scripts",
            ],
            "latency_ms": total_latency_ms,
            "usage": usage_total,
            "usage_available": usage_available,
            "exit_code": 0,
            "prohibited_commands": prohibited_commands(joined_events),
        }
        return report, audit

    async def _call_bundle(
        self, *, prompt: str, schema_path: Path, output_path: Path, workspace: Path
    ):
        command = [
            self.provider.config.command or "codex",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-C",
            str(workspace),
        ]
        if self.provider.config.model and self.provider.config.model != "default":
            command.extend(("--model", self.provider.config.model))
        command.append("-")
        started = time.perf_counter()
        result = await self.provider._run_process(
            command, stdin=prompt, cwd=workspace, env=_subscription_env()
        )
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        self.provider._ensure_process_success(result)
        if not output_path.is_file():
            raise RuntimeError("Action Agent did not produce an implementation bundle")
        return result

    @staticmethod
    def _apply_bundle(workspace: Path, bundle: ImplementationBundle) -> None:
        output_root = (workspace / "output").resolve()
        seen: set[str] = set()
        total_bytes = 0
        for item in bundle.files:
            if item.relative_path in seen:
                raise ValueError(f"duplicate implementation path: {item.relative_path}")
            seen.add(item.relative_path)
            target = (workspace / item.relative_path).resolve()
            if not _inside(target, output_root):
                raise ValueError(f"implementation path escaped output/: {item.relative_path}")
            encoded = item.content.encode("utf-8")
            total_bytes += len(encoded)
            if total_bytes > 2_000_000:
                raise ValueError("implementation bundle exceeds 2 MB")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.content, encoding="utf-8", newline="\n")

    @staticmethod
    async def _run_validation(workspace: Path) -> tuple[list[ExecutionTestResult], str]:
        return await ExecutionRuntimeValidator().validate(workspace / "output")

    @staticmethod
    def _prompt(
        objective: str,
        selected_repository: dict[str, Any],
        council_decision: dict[str, Any],
        *,
        feedback: str = "",
    ) -> str:
        repair = (
            f"\nHOST TEST FAILURE FROM THE PREVIOUS BUNDLE:\n{feedback}\n"
            "Read the current output files and return a complete corrected replacement bundle.\n"
            if feedback
            else ""
        )
        return f"""You are the Action Agent inside Guildless. Execute the objective, do not merely advise.

OBJECTIVE:
{objective}

SELECTED OSS SNAPSHOT:
{json.dumps(selected_repository, ensure_ascii=False, sort_keys=True)}

COUNCIL DECISION (advisory, not automatically confirmed):
{json.dumps(council_decision, ensure_ascii=False, sort_keys=True)}

Workspace contract:
- Read source_repo/ as the exact selected upstream snapshot. You are in a read-only sandbox.
- Return a complete ImplementationBundle. The trusted host, not you, writes files under output/.
- Every relative_path must start with output/. Use forward slashes.
- Choose Python or TypeScript from the objective and inspected OSS; TypeScript is fully allowed.
- For Python, include stdlib unittest tests under output/tests.
- For TypeScript, prefer a dependency-free Node 24 project and node:test files under output/tests.
- If TypeScript dependencies are unavoidable, include an exact pnpm-lock.yaml or package-lock.json.
- The host never executes package.json scripts. It may install locked packages offline with lifecycle scripts disabled.
- Inspect the actual source and license before reusing code. Preserve required notices in output/.
- Implement the smallest working prototype that satisfies the objective.
- Do not access D:\\guildless_sim, D:\\founder_memory, OneDrive, customer data, or credentials.
- Do not use network tools or contact external services after the supplied repository is cloned.
- Never push, publish, deploy, send email/messages, create a PR, make payments/contracts, or delete outside output/.
- If an external effect is required, record it in approval_requests and stop before performing it.
- Do not claim tests ran. The trusted host detects the runtime and runs fixed Python or TypeScript validators.
- Finish by returning only the required structured ImplementationBundle.
{repair}
"""


def verify_execution(
    *, workspace: Path, repository: MaterializedRepository, report: ExecutionReport, audit: dict[str, Any]
) -> dict[str, Any]:
    source_hash_after = tree_sha256(repository.source_dir)
    source_unchanged = source_hash_after == repository.source_hash_before
    output_root = (workspace / "output").resolve()
    output_files = [path for path in output_root.rglob("*") if path.is_file()]
    invalid_artifacts: list[str] = []
    for claimed in [*report.changed_files, *report.artifacts]:
        target = (workspace / claimed).resolve()
        if not _inside(target, output_root) or not target.is_file():
            invalid_artifacts.append(claimed)
    passed_tests = sum(1 for test in report.tests if test.passed)
    violations = list(audit.get("prohibited_commands", []))
    accepted = bool(
        source_unchanged
        and output_files
        and not invalid_artifacts
        and not violations
        and report.status == "completed"
        and passed_tests > 0
    )
    return {
        "accepted": accepted,
        "source_hash_before": repository.source_hash_before,
        "source_hash_after": source_hash_after,
        "source_unchanged": source_unchanged,
        "output_file_count": len(output_files),
        "invalid_artifact_claims": invalid_artifacts,
        "prohibited_commands": violations,
        "passed_test_count": passed_tests,
        "external_actions_performed": False,
        "approval_required": bool(report.approval_requests),
    }
