param(
    [string]$CameraIp = "",
    [string]$Password = "",
    [ValidateSet("tcp", "udp")]
    [string]$Transport = "tcp",
    [string]$Stream = "sub",
    [double]$DurationSeconds = 8.0,
    [string]$Source = ""
)

$pythonCandidates = @(
    "C:\Users\YANG\.conda\envs\AI\python.exe",
    "C:\Users\YANG\.conda\envs\health\python.exe",
    "D:\Anaconda\python.exe"
)

$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    Write-Host "No usable Python runtime was found."
    exit 2
}

$script = Join-Path $PSScriptRoot "camera_probe_xstrive.py"
if (-not (Test-Path $script)) {
    Write-Host "camera_probe_xstrive.py was not found next to this launcher."
    exit 3
}

$args = @($script, "--transport", $Transport, "--stream", $Stream, "--duration-seconds", "$DurationSeconds")

if ($Source) {
    $args += @("--source", $Source)
} else {
    if (-not $CameraIp) {
        Write-Host "Provide -CameraIp or -Source."
        exit 4
    }
    $args += @("--host", $CameraIp, "--password", $Password)
}

Write-Host "Using Python:" $python
Write-Host "Launching camera probe..."
& $python @args
exit $LASTEXITCODE
