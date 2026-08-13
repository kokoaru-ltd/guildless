param(
    [int]$Port = 8780,
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendRoot = Join-Path $projectRoot "frontend"

Set-Location $projectRoot
$env:PAPERCLIP_TELEMETRY_DISABLED = "1"
$env:DO_NOT_TRACK = "1"

if (Test-Path -LiteralPath (Join-Path $projectRoot ".gitmodules")) {
    # Only initialize the four pinned top-level packs. SalesGPT contains an
    # obsolete nested submodule entry that is unrelated to Guildless.
    git -C $projectRoot submodule update --init
    if ($LASTEXITCODE -ne 0) {
        throw "Sales and marketing OSS setup failed. Check Git access and run the script again."
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python 3.11+ was not found. Install Python and run this script again."
    }
    & $pythonCommand.Source -m venv .venv
}

if (-not $SkipInstall) {
    & $venvPython -m pip install -e ".[dev]"
    Push-Location $frontendRoot
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
            npm ci
        }
        npm run build
    }
    finally {
        Pop-Location
    }
}

$server = Start-Process -FilePath $venvPython -ArgumentList @(
    "-m", "council", "serve", "--host", "127.0.0.1", "--port", $Port
) -WorkingDirectory $projectRoot -NoNewWindow -PassThru

try {
    $url = "http://127.0.0.1:$Port/guildless"
    $ready = $false
    foreach ($attempt in 1..40) {
        if ($server.HasExited) {
            throw "Guildless stopped before it became ready. Exit code: $($server.ExitCode)"
        }
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw "Guildless startup timed out: $url"
    }
    Write-Host "Guildless is ready: $url" -ForegroundColor Green
    if ($SmokeTest) {
        Write-Host "Smoke test passed." -ForegroundColor Green
        return
    }
    if (-not $NoBrowser) {
        Start-Process $url
    }
    Wait-Process -Id $server.Id
}
finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id
    }
}
