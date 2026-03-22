param(
    [string]$Model = "Qwen3:1.7B",
    [string]$Prompt = "",
    [switch]$ListModels
)

function Get-InstalledModelNames {
    $lines = ollama list | Select-Object -Skip 1
    $names = @()
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if (-not $trimmed) {
            continue
        }
        $parts = $trimmed -split "\s{2,}"
        if ($parts.Length -gt 0 -and $parts[0].Trim()) {
            $names += $parts[0].Trim()
        }
    }
    return $names
}

$installedModels = Get-InstalledModelNames

if ($ListModels) {
    Write-Host "Installed Ollama models:"
    foreach ($name in $installedModels) {
        Write-Host " - $name"
    }
    exit 0
}

$matchedModel = $installedModels | Where-Object { $_.ToLower() -eq $Model.ToLower() } | Select-Object -First 1
if (-not $matchedModel) {
    Write-Error "Model '$Model' is not installed. Use -ListModels to view available models."
    exit 1
}

if ($Prompt) {
    Write-Host "Running one-shot prompt with model: $matchedModel"
    ollama run $matchedModel $Prompt
    exit $LASTEXITCODE
}

Write-Host "Starting interactive local chat with model: $matchedModel"
Write-Host "Press Ctrl+C to exit."
ollama run $matchedModel
exit $LASTEXITCODE
