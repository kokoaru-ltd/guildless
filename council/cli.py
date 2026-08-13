from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from council.autonomous import GuildlessAutonomousRunner
from council.config import Settings
from council.guildless import GuildlessOrchestrator
from council.orchestrator import CouncilOrchestrator, ROLES, VALID_MODES, default_provider_factory
from council.providers.base import ProviderUnavailable
from council.schemas import GitHubSelectionConstraints, GuildlessJobRequest
from council.security import ContextPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="council", description="Blind multi-LLM advisory council")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Run one bounded council session")
    ask.add_argument("--mode", choices=sorted(VALID_MODES), default="fast")
    ask.add_argument("--task", "--task-type", dest="task_type", choices=sorted(ROLES), required=True)
    ask.add_argument("--question", required=True)
    ask.add_argument("--context", action="append", default=[], metavar="PATH")
    ask.add_argument("--allowed-provider", action="append", choices=("claude", "deepseek", "codex", "sakana"))
    ask.add_argument("--output-dir", type=Path)

    subparsers.add_parser("doctor", help="Check CLI/subscription/local availability without generating")
    serve = subparsers.add_parser("serve", help="Run the asynchronous HTTP Council Service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8780)
    solve = subparsers.add_parser(
        "solve",
        help="Run the Guildless MVP: GitHub research, independent specialists, criticism, rebuttal, Judge",
    )
    solve.add_argument("--goal", required=True)
    solve.add_argument("--github-query", action="append", required=True)
    solve.add_argument("--context", action="append", default=[], metavar="PATH")
    solve.add_argument(
        "--allowed-provider",
        action="append",
        required=True,
        choices=("claude", "deepseek", "codex", "sakana"),
    )
    solve.add_argument("--license", action="append", dest="licenses")
    solve.add_argument("--min-stars", type=int, default=0)
    solve.add_argument("--max-candidates", type=int, default=10)
    solve.add_argument("--max-rounds", type=int, choices=(1, 2, 3), default=3)
    solve.add_argument("--output-dir", type=Path)
    job = subparsers.add_parser(
        "job",
        help="Give Guildless one objective and let it research, select, implement, test, and verify",
    )
    job.add_argument("--objective", required=True)
    job.add_argument("--github-query", action="append", required=True)
    job.add_argument("--context", action="append", default=[], metavar="PATH")
    job.add_argument(
        "--allowed-provider",
        action="append",
        required=True,
        choices=("claude", "deepseek", "codex", "sakana"),
    )
    job.add_argument("--license", action="append", dest="licenses")
    job.add_argument("--min-stars", type=int, default=0)
    job.add_argument("--max-candidates", type=int, default=10)
    job.add_argument("--max-rounds", type=int, choices=(1, 2, 3), default=1)
    job.add_argument("--workspace-label", default="job")
    job.add_argument("--max-execution-minutes", type=int, default=20)
    resume = subparsers.add_parser(
        "execute-from-run",
        help="Let Guildless implement and verify from a completed Guildless analysis run",
    )
    resume.add_argument("--analysis-run", type=Path, required=True)
    resume.add_argument("--objective", required=True)
    resume.add_argument("--workspace-label", default="resume")
    resume.add_argument("--max-execution-minutes", type=int, default=20)
    return parser


async def _run_ask(args: argparse.Namespace, settings: Settings) -> int:
    orchestrator = CouncilOrchestrator(settings)
    try:
        result = await orchestrator.ask(
            question=args.question,
            task_type=args.task_type,
            mode=args.mode,
            context_paths=args.context,
            allowed_providers=args.allowed_provider,
            output_dir=args.output_dir.resolve() if args.output_dir else None,
        )
    finally:
        await orchestrator.aclose()
    print(json.dumps(result.final_decision, ensure_ascii=False, indent=2))
    print(f"\nArtifacts: {result.run_dir}")
    print("Pay-as-you-go API fallback: disabled")
    return 0


async def _doctor(settings: Settings) -> int:
    providers = default_provider_factory(settings)
    runtime = settings.runtime_dir or Path.cwd() / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "providers": {},
        "output_dir": str(settings.output_dir),
        "forbidden_roots_enforced": [r"D:\guildless_sim", r"D:\founder_memory"],
        "automatic_api_fallback": False,
        "automatic_confirmation": False,
    }
    try:
        claude = providers["claude"]
        try:
            await claude._verify_subscription(runtime / "doctor-claude")  # type: ignore[attr-defined]
            report["providers"]["claude"] = {  # type: ignore[index]
                "available": True,
                "auth": "claude.ai subscription",
                "model": settings.providers["claude"].model,
            }
        except ProviderUnavailable as exc:
            report["providers"]["claude"] = exc.audit_dict("doctor")  # type: ignore[index]

        codex = providers["codex"]
        try:
            warning = await codex._verify_subscription(runtime / "doctor-codex")  # type: ignore[attr-defined]
            report["providers"]["codex"] = {  # type: ignore[index]
                "available": True,
                "auth": "ChatGPT subscription",
                "model": settings.providers["codex"].model,
                "warning": warning or None,
            }
        except ProviderUnavailable as exc:
            report["providers"]["codex"] = exc.audit_dict("doctor")  # type: ignore[index]

        deepseek = providers["deepseek"]
        try:
            response = await deepseek.client.get(settings.providers["deepseek"].base_url + "/api/tags")
            response.raise_for_status()
            models = {item.get("name") for item in response.json().get("models", [])}
            model = settings.providers["deepseek"].model
            report["providers"]["deepseek"] = {  # type: ignore[index]
                "available": model in models,
                "transport": "Ollama localhost",
                "model": model,
                "reason": None if model in models else "model_not_installed",
            }
        except Exception as exc:
            report["providers"]["deepseek"] = {  # type: ignore[index]
                "available": False,
                "transport": "Ollama localhost",
                "model": settings.providers["deepseek"].model,
                "reason": "ollama_unavailable",
                "message": f"{type(exc).__name__}: {str(exc)[:300]}",
            }

        report["providers"]["sakana"] = {  # type: ignore[index]
            "available": bool(settings.providers["sakana"].api_key),
            "auth": "Sakana subscription key",
            "model": settings.providers["sakana"].model,
            "optional_judge_fallback": True,
        }
    finally:
        await asyncio.gather(*(provider.aclose() for provider in providers.values()))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    required = ("claude", "codex", "deepseek")
    okay = all(bool(report["providers"][name].get("available")) for name in required)  # type: ignore[index]
    return 0 if okay else 2


