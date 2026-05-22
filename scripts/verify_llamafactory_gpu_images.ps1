param(
    [string[]]$Images = @("health-llamafactory-gpu:latest", "health-llamafactory-gpu-devel:latest")
)

$ErrorActionPreference = "Continue"

$probe = @'
import importlib.util, json, subprocess
mods = ["llamafactory", "torch", "deepspeed", "flash_attn", "vllm", "unsloth", "liger_kernel"]
result = {"modules": {name: importlib.util.find_spec(name) is not None for name in mods}}
try:
    import torch
    result["torch"] = getattr(torch, "__version__", "")
    result["cuda_available"] = bool(torch.cuda.is_available())
    result["cuda_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
    result["cuda_capability"] = torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None
    if torch.cuda.is_available():
        x = torch.ones((1,), device="cuda")
        result["cuda_tensor_ok"] = float(x.cpu()[0]) == 1.0
except Exception as exc:
    result["error"] = f"{type(exc).__name__}: {exc}"
try:
    nvcc = subprocess.run(["nvcc", "-V"], capture_output=True, text=True, timeout=10)
    result["nvcc"] = nvcc.returncode == 0
    result["nvcc_version"] = (nvcc.stdout or nvcc.stderr).strip().splitlines()[-1] if (nvcc.stdout or nvcc.stderr).strip() else ""
except Exception as exc:
    result["nvcc"] = False
    result["nvcc_error"] = f"{type(exc).__name__}: {exc}"
print(json.dumps(result, ensure_ascii=False, default=str))
'@

foreach ($image in $Images) {
    docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) {
        [pscustomobject]@{ image = $image; exists = $false } | ConvertTo-Json -Compress
        continue
    }
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("llamafactory-gpu-probe-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
    $probePath = Join-Path $tmpDir "probe.py"
    Set-Content -Path $probePath -Value $probe -Encoding UTF8
    $mountPath = $probePath -replace "\\", "/"
    $output = docker run --rm --gpus all -v "${mountPath}:/tmp/probe.py:ro" $image python /tmp/probe.py 2>&1
    Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -eq 0) {
        $payload = $output | Select-Object -Last 1
        [pscustomobject]@{ image = $image; exists = $true; probe = ($payload | ConvertFrom-Json) } | ConvertTo-Json -Compress -Depth 8
    } else {
        [pscustomobject]@{ image = $image; exists = $true; error = ($output -join "`n") } | ConvertTo-Json -Compress
    }
}
