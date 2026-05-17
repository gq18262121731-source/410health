param(
    [string]$CondaEnv = "llamafactory",
    [int]$Port = 7860,
    [string]$ProbeHost = "127.0.0.1",
    [string]$LLaMAFactoryRoot = "D:\Program\LLaMA-Factory"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

if (!(Test-Path $LLaMAFactoryRoot)) {
    throw "LLaMA-Factory root not found: $LLaMAFactoryRoot"
}

. (Join-Path $PSScriptRoot "conda_env.ps1")

function Test-TuningConsoleReady {
    param(
        [string]$ProbeHost,
        [int]$ProbePort
    )

    try {
        $resp = Invoke-WebRequest -Uri "http://$ProbeHost`:$ProbePort/" -UseBasicParsing -TimeoutSec 3
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
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
    if (Test-TuningConsoleReady -ProbeHost $ProbeHost -ProbePort $Port) {
        Write-Host "Model tuning console already running on port $Port."
        exit 0
    }
}

$python = Resolve-EnvPython -CondaEnv $CondaEnv
$env:GRADIO_SERVER_NAME = "0.0.0.0"
$env:GRADIO_SERVER_PORT = "$Port"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:LLAMA_FACTORY_ROOT = $LLaMAFactoryRoot
$env:DISABLE_VERSION_CHECK = "1"

Set-Location $LLaMAFactoryRoot
& $python (Join-Path $repoRoot "scripts\model_tuning_console_entry.py")
exit $LASTEXITCODE