async def _run_solve(args: argparse.Namespace, settings: Settings) -> int:
    context_documents = ContextPolicy(settings.max_context_bytes).read_explicit(args.context)
    context = {
        "documents": [
            {
                "source_path": item.source_path,
                "sha256": item.sha256,
                "content": item.content,
            }
            for item in context_documents
        ]
    }
    constraints = GitHubSelectionConstraints(
        license_allowlist=args.licenses
        or ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"],
        min_stars=args.min_stars,
        max_candidates=args.max_candidates,
    )
    orchestrator = GuildlessOrchestrator(settings)
    try:
        result = await orchestrator.run(
            goal=args.goal,
            github_queries=args.github_query,
            context=context,
            constraints=constraints,
            allowed_providers=args.allowed_provider,
            max_rounds=args.max_rounds,
            output_dir=args.output_dir.resolve() if args.output_dir else None,
        )
    finally:
        await orchestrator.aclose()
    print(json.dumps(result.final_decision, ensure_ascii=False, indent=2))
    print(f"\nArtifacts: {result.run_dir}")
    print("External actions: disabled")
    return 0


def _context_payload(paths: list[str], settings: Settings) -> dict:
    documents = ContextPolicy(settings.max_context_bytes).read_explicit(paths)
    return {
        "documents": [
            {
                "source_path": item.source_path,
                "sha256": item.sha256,
                "content": item.content,
            }
            for item in documents
        ]
    }


async def _run_job(args: argparse.Namespace, settings: Settings) -> int:
    request = GuildlessJobRequest(
        objective=args.objective,
        github_queries=args.github_query,
        context=_context_payload(args.context, settings),
        constraints=GitHubSelectionConstraints(
            license_allowlist=args.licenses
            or ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"],
            min_stars=args.min_stars,
            max_candidates=args.max_candidates,
        ),
        allowed_providers=args.allowed_provider,
        workspace_label=args.workspace_label,
        max_rounds=args.max_rounds,
        max_execution_minutes=args.max_execution_minutes,
    )
    runner = GuildlessAutonomousRunner(settings)
    result = await runner.run(request)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nWorkspace: {result.get('workspace', 'not created')}")
    print("External actions: disabled unless separately approved")
    return 0 if result["status"] in {"completed", "awaiting_approval"} else 2


async def _run_execute_from_run(args: argparse.Namespace, settings: Settings) -> int:
    runner = GuildlessAutonomousRunner(settings)
    result = await runner.execute_from_analysis(
        analysis_run_dir=args.analysis_run,
        objective=args.objective,
        workspace_label=args.workspace_label,
        max_execution_minutes=args.max_execution_minutes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nWorkspace: {result.get('workspace', 'not created')}")
    print("External actions: disabled unless separately approved")
    return 0 if result["status"] in {"completed", "awaiting_approval"} else 2


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = build_parser().parse_args(argv)
    settings = Settings.load()
    if args.command == "doctor":
        raise SystemExit(asyncio.run(_doctor(settings)))
    if args.command == "ask":
        raise SystemExit(asyncio.run(_run_ask(args, settings)))
    if args.command == "serve":
        import uvicorn

        uvicorn.run("council.api:app", host=args.host, port=args.port, reload=False)
        return
    if args.command == "solve":
        raise SystemExit(asyncio.run(_run_solve(args, settings)))
    if args.command == "job":
        raise SystemExit(asyncio.run(_run_job(args, settings)))
    if args.command == "execute-from-run":
        raise SystemExit(asyncio.run(_run_execute_from_run(args, settings)))
    raise SystemExit(2)
