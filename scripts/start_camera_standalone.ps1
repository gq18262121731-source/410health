param(
    [string]$CondaEnv = "health",
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8001,
    [int]$CameraIndex = 0,
    [ValidateSet("auto", "any", "dshow", "msmf")]
    [string]$Backend = "any",
    [double]$Fps = 6.0,
    [int]$JpegQuality = 85
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
. (Join-Path $PSScriptRoot "conda_env.ps1")

function Test-CameraServiceReady {
    param(
        [string]$ProbeHost = "127.0.0.1",
        [int]$ProbePort = 8001
    )

    try {
        $resp = Invoke-RestMethod -Uri "http://$ProbeHost`:$ProbePort/" -TimeoutSec 2
        return $resp.status -eq "running"
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
    if (Test-CameraServiceReady -ProbeHost $ListenHost -ProbePort $Port) {
        Write-Host "Standalone camera service already running on port $Port, reusing existing service."
        exit 0
    }

    $procSummary = $existingPids |
        ForEach-Object {
            $proc = Get-Process -Id $_ -ErrorAction SilentlyContinue
            if ($proc) { "$($proc.ProcessName)($($_))" } else { "PID=$_" }
        }

    throw "Port $Port is already in use by $($procSummary -join ', '). Please stop that process before starting a new camera service."
}

$python = Resolve-EnvPython -CondaEnv $CondaEnv
$scriptPath = Join-Path $root "camera_service_standalone.py"

& $python $scriptPath `
    --host $ListenHost `
    --port $Port `
    --camera-index $CameraIndex `
    --backend $Backend `
    --fps $Fps `
    --jpeg-quality $JpegQuality

exit $LASTEXITCODE
