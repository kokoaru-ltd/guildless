<#
Brings the runtime up and opens the control centre.

Idempotent by design. Double-clicking twice must not produce two runtimes
writing to the same ledger, so an existing healthy process is reused rather
than replaced.
#>
param(
  [int]$Port = 8780,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$home_dir = Split-Path -Parent $PSScriptRoot
$python = Join-Path $home_dir '.venv\Scripts\python.exe'
$logOut = Join-Path $home_dir 'runs\runtime.log'
$logErr = Join-Path $home_dir 'runs\runtime.err.log'
$url = "http://127.0.0.1:$Port/"

New-Item -ItemType Directory -Force (Join-Path $home_dir 'runs') | Out-Null

function Test-Runtime {
  try {
    $null = Invoke-RestMethod ($url + 'v1/outcome') -TimeoutSec 4
    return $true
  } catch { return $false }
}

if (Test-Runtime) {
  Write-Host "Guildless: 既に稼働中です ($url)"
} else {
  # A process on the port that does not answer /v1/outcome is a stale runtime
  # from a previous crash. Clearing it is safe; leaving it means the port is
  # held and nothing works.
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*council*serve*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

  Write-Host "Guildless: 実行エンジンを起動しています..."
  Start-Process -FilePath $python `
    -ArgumentList @('-m','council','serve','--host','127.0.0.1','--port',"$Port") `
    -WorkingDirectory $home_dir `
    -RedirectStandardOutput $logOut -RedirectStandardError $logErr `
    -WindowStyle Hidden | Out-Null

  $ready = $false
  foreach ($attempt in 1..30) {
    Start-Sleep -Milliseconds 700
    if (Test-Runtime) { $ready = $true; break }
  }
  if (-not $ready) {
    Write-Host "Guildless: 起動できませんでした。直近のログ:"
    if (Test-Path $logErr) { Get-Content $logErr -Tail 15 }
    Read-Host "Enterで終了"
    exit 1
  }
  Write-Host "Guildless: 稼働中"
}

$raw = Invoke-WebRequest ($url + 'v1/outcome') -UseBasicParsing -TimeoutSec 10
$state = [System.Text.Encoding]::UTF8.GetString($raw.RawContentStream.ToArray()) | ConvertFrom-Json
Write-Host ""
Write-Host ("  実際に増えた金   " + ('¥{0:N0}' -f $state.verified_net_outcome_yen))
Write-Host ("  状態             " + $state.status)
Write-Host ("  いまの作業       " + $state.current_action)
Write-Host ("  止まっている理由 " + $state.bottleneck)
if ($state.human_required.Count -gt 0) {
  Write-Host ""
  Write-Host "  あなたの操作が必要です:" -ForegroundColor Yellow
  foreach ($task in $state.human_required) { Write-Host ("    - " + $task.title) }
}
Write-Host ""

if (-not $NoBrowser) { Start-Process $url }
Write-Host "画面: $url"
Write-Host "停止: scripts\stop-guildless.ps1"
