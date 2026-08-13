from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from council.schemas import ExecutionTestResult


IGNORED_PARTS = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}


@dataclass(frozen=True)
class RuntimeDetection:
    python: bool
    typescript: bool

    @property
    def names(self) -> list[str]:
        names: list[str] = []
        if self.python:
            names.append("python")
        if self.typescript:
            names.append("typescript")
        return names


def _source_files(root: Path, suffixes: set[str]) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.suffix.casefold() in suffixes
        and not any(part in IGNORED_PARTS for part in path.relative_to(root).parts)
    ]


def detect_runtimes(output: Path) -> RuntimeDetection:
    python_files = _source_files(output, {".py"})
    type_files = _source_files(output, {".ts", ".tsx", ".mts", ".cts"})
    return RuntimeDetection(
        python=bool(python_files or (output / "pyproject.toml").is_file()),
        typescript=bool(
            type_files
            or (output / "tsconfig.json").is_file()
            or (output / "package.json").is_file()
        ),
    )


def _executable(name: str) -> str | None:
    if os.name == "nt":
        return shutil.which(name + ".cmd") or shutil.which(name)
    return shutil.which(name)


class ExecutionRuntimeValidator:
    """Runs only fixed, non-publishing validation commands selected by code."""

    def __init__(self, timeout_seconds: float = 120.0):
        self.timeout_seconds = timeout_seconds

    async def validate(self, output: Path) -> tuple[list[ExecutionTestResult], str]:
        detection = detect_runtimes(output)
        results: list[ExecutionTestResult] = []
        if detection.python:
            results.extend(await self._validate_python(output))
        if detection.typescript:
            results.extend(await self._validate_typescript(output))
        if not detection.names:
            results.append(
                ExecutionTestResult(
                    command="runtime-detect",
                    passed=False,
                    summary="No supported Python or TypeScript project was detected.",
                )
            )
        failures = [item.summary for item in results if not item.passed]
        return results, "\n\n".join(failures)

    async def _validate_python(self, output: Path) -> list[ExecutionTestResult]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(output)
        results = [
            await self._run(
                [sys.executable, "-m", "compileall", "-q", str(output)],
                cwd=output,
                env=env,
            )
        ]
        tests_dir = output / "tests"
        python_tests = _source_files(tests_dir, {".py"}) if tests_dir.is_dir() else []
        if python_tests:
            result = await self._run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir), "-v"],
                cwd=output,
                env=env,
            )
            match = re.search(r"Ran\s+(\d+)\s+tests?", result.summary)
            if not match or int(match.group(1)) < 1:
                result = ExecutionTestResult(
                    command=result.command,
                    passed=False,
                    summary=result.summary + "\nNo Python tests were executed.",
                )
            results.append(result)
        else:
            results.append(
                ExecutionTestResult(
                    command="python -m unittest discover",
                    passed=False,
                    summary="Python project has no tests under output/tests.",
                )
            )
        return results

    async def _validate_typescript(self, output: Path) -> list[ExecutionTestResult]:
        node = _executable("node")
        if not node:
            return [
                ExecutionTestResult(
                    command="node --version",
                    passed=False,
                    summary="Node.js is not installed.",
                )
            ]
        results: list[ExecutionTestResult] = []
        package = self._package_json(output)
        dependency_count = sum(
            len(package.get(key, {}) or {})
            for key in ("dependencies", "devDependencies", "optionalDependencies")
        )
        if dependency_count and not (output / "node_modules").is_dir():
            results.append(await self._offline_install(output))
            if not results[-1].passed:
                return results

        source_files = [
            path
            for path in _source_files(output, {".ts", ".tsx", ".mts", ".cts"})
            if "tests" not in path.relative_to(output).parts
            and not path.name.endswith((".test.ts", ".spec.ts", ".test.mts", ".spec.mts"))
        ]
        tsc = self._local_binary(output, "tsc")
        if tsc:
            results.append(await self._run([tsc, "--noEmit"], cwd=output))
        else:
            tsx = [path for path in source_files if path.suffix.casefold() == ".tsx"]
            if tsx:
                results.append(
                    ExecutionTestResult(
                        command="typescript syntax validation",
                        passed=False,
                        summary="TSX requires a locked local TypeScript compiler; none was available.",
                    )
                )
            elif source_files:
                for path in source_files:
                    results.append(
                        await self._run(
                            [node, "--experimental-strip-types", "--check", str(path)],
                            cwd=output,
                        )
                    )

        tests = [
            path
            for path in _source_files(output / "tests", {".ts", ".mts", ".cts", ".js", ".mjs", ".cjs"})
            if ".test." in path.name or ".spec." in path.name or path.name.startswith("test")
        ] if (output / "tests").is_dir() else []
        if not tests:
            results.append(
                ExecutionTestResult(
                    command="node --test",
                    passed=False,
                    summary="TypeScript project has no tests under output/tests.",
                )
            )
            return results
        test_result = await self._run(
            [node, "--experimental-strip-types", "--test", *[str(path) for path in tests]],
            cwd=output,
        )
        match = re.search(r"(?:^|\s)tests\s+(\d+)", test_result.summary, re.MULTILINE)
        if not match or int(match.group(1)) < 1:
            test_result = ExecutionTestResult(
                command=test_result.command,
                passed=False,
                summary=test_result.summary + "\nNo TypeScript tests were executed.",
            )
        results.append(test_result)
        return results

    @staticmethod
    def _package_json(output: Path) -> dict:
        path = output / "package.json"
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("package.json must contain an object")
        return value

    async def _offline_install(self, output: Path) -> ExecutionTestResult:
        env = os.environ.copy()
        env.update(
            {
                "npm_config_ignore_scripts": "true",
                "npm_config_audit": "false",
                "npm_config_fund": "false",
                "NO_UPDATE_NOTIFIER": "1",
            }
        )
        if (output / "pnpm-lock.yaml").is_file():
            pnpm = _executable("pnpm")
            if pnpm:
                return await self._run(
                    [pnpm, "install", "--offline", "--frozen-lockfile", "--ignore-scripts"],
                    cwd=output,
                    env=env,
                )
        if (output / "package-lock.json").is_file():
            npm = _executable("npm")
            if npm:
                return await self._run(
                    [npm, "ci", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"],
                    cwd=output,
                    env=env,
                )
        return ExecutionTestResult(
            command="dependency-install --offline --ignore-scripts",
            passed=False,
            summary=(
                "Dependencies are declared but no supported lockfile/offline package manager is "
                "available. Network installation and lifecycle scripts are forbidden."
            ),
        )

    @staticmethod
    def _local_binary(output: Path, name: str) -> str | None:
        suffix = ".cmd" if os.name == "nt" else ""
        path = output / "node_modules" / ".bin" / f"{name}{suffix}"
        return str(path) if path.is_file() else None

    async def _run(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> ExecutionTestResult:
        display_command = " ".join(command)
        resolved_command = list(command)
        if os.name == "nt" and Path(command[0]).suffix.casefold() in {".cmd", ".bat"}:
            resolved_command = [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/s",
                "/c",
                *command,
            ]
        try:
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
            text = (stdout + stderr).decode("utf-8", errors="replace")
            return ExecutionTestResult(
                command=display_command,
                passed=process.returncode == 0,
                summary=text[-3000:] or f"exit code {process.returncode}",
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return ExecutionTestResult(
                command=display_command,
                passed=False,
                summary=f"Validation timed out after {self.timeout_seconds:g} seconds.",
            )
        except OSError as exc:
            return ExecutionTestResult(
                command=display_command,
                passed=False,
                summary=f"Validation command could not start: {type(exc).__name__}: {exc}",
            )
