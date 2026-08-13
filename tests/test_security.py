from pathlib import Path

import pytest

from council.security import ContextPolicy, ContextSecurityError, validate_output_root


@pytest.mark.parametrize(
    "path",
    [
        r"D:\guildless_sim\context.md",
        r"D:\guildless_simulated\..\guildless_sim\context.md",
        r"D:\founder_memory\raw.sqlite",
        r"D:\founder_memory\approved.md",
    ],
)
def test_forbidden_roots_rejected_before_access(path: str):
    with pytest.raises(ContextSecurityError):
        ContextPolicy(1000).read_explicit([path])


def test_only_explicit_utf8_text_is_read(tmp_path: Path):
    allowed = tmp_path / "context.md"
    allowed.write_text("approved context", encoding="utf-8")
    docs = ContextPolicy(1000).read_explicit([str(allowed)])
    assert docs[0].content == "approved context"

    blocked = tmp_path / "raw.sqlite"
    blocked.write_bytes(b"sqlite")
    with pytest.raises(ContextSecurityError):
        ContextPolicy(1000).read_explicit([str(blocked)])


def test_output_is_confined_to_boundary(tmp_path: Path):
    boundary = tmp_path / "council"
    boundary.mkdir()
    assert validate_output_root(boundary / "runs", boundary) == boundary / "runs"
    with pytest.raises(ContextSecurityError):
        validate_output_root(tmp_path / "outside", boundary)
    with pytest.raises(ContextSecurityError):
        validate_output_root(Path(r"D:\founder_memory\council-output"), boundary)
