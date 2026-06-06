param(
    [string]$FileName = "CameraRuntime8090.cmd"
)

$startupDir = [Environment]::GetFolderPath("Startup")
$target = Join-Path $startupDir $FileName

if (Test-Path $target) {
    Remove-Item $target -Force
    Write-Host "Startup launcher removed."
    Write-Host ("Path: " + $target)
} else {
    Write-Host "Startup launcher did not exist."
    Write-Host ("Path: " + $target)
}

