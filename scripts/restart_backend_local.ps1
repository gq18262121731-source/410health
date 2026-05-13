$ErrorActionPreference = "Stop"

$backendPids = @(
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
)

foreach ($pid in $backendPids) {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

$python = "C:\Users\13010\anaconda3\envs\helth\python.exe"
Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory "D:\ai_helth-main" `
    -WindowStyle Hidden

Start-Sleep -Seconds 8

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 8 |
        ConvertTo-Json -Compress
} catch {
    $_.Exception.Message
}
