param(
    [string]$VhdPath = "C:\Users\YANG\AppData\Local\Docker\wsl\disk\docker_data.vhdx"
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Please run this script in an elevated Administrator PowerShell."
}

if (!(Test-Path $VhdPath)) {
    throw "Docker VHDX not found: $VhdPath"
}

Write-Host "Stopping Docker/WSL..."
docker system df 2>$null | Out-Host
wsl --shutdown
Start-Sleep -Seconds 8
Get-Process "Docker Desktop", "com.docker.backend" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

$before = [math]::Round((Get-Item $VhdPath).Length / 1GB, 2)
Write-Host "Docker VHDX before compact: $before GB"

if (Get-Command Optimize-VHD -ErrorAction SilentlyContinue) {
    Optimize-VHD -Path $VhdPath -Mode Full
} else {
    $diskpartScript = @"
select vdisk file="$VhdPath"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@
    $tmp = Join-Path $env:TEMP "compact-docker-vhdx.txt"
    Set-Content -Path $tmp -Value $diskpartScript -Encoding ASCII
    diskpart /s $tmp
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

$after = [math]::Round((Get-Item $VhdPath).Length / 1GB, 2)
Write-Host "Docker VHDX after compact: $after GB"
Get-PSDrive C | Select-Object Name, @{n = "UsedGB"; e = { [math]::Round($_.Used / 1GB, 2) } }, @{n = "FreeGB"; e = { [math]::Round($_.Free / 1GB, 2) } }

