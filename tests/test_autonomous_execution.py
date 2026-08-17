from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import httpx

from council.action_executor import (
    CodexActionExecutor,
    MaterializedRepository,
    WorkspacePolicy,
    prohibited_commands,
    tree_sha256,
    verify_execution,
)
from council.api import create_app
from council.cli import build_parser
from council.execution_runtime import ExecutionRuntimeValidator, detect_runtimes
from council.schemas import (
    ExecutionReport,
    ExecutionTestResult,
    GuildlessJobRequest,
    ImplementationBundle,
)


def test_workspace_policy_creates_isolated_output(tmp_path: Path) -> None:
    policy = WorkspacePolicy(tmp_path / "workspaces")
    workspace = policy.create("job_test_123")
    assert workspace.parent == (tmp_path / "workspaces").resolve()
    assert (workspace / "output").is_dir()
    assert (workspace / ".guildless").is_dir()
    with pytest.raises(FileExistsError):
        policy.create("job_test_123")


def test_workspace_policy_rejects_bad_job_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        WorkspacePolicy(tmp_path).create("../escape")


def test_prohibited_command_detection_reads_command_fields_only() -> None:
    events = "\n".join(
        [
            json.dumps({"type": "item", "command": "pytest -q"}),
            json.dumps({"type": "item", "command": "git push origin main"}),
            json.dumps({"message": "Never run git push; this is prompt text only."}),
        ]
    )
    assert prohibited_commands(events) == ["git push origin main"]


def test_verifier_requires_unchanged_source_real_output_and_passed_test(tmp_path: Path) -> None:
    workspace = tmp_path / "job"
    source = workspace / "source_repo"
    output = workspace / "output"
    source.mkdir(parents=True)
    output.mkdir()
    (source / "LICENSE").write_text("MIT", encoding="utf-8")
    (output / "prototype.py").write_text("print('ok')", encoding="utf-8")
    before = tree_sha256(source)
    repository = MaterializedRepository("owner/repo", "a" * 40, source, before)
    report = ExecutionReport(
        status="completed",
        summary="implemented",
        implementation_directory="output",
        changed_files=["output/prototype.py"],
        artifacts=["output/prototype.py"],
        tests=[ExecutionTestResult(command="python output/prototype.py", passed=True, summary="ok")],
        blockers=[],
        approval_requests=[],
        next_action="review",
    )
    result = verify_execution(
        workspace=workspace,
        repository=repository,
        report=report,
        audit={"prohibited_commands": []},
    )
    assert result["accepted"] is True
    assert result["source_unchanged"] is True
    assert result["external_actions_performed"] is False


def test_verifier_rejects_source_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "job"
    source = workspace / "source_repo"
    output = workspace / "output"
    source.mkdir(parents=True)
    output.mkdir()
    (source / "a.txt").write_text("before", encoding="utf-8")
    before = tree_sha256(source)
    (source / "a.txt").write_text("after", encoding="utf-8")
    (output / "x.txt").write_text("x", encoding="utf-8")
    report = ExecutionReport(
        status="completed",
        summary="done",
        implementation_directory="output",
        changed_files=["output/x.txt"],
        artifacts=["output/x.txt"],
        tests=[ExecutionTestResult(command="test", passed=True, summary="passed")],
        blockers=[],
        approval_requests=[],
        next_action="none",
    )
    result = verify_execution(
        workspace=workspace,
        repository=MaterializedRepository("owner/repo", "b" * 40, source, before),
        report=report,
        audit={"prohibited_commands": []},
    )
    assert result["accepted"] is False
    assert result["source_unchanged"] is False


def test_job_contract_and_cli_expose_one_instruction_flow() -> None:
    request = GuildlessJobRequest(
        objective="Select an OSS base and build a tested local prototype",
        github_queries=["multi agent council python"],
        allowed_providers=["claude", "codex"],
    )
    assert request.max_rounds == 1
    parser = build_parser()
    args = parser.parse_args(
        [
            "job",
            "--objective",
            request.objective,
            "--github-query",
            request.github_queries[0],
            "--allowed-provider",
            "claude",
            "--allowed-provider",
            "codex",
        ]
    )
    assert args.command == "job"


@pytest.mark.asyncio
async def test_host_applies_bundle_only_to_output_and_runs_allowlisted_tests(tmp_path: Path) -> None:
    workspace = tmp_path / "job"
    (workspace / "output").mkdir(parents=True)
    bundle = ImplementationBundle.model_validate(
        {
            "summary": "tiny package",
            "files": [
                {"relative_path": "output/value.py", "content": "VALUE = 42\n"},
                {
                    "relative_path": "output/tests/test_value.py",
                    "content": (
                        "import unittest\n"
                        "from value import VALUE\n"
                        "class T(unittest.TestCase):\n"
                        "    def test_value(self): self.assertEqual(VALUE, 42)\n"
                    ),
                },
            ],
            "test_strategy": "unittest",
            "approval_requests": [],
        }
    )
    CodexActionExecutor._apply_bundle(workspace, bundle)
    results, feedback = await CodexActionExecutor._run_validation(workspace)
    assert all(item.passed for item in results)
    assert feedback == ""


def test_host_rejects_bundle_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "job"
    (workspace / "output").mkdir(parents=True)
    bundle = ImplementationBundle.model_validate(
        {
            "summary": "escape",
            "files": [{"relative_path": "output/../outside.py", "content": "x = 1\n"}],
            "test_strategy": "none",
            "approval_requests": [],
        }
    )
    with pytest.raises(ValueError, match="escaped output"):
        CodexActionExecutor._apply_bundle(workspace, bundle)
    assert not (workspace / "outside.py").exists()


