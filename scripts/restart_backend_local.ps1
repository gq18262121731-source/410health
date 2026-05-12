$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "uvicorn|backend.main:app|frame_analysis_worker" }

foreach ($process in $processes) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

$python = "C:\Users\YANG\.conda\envs\helth\python.exe"
Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory "D:\Program\health(5-12)" `
    -WindowStyle Hidden

Start-Sleep -Seconds 8

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 8 |
        ConvertTo-Json -Compress
} catch {
    $_.Exception.Message
}
