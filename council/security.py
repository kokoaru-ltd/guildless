from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN_ROOTS = (
    Path(r"D:\guildless_sim"),
    Path(r"D:\founder_memory"),
)
COUNCIL_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".tsv"}


class ContextSecurityError(ValueError):
    pass


def _normalized(path: Path) -> str:
    return str(path).replace("/", "\\").rstrip("\\").casefold()


def _is_within(path: Path, root: Path) -> bool:
    candidate = _normalized(path)
    forbidden = _normalized(root)
    return candidate == forbidden or candidate.startswith(forbidden + "\\")


def _reject_forbidden(path: Path) -> None:
    if any(_is_within(path, root) for root in FORBIDDEN_ROOTS):
        raise ContextSecurityError(f"Forbidden context root: {path}")


def validate_output_root(path: Path, boundary: Path = COUNCIL_ROOT) -> Path:
    """Resolve output without creating it and keep all writes inside the council boundary."""
    requested = Path(os.path.abspath(path))
    _reject_forbidden(requested)
    resolved = requested.resolve(strict=False)
    _reject_forbidden(resolved)
    resolved_boundary = boundary.resolve(strict=True)
    if not _is_within(resolved, resolved_boundary):
        raise ContextSecurityError(
            f"Council output must stay inside {resolved_boundary}: {resolved}"
        )
    return resolved


@dataclass(frozen=True)
class ContextDocument:
    source_path: str
    sha256: str
    size_bytes: int
    content: str


class ContextPolicy:
    def __init__(self, max_total_bytes: int):
        self.max_total_bytes = max_total_bytes

    def read_explicit(self, paths: list[str]) -> list[ContextDocument]:
        documents: list[ContextDocument] = []
        total = 0
        for raw_path in paths:
            requested = Path(os.path.abspath(Path(raw_path).expanduser()))
            _reject_forbidden(requested)
            if requested.suffix.casefold() not in ALLOWED_EXTENSIONS:
                raise ContextSecurityError(f"Context must be an approved UTF-8 text file: {requested}")
            if not requested.exists():
                raise ContextSecurityError(f"Context file does not exist: {requested}")
            if not requested.is_file():
                raise ContextSecurityError(f"Context path is not a file: {requested}")
            resolved = requested.resolve(strict=True)
            _reject_forbidden(resolved)
            data = resolved.read_bytes()
            total += len(data)
            if total > self.max_total_bytes:
                raise ContextSecurityError(
                    f"Explicit context exceeds {self.max_total_bytes} bytes in total"
                )
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ContextSecurityError(f"Context is not UTF-8 text: {resolved}") from exc
            documents.append(
                ContextDocument(
                    source_path=str(resolved),
                    sha256=hashlib.sha256(data).hexdigest(),
                    size_bytes=len(data),
                    content=content,
                )
            )
        return documents

    def read_inline(self, context: dict) -> list[ContextDocument]:
        """Accept only the JSON object supplied by the caller; never dereference values as paths."""
        data = json.dumps(
            context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(data) > self.max_total_bytes:
            raise ContextSecurityError(
                f"Inline context exceeds {self.max_total_bytes} bytes in total"
            )
        return [
            ContextDocument(
                source_path="inline:request.context",
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                content=data.decode("utf-8"),
            )
        ]
