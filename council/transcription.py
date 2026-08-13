from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any


class LocalWhisperTranscriber:
    """Lazy, local-only speech-to-text using the vendored faster-whisper OSS."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        device: str | None = None,
        model_cache_dir: Path | None = None,
    ) -> None:
        self.model_name = model_name or os.getenv("GUILDLESS_WHISPER_MODEL", "small")
        self.requested_device = device or os.getenv("GUILDLESS_WHISPER_DEVICE", "auto")
        self.model_cache_dir = model_cache_dir or Path(
            os.getenv(
                "GUILDLESS_WHISPER_MODEL_DIR",
                str(Path(__file__).resolve().parent.parent / ".runtime" / "whisper_models"),
            )
        ).resolve()
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self._model: Any | None = None
        self._device = "unloaded"
        self._compute_type = "unloaded"
        self._fallback_reason: str | None = None
        self._load_lock = threading.Lock()
        self._transcribe_lock = threading.Lock()

    def _cuda_is_visible(self) -> bool:
        try:
            import ctranslate2

            if os.name == "nt":
                import ctypes

                # CTranslate2 can see the GPU while the runtime DLLs needed at
                # first inference are still missing. Check them up front so
                # auto mode falls back before a user records anything.
                for dll_name in ("cublas64_12.dll", "cudnn64_9.dll"):
                    ctypes.WinDLL(dll_name)

            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model

            from faster_whisper import WhisperModel

            wants_cuda = self.requested_device == "cuda" or (
                self.requested_device == "auto" and self._cuda_is_visible()
            )
            if wants_cuda:
                try:
                    self._model = WhisperModel(
                        self.model_name,
                        device="cuda",
                        compute_type="float16",
                        download_root=str(self.model_cache_dir),
                    )
                    self._device = "cuda"
                    self._compute_type = "float16"
                    return self._model
                except Exception as exc:
                    if self.requested_device == "cuda":
                        raise
                    self._fallback_reason = f"{type(exc).__name__}: {str(exc)[:240]}"

            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
                download_root=str(self.model_cache_dir),
                cpu_threads=max(1, min(8, os.cpu_count() or 4)),
            )
            self._device = "cpu"
            self._compute_type = "int8"
            return self._model

    def transcribe_file(self, audio_path: Path, *, language: str | None = "ja") -> dict[str, Any]:
        started = time.perf_counter()
        with self._transcribe_lock:
            model = self._load()
            segments_iter, info = model.transcribe(
                str(audio_path),
                language=language or None,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=True,
            )
            segments = [
                {
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "text": segment.text.strip(),
                }
                for segment in segments_iter
                if segment.text.strip()
            ]

        return {
            "text": "".join(segment["text"] for segment in segments).strip(),
            "language": getattr(info, "language", language or "unknown"),
            "language_probability": round(float(getattr(info, "language_probability", 0.0)), 6),
            "duration_seconds": round(float(getattr(info, "duration", 0.0)), 3),
            "segments": segments,
            "model": self.model_name,
            "device": self._device,
            "compute_type": self._compute_type,
            "latency_seconds": round(time.perf_counter() - started, 3),
            "local_only": True,
            "fallback_reason": self._fallback_reason,
        }

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "engine": "SYSTRAN/faster-whisper",
            "version": "1.2.1",
            "source_commit": "65882eee9f5cdbeeb2d877f1131d48cf241b327d",
            "model": self.model_name,
            "requested_device": self.requested_device,
            "loaded_device": self._device,
            "compute_type": self._compute_type,
            "local_only": True,
        }
