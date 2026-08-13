from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from council.api import create_app
from council.config import ProviderConfig, Settings


class FakeTranscriber:
    def status(self) -> dict:
        return {"available": True, "engine": "fake", "local_only": True}

    def transcribe_file(self, audio_path: Path, *, language: str | None = "ja") -> dict:
        assert audio_path.read_bytes() == b"RIFF-fake-audio"
        return {
            "text": "音声入力のテストです",
            "language": language,
            "segments": [],
            "model": "fake",
            "device": "cpu",
            "local_only": True,
        }


def make_voice_app(tmp_path: Path):
    providers = {"deepseek": ProviderConfig("deepseek", "test", billing_mode="local")}
    settings = Settings(providers, tmp_path / "runs", 5, 0, 100_000, tmp_path / ".runtime", 3)
    return create_app(settings, output_boundary=tmp_path, voice_transcriber=FakeTranscriber())


@pytest.mark.asyncio
async def test_local_transcription_endpoint(tmp_path: Path) -> None:
    app = make_voice_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            files={"file": ("voice.wav", b"RIFF-fake-audio", "audio/wav")},
            data={"language": "ja"},
        )
        assert response.status_code == 200
        assert response.json()["text"] == "音声入力のテストです"
        assert response.json()["local_only"] is True
        assert not list((tmp_path / ".runtime" / "voice_uploads").glob("*"))


@pytest.mark.asyncio
async def test_transcription_rejects_non_audio(tmp_path: Path) -> None:
    app = make_voice_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            files={"file": ("payload.txt", b"not audio", "text/plain")},
        )
        assert response.status_code == 415
