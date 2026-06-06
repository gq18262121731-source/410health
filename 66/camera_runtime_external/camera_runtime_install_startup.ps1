param(
    [string]$FileName = "CameraRuntime8090.cmd"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupDir = [Environment]::GetFolderPath("Startup")
if (-not $startupDir) {
    Write-Host "Startup folder was not found."
    exit 2
}

$startScript = Join-Path $root "camera_runtime_start.ps1"
if (-not (Test-Path $startScript)) {
    Write-Host "camera_runtime_start.ps1 was not found."
    exit 3
}

$target = Join-Path $startupDir $FileName
$content = @"
@echo off
powershell.exe -ExecutionPolicy Bypass -File "$startScript" -ListenPort 8090
"@
$content | Set-Content -Path $target -Encoding ASCII

Write-Host "Startup launcher installed."
Write-Host ("Path: " + $target)

