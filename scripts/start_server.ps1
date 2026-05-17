param(
    [string]$CondaEnv = 'helth',
    [string]$ListenHost = '0.0.0.0',
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
. (Join-Path $PSScriptRoot 'conda_env.ps1')

function Test-BackendReady {
    param(
        [string]$ProbeHost = '127.0.0.1',
        [int]$Port = 8000
    )

    try {
        $resp = Invoke-RestMethod -Uri "http://$ProbeHost`:$Port/healthz" -TimeoutSec 2
        return $resp.status -eq 'ok'
    }
    catch {
        return $false
    }
}

$existingPids = @(
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
)

if ($existingPids.Count -gt 0) {
    if (Test-BackendReady -Port $Port) {
        Write-Host "Backend already running on port $Port, reusing existing service."
        exit 0
    }

    $procSummary = $existingPids |
        ForEach-Object {
            $proc = Get-Process -Id $_ -ErrorAction SilentlyContinue
            if ($proc) { "$($proc.ProcessName)($($_))" } else { "PID=$_" }
        }

    throw "Port $Port is already in use by $($procSummary -join ', '). Please stop that process before starting a new backend."
}

$args = @('-m', 'uvicorn', 'backend.main:app', '--host', $ListenHost, '--port', "$Port")
if ($Reload) {
    $args += '--reload'
}

$python = Resolve-EnvPython -CondaEnv $CondaEnv
try {
    $localIpv4 = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254*' -and
            $_.ValidLifetime -gt 0
    } |
        Sort-Object -Property InterfaceMetric |
        Select-Object -First 1 -ExpandProperty IPAddress
    if ($localIpv4) {
        Write-Host "Mobile app should use: http://${localIpv4}:${Port}"
    }
} catch {
    # Ignore IP discovery failure; backend can still start.
}
& $python @args
exit $LASTEXITCODE
