param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,
    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"
$packageRoot = Split-Path $PSScriptRoot -Parent
$dropInRoot = Join-Path $packageRoot "drop-in"

if (!(Test-Path $dropInRoot)) {
    throw "drop-in directory not found: $dropInRoot"
}

if (!(Test-Path $TargetRoot)) {
    throw "TargetRoot does not exist: $TargetRoot"
}

$resolvedTarget = (Resolve-Path $TargetRoot).Path
$files = Get-ChildItem -Path $dropInRoot -Recurse -File

foreach ($file in $files) {
    $relative = $file.FullName.Substring($dropInRoot.Length).TrimStart("\", "/")
    $target = Join-Path $resolvedTarget $relative
    Write-Host "$relative -> $target"
    if (!$WhatIfOnly) {
        New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

Write-Host "Applied $($files.Count) fine-tuning handoff files."

