<#
Stops the runtime.

Deliberately separate from closing the window. A control centre that shuts the
company down when its window closes would end a run mid-flight, and a run that
has money reserved needs to reach a settled state rather than vanish.
#>
$ErrorActionPreference = 'SilentlyContinue'

$stopped = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*council*serve*' } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
    $stopped++
  }

if ($stopped -gt 0) {
  Write-Host "Guildless: 停止しました（$stopped プロセス）"
} else {
  Write-Host "Guildless: 稼働していません"
}
