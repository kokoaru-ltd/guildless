# Guildless local voice input

Guildless voice input does not use the browser Web Speech API. The browser
records WebM/Opus audio with `MediaRecorder`, sends it to the same local
Guildless server, and the server transcribes it with a pinned GitHub checkout
of `SYSTRAN/faster-whisper`.

## Fixed OSS source

- Repository: https://github.com/SYSTRAN/faster-whisper
- Release: v1.2.1
- Commit: `65882eee9f5cdbeeb2d877f1131d48cf241b327d`
- License: MIT
- Local checkout: `third_party/faster-whisper`

## Set up from a fresh Guildless checkout

```powershell
cd D:\guildless_council
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_voice.ps1
```

The setup script clones faster-whisper when absent, checks out the exact
commit, and installs that checkout in editable mode. It does not silently
replace it with another project.

## Start Guildless

```powershell
cd D:\guildless_council
.\.venv\Scripts\python.exe -m uvicorn council.api:app --host 127.0.0.1 --port 8780
```

Open `http://127.0.0.1:8780/guildless`, press **音声で話す**, allow the
microphone, speak, and press **録音を止める**. Text is inserted into the
composer but is not sent automatically.

## Local processing boundary

1. The browser captures audio locally.
2. Audio is posted only to the same Guildless origin.
3. The server stores it in a temporary runtime file.
4. faster-whisper transcribes it locally.
5. The temporary audio file is deleted in a `finally` block.
6. Only the resulting text is returned to the composer.

Maximum recording duration in the UI is 60 seconds. The API rejects uploads
over 25 MB and non-audio content types.

## Model and GPU

Defaults:

```dotenv
GUILDLESS_WHISPER_MODEL=small
GUILDLESS_WHISPER_DEVICE=auto
```

On Windows, CUDA mode requires both CUDA 12 cuBLAS and cuDNN 9 runtime DLLs.
Auto mode checks those DLLs before loading a CUDA model and falls back to CPU
`int8` when they are unavailable. Set `GUILDLESS_WHISPER_DEVICE=cuda` only
after the required runtime is installed and on PATH.

The model is downloaded once into `.runtime/whisper_models`; subsequent
transcriptions use the local copy.
