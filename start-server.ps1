$out = 'D:\guildless\server-revenue.log'
$err = 'D:\guildless\server-revenue.err.log'
$p = Start-Process -FilePath 'D:\guildless\.venv\Scripts\python.exe' -ArgumentList @('-m','council','serve','--host','127.0.0.1','--port','8780') -WorkingDirectory 'D:\guildless' -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru
Write-Output "PID=$($p.Id)"
