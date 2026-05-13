param(
    [string]$CondaEnv = "health"
)

$ErrorActionPreference = "Stop"

function Resolve-EnvPython {
    param([string]$CondaEnv)

    $envNames = @($CondaEnv)
    if ($CondaEnv -eq "health") {
        $envNames += "helth"
    }

    foreach ($name in $envNames) {
    $candidates = @(
            (Join-Path $env:USERPROFILE ".conda\envs\$name\python.exe"),
            (Join-Path $env:USERPROFILE "miniconda3\envs\$name\python.exe"),
            (Join-Path $env:USERPROFILE "anaconda3\envs\$name\python.exe"),
            (Join-Path $env:LOCALAPPDATA "anaconda3\envs\$name\python.exe")
    ) | Where-Object { $_ }

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }
    }

    throw "Cannot find python.exe for conda env '$CondaEnv'. Tried: $($envNames -join ', ')."
}