def test_api_exposes_autonomous_job_endpoints(tmp_path: Path) -> None:
    from council.config import Settings

    settings = Settings.load()
    settings = Settings(
        providers=settings.providers,
        output_dir=tmp_path / "runs",
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
        max_context_bytes=settings.max_context_bytes,
        runtime_dir=tmp_path / "runtime",
        local_repetitions=settings.local_repetitions,
    )
    app = create_app(settings, output_boundary=tmp_path)
    routes = {route.path for route in app.routes}
    assert "/v1/guildless/jobs" in routes
    assert "/v1/guildless/jobs/{job_id}" in routes
    assert "/v1/guildless/jobs/{job_id}/events" in routes


@pytest.mark.asyncio
async def test_ui_and_job_history_include_cli_completed_job(tmp_path: Path) -> None:
    from council.config import Settings

    settings = Settings.load()
    runs = tmp_path / "runs"
    job_dir = runs / "job_ui_fixture_123"
    job_dir.mkdir(parents=True)
    (job_dir / "job_result.json").write_text(
        json.dumps(
            {
                "job_id": job_dir.name,
                "status": "completed",
                "objective": "TypeScriptの試作品を作る",
                "external_actions_performed": False,
                "selected_repository": {"full_name": "owner/repo"},
                "execution_report": {"summary": "完了"},
                "verification": {"passed_test_count": 2, "output_file_count": 4},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    configured = Settings(
        providers=settings.providers,
        output_dir=runs,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
        max_context_bytes=settings.max_context_bytes,
        runtime_dir=tmp_path / "runtime",
        local_repetitions=settings.local_repetitions,
    )
    app = create_app(configured, output_boundary=tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get("/guildless")
        assert page.status_code == 200
        assert "Guildless — AI企業運営OS" in page.text
        script_path = re.search(r'src="([^"]+\.js)"', page.text).group(1)
        script = await client.get(script_path)
        assert script.status_code == 200
        # The bundle must carry the control tower's own wording. Asserting on
        # the served bundle rather than the source is what catches a UI that
        # builds but is never actually shipped -- which has happened here: an
        # installed build once served a bundle whose source no longer existed.
        #
        # Pinned to the sidebar destinations rather than a phrase inside one
        # screen. Copy inside a screen is meant to change; the set of places
        # the product has is the thing that should not change quietly.
        for destination in ("Overview", "Business", "Revenue", "Assets", "Activity"):
            assert destination in script.text
        assert "GUILDLESS" in script.text
        history = (await client.get("/v1/guildless/jobs")).json()
        assert history["jobs"][0]["objective"] == "TypeScriptの試作品を作る"
        detail = (await client.get(f"/v1/guildless/jobs/{job_dir.name}")).json()
        assert detail["status"] == "completed"
        council = (await client.get(f"/v1/guildless/jobs/{job_dir.name}/council")).json()
        assert council["available"] is False
        artifacts = (await client.get(f"/v1/guildless/jobs/{job_dir.name}/artifacts")).json()
        assert artifacts == {"job_id": job_dir.name, "artifacts": [], "count": 0}
        audit = (await client.get(f"/v1/guildless/jobs/{job_dir.name}/audit")).json()
        assert audit["external_actions_performed"] is False


@pytest.mark.asyncio
async def test_typescript_runtime_detects_checks_and_runs_node_tests(tmp_path: Path) -> None:
    output = tmp_path / "output"
    (output / "src").mkdir(parents=True)
    (output / "tests").mkdir()
    (output / "package.json").write_text(
        json.dumps(
            {
                "name": "guildless-typescript-fixture",
                "private": True,
                "type": "module",
                "scripts": {"test": "node -e process.exit(99)"},
            }
        ),
        encoding="utf-8",
    )
    (output / "src" / "sum.ts").write_text(
        "export function sum(a: number, b: number): number { return a + b; }\n",
        encoding="utf-8",
    )
    (output / "tests" / "sum.test.ts").write_text(
        (
            "import test from 'node:test';\n"
            "import assert from 'node:assert/strict';\n"
            "import { sum } from '../src/sum.ts';\n"
            "test('sum', () => assert.equal(sum(20, 22), 42));\n"
        ),
        encoding="utf-8",
    )
    detection = detect_runtimes(output)
    assert detection.names == ["typescript"]
    results, feedback = await ExecutionRuntimeValidator().validate(output)
    assert results
    assert all(item.passed for item in results), feedback
    assert any("--test" in item.command for item in results)
    assert all("process.exit(99)" not in item.command for item in results)


@pytest.mark.asyncio
async def test_typescript_dependencies_require_offline_lockfile(tmp_path: Path) -> None:
    output = tmp_path / "output"
    (output / "tests").mkdir(parents=True)
    (output / "package.json").write_text(
        json.dumps(
            {
                "name": "locked-only",
                "private": True,
                "type": "module",
                "dependencies": {"left-pad": "1.3.0"},
            }
        ),
        encoding="utf-8",
    )
    (output / "tests" / "safe.test.ts").write_text(
        "import test from 'node:test'; test('safe', () => {});\n",
        encoding="utf-8",
    )
    results, feedback = await ExecutionRuntimeValidator().validate(output)
    assert any(not item.passed for item in results)
    assert "no supported lockfile" in feedback
