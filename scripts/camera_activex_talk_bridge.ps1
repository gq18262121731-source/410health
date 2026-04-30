$ErrorActionPreference = "Continue"

$ip = $env:CAMERA_IP
$deviceId = $env:CAMERA_ACTIVEX_ID
$user = $env:CAMERA_USER
$password = $env:CAMERA_PASSWORD
$stopFile = $env:CAMERA_TALK_STOP_FILE
$portText = $env:CAMERA_ACTIVEX_PORT
$devTypeText = $env:CAMERA_ACTIVEX_DEV_TYPE
$maxSecondsText = $env:CAMERA_TALK_MAX_SECONDS
if ([string]::IsNullOrWhiteSpace($portText)) { $portText = "10080" }
if ([string]::IsNullOrWhiteSpace($devTypeText)) { $devTypeText = "924" }
if ([string]::IsNullOrWhiteSpace($maxSecondsText)) { $maxSecondsText = "60" }
$port = [int]$portText
$devType = [int]$devTypeText
$maxSeconds = [int]$maxSecondsText

function Write-BridgeLog {
  param([string]$Message)
  Write-Output ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
}

if ($devType -eq 924) {
  $deviceId = $ip
} elseif ([string]::IsNullOrWhiteSpace($deviceId)) {
  $deviceId = $ip
}

if ([string]::IsNullOrWhiteSpace($deviceId) -or [string]::IsNullOrWhiteSpace($user) -or [string]::IsNullOrWhiteSpace($password)) {
  Write-BridgeLog "MISSING_CAMERA_ENV"
  exit 2
}

if ([string]::IsNullOrWhiteSpace($stopFile)) {
  Write-BridgeLog "MISSING_STOP_FILE"
  exit 2
}

$remote = $null
try {
  Write-BridgeLog "CREATE_COM"
  $remote = New-Object -ComObject AxRemoteProj1.AxRemote

  try { $remote.Lan = "cn" } catch {}
  try { $remote.TCPMode = 1 } catch {}

  $isLan = 1
  if ($devType -eq 922 -and $port -eq 0) { $isLan = 0 }
  Write-BridgeLog ("ADD_DEV devType={0} id={1} port={2} isLan={3}" -f $devType, $deviceId, $port, $isLan)
  $addResult = $remote.AddDev4($devType, $isLan, $deviceId, $port, "Camera", $user, $password, 1)
  Write-BridgeLog ("ADD_DEV_RESULT=" + $addResult)

  $remote.ConnectAll()
  Write-BridgeLog "CONNECT_ALL_CALLED"
  Start-Sleep -Seconds 8

  try { Write-BridgeLog ("VIDEO_RECV=" + $remote.VideoRecv) } catch { Write-BridgeLog ("VIDEO_RECV_ERROR=" + $_.Exception.Message) }
  try { Write-BridgeLog ("LISTEN=" + $remote.Listen) } catch { Write-BridgeLog ("LISTEN_ERROR=" + $_.Exception.Message) }
  try { $remote.Listen = 1; Write-BridgeLog "LISTEN_SET_CALLED" } catch { Write-BridgeLog ("LISTEN_SET_ERROR=" + $_.Exception.Message) }
  Start-Sleep -Milliseconds 500

  $talking = 0
  for ($attempt = 1; $attempt -le 5; $attempt++) {
    $remote.StartTalk()
    Start-Sleep -Milliseconds 800
    try { $talking = [int]$remote.IsTalking } catch { $talking = 0 }
    Write-BridgeLog ("START_TALK_CALLED attempt={0} IsTalking={1}" -f $attempt, $talking)
    if ($talking -ne 0) {
      break
    }
  }

  $deadline = (Get-Date).AddSeconds([Math]::Max(5, $maxSeconds))
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $stopFile) {
      Write-BridgeLog "STOP_FILE_DETECTED"
      break
    }
    Start-Sleep -Milliseconds 250
  }

  try { $remote.StopTalk(); Write-BridgeLog "STOP_TALK_CALLED" } catch { Write-BridgeLog ("STOP_TALK_ERROR=" + $_.Exception.Message) }
  try { $remote.DisConnectAll(); Write-BridgeLog "DISCONNECT_ALL_CALLED" } catch {}
  exit 0
} catch {
  Write-BridgeLog ("BRIDGE_ERROR=" + $_.Exception.Message)
  try {
    if ($remote -ne $null) {
      $remote.StopTalk()
      $remote.DisConnectAll()
    }
  } catch {}
  exit 1
}
