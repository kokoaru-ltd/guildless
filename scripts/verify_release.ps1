$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Run scripts\start_guildless.ps1 once before release verification."
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm run build
}
finally {
    Pop-Location
}

Push-Location $projectRoot
try {
    & $python -m pytest -q
}
finally {
    Pop-Location
}
