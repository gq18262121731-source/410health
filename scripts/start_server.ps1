param(
    [string]$CondaEnv = 'helth',
    [string]$ListenHost = '127.0.0.1',
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
. (Join-Path $PSScriptRoot 'conda_env.ps1')

$args = @('-m', 'uvicorn', 'backend.main:app', '--host', $ListenHost, '--port', "$Port")
if ($Reload) {
    Write-Warning 'The project lives in OneDrive. Use --reload only when you really need hot reloading.'
    $args += '--reload'
}

$python = Resolve-EnvPython -CondaEnv $CondaEnv
& $python @args
exit $LASTEXITCODE
