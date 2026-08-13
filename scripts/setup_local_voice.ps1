$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$sourceRoot = Join-Path $projectRoot "third_party\faster-whisper"
$commit = "65882eee9f5cdbeeb2d877f1131d48cf241b327d"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment was not found: $python"
}

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    New-Item -ItemType Directory -Path (Split-Path $sourceRoot) -Force | Out-Null
    git clone https://github.com/SYSTRAN/faster-whisper.git $sourceRoot
}

if (Test-Path -LiteralPath (Join-Path $sourceRoot ".git")) {
    git -C $sourceRoot fetch --depth 1 origin $commit
    git -C $sourceRoot checkout --detach $commit
}
& $python -m pip install -e $sourceRoot "python-multipart>=0.0.20,<1"

Write-Host "Local voice engine ready. Source commit: $commit"
Write-Host "The first transcription downloads the configured Whisper model once."
