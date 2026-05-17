$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = "D:\ai_helth-main"
$python = "C:\Users\13010\anaconda3\envs\helth-gpu\python.exe"
$apiBase = "http://127.0.0.1:8000/api/v1"
$outDir = Join-Path $root "tmp_rtsp_camera1_debug"
$snapshotPath = Join-Path $outDir "camera1_snapshot.jpg"
$summaryPath = Join-Path $outDir "pipeline_summary.json"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Read-EnvFile {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $map
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $map[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
    return $map
}

function Invoke-JsonGet {
    param([string]$Url)
    Invoke-RestMethod -Uri $Url -TimeoutSec 20
}

function Get-FirstValue {
    param(
        [hashtable]$Map,
        [string[]]$Keys,
        [string]$Default = ""
    )
    foreach ($key in $Keys) {
        if ($Map.ContainsKey($key)) {
            $value = $Map[$key]
            if ($null -ne $value -and "$value".Trim() -ne "") {
                return "$value".Trim()
            }
        }
    }
    return $Default
}

function Restart-Backend {
    Write-Host "== 重启后端 ==" -ForegroundColor Cyan
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

    Start-Sleep -Seconds 2

    Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $root `
        -WindowStyle Hidden

    Start-Sleep -Seconds 12
    $health = Invoke-JsonGet "$apiBase/../healthz".Replace("/api/v1/..", "")
    $health | ConvertTo-Json -Depth 4
}

function Save-Snapshot {
    param([hashtable]$Payload)
    Write-Host "== 保存快照 ==" -ForegroundColor Cyan
    $json = $Payload | ConvertTo-Json -Depth 6
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    Invoke-WebRequest `
        -Uri "$apiBase/camera/setup/test-snapshot" `
        -Method Post `
        -ContentType "application/json" `
        -Body $bytes `
        -OutFile $snapshotPath `
        -TimeoutSec 30 | Out-Null
    Get-Item -LiteralPath $snapshotPath | Select-Object FullName,Length,LastWriteTime
}

$envMap = Read-EnvFile -Path (Join-Path $root ".env")

$cameraIp = Get-FirstValue -Map $envMap -Keys @("CAMERA1_IP", "CAMERA_IP")
$cameraUser = Get-FirstValue -Map $envMap -Keys @("CAMERA1_USER", "CAMERA_USER") -Default "admin"
$cameraPassword = Get-FirstValue -Map $envMap -Keys @("CAMERA1_PASSWORD", "CAMERA_PASSWORD")
$cameraRtspPort = Get-FirstValue -Map $envMap -Keys @("CAMERA1_RTSP_PORT", "CAMERA_RTSP_PORT") -Default "554"
$cameraRtspPath = Get-FirstValue -Map $envMap -Keys @("CAMERA1_RTSP_PATH", "CAMERA_RTSP_PATH")
$cameraStreamRtspPath = Get-FirstValue -Map $envMap -Keys @("CAMERA1_STREAM_RTSP_PATH", "CAMERA_STREAM_RTSP_PATH")
$cameraAudioRtspPath = Get-FirstValue -Map $envMap -Keys @("CAMERA1_AUDIO_RTSP_PATH", "CAMERA_AUDIO_RTSP_PATH")
$cameraOnvifPort = Get-FirstValue -Map $envMap -Keys @("CAMERA1_ONVIF_PORT", "CAMERA_ONVIF_PORT") -Default "0"

$camera1Payload = @{
    camera_source_mode = "rtsp"
    camera_ip = $cameraIp
    camera_user = $cameraUser
    camera_password = $cameraPassword
    camera_rtsp_port = [int]$cameraRtspPort
    camera_rtsp_path = $cameraRtspPath
    camera_stream_rtsp_path = $cameraStreamRtspPath
    camera_audio_rtsp_path = $cameraAudioRtspPath
    camera_onvif_port = [int]$cameraOnvifPort
}

Write-Host "== camera1 当前参数 ==" -ForegroundColor Cyan
$camera1Payload | ConvertTo-Json -Depth 4

Write-Host "== 第一步：写入 RTSP 配置 ==" -ForegroundColor Cyan
$configResp = Invoke-RestMethod `
    -Uri "$apiBase/camera/setup/config" `
    -Method Post `
    -ContentType "application/json" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes(($camera1Payload | ConvertTo-Json -Depth 6))) `
    -TimeoutSec 20
$configResp | ConvertTo-Json -Depth 6

Restart-Backend | Out-Host

Write-Host "== 第二步：确认后端摄像头状态 ==" -ForegroundColor Cyan
$cameraStatus = Invoke-JsonGet "$apiBase/camera/status"
$streamStatus = Invoke-JsonGet "$apiBase/camera/stream-status"
$cameraStatus | ConvertTo-Json -Depth 6
$streamStatus | ConvertTo-Json -Depth 6

Write-Host "== 第三步：RTSP 直连探测 ==" -ForegroundColor Cyan
& $python "$root\scripts\camera_direct_probe.py" --hosts $camera1Payload.camera_ip --rtsp-ports "$($camera1Payload.camera_rtsp_port),554,10554"

Save-Snapshot -Payload $camera1Payload | Out-Host

Write-Host "== 第四/五步：姿态 + 跌倒最小闭环 ==" -ForegroundColor Cyan
$pipelineJson = & $python "$root\scripts\debug_camera_pose_fall_pipeline.py" --image-path $snapshotPath
$pipelineJson | Out-Host
$pipelineJson | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "== 第六步：前端/后端展示地址 ==" -ForegroundColor Green
Write-Host "前端: http://127.0.0.1:5182/"
Write-Host "后端健康: http://127.0.0.1:8000/healthz"
Write-Host "原始流: http://127.0.0.1:8000/api/v1/camera/stream.mjpg"
Write-Host "姿态流: http://127.0.0.1:8000/api/v1/camera/stream.pose.mjpg"
Write-Host "检测流: http://127.0.0.1:8000/api/v1/camera/stream.detect.mjpg"
Write-Host "姿态最新: http://127.0.0.1:8000/api/v1/camera/pose-detection/latest"
Write-Host "跌倒状态: http://127.0.0.1:8000/api/v1/camera/fall-detection/status"
Write-Host ""
Write-Host "== 中间结果输出目录 ==" -ForegroundColor Green
Write-Host $outDir
