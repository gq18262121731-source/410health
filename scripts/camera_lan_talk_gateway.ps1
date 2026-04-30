$ErrorActionPreference = "Stop"

$dllDir = $env:CAMERA_LAN_TALK_DLL_DIR
$ip = $env:CAMERA_IP
$portText = $env:CAMERA_ONVIF_PORT
$user = $env:CAMERA_USER
$password = $env:CAMERA_PASSWORD
$logFile = $env:CAMERA_LAN_TALK_LOG
$readyFile = $env:CAMERA_LAN_TALK_READY_FILE
$sendMode = $env:CAMERA_LAN_TALK_SEND_MODE

function Log-Line($message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    if ($logFile) {
        try {
            Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
        } catch {
            # The backend may poll this file while audio is flowing; logging must never kill talkback.
        }
    }
    Write-Output $line
}

if ([string]::IsNullOrWhiteSpace($dllDir)) {
    $dllDir = "C:\Program Files (x86)\IPCam ActiveX\924"
}
if ([string]::IsNullOrWhiteSpace($ip)) {
    throw "CAMERA_IP_NOT_CONFIGURED"
}
if ([string]::IsNullOrWhiteSpace($portText)) {
    $portText = "10080"
}
if ([string]::IsNullOrWhiteSpace($user)) {
    $user = "admin"
}
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "CAMERA_PASSWORD_NOT_CONFIGURED"
}
if (-not (Test-Path -LiteralPath (Join-Path $dllDir "DevDll_924.dll"))) {
    throw "DEV_DLL_924_NOT_FOUND: $dllDir"
}
if ([string]::IsNullOrWhiteSpace($sendMode)) {
    $sendMode = "pcm_mode1"
}

Set-Location -LiteralPath $dllDir
$env:PATH = "$dllDir;$env:PATH"

$source = @"
using System;
using System.Runtime.InteropServices;

public static class CameraLanTalkNative
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetDllDirectory(string lpPathName);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "dev_Init")]
    public static extern IntPtr DevInit();

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, EntryPoint = "dev_put_auth")]
    public static extern int PutAuth(IntPtr handle, string user, string password);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi, EntryPoint = "dev_put_IP")]
    public static extern int PutIp(IntPtr handle, string ip, string port, string stream, int reserved1, int reserved2, int reserved3);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_Connect")]
    public static extern int Connect(IntPtr handle, int stream);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_Start")]
    public static extern int Start(IntPtr handle);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_StartAudio")]
    public static extern int StartAudio(IntPtr handle);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_GetTalkAudioFmt")]
    public static extern int GetTalkAudioFmt(IntPtr handle, out int fmt);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_EncodeAudio")]
    public static extern int EncodeAudio(IntPtr unused, byte[] pcm, int pcmLen, int mode, byte[] encoded, out int encodedLen, out int extra1, out int extra2);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_TalkOpen")]
    public static extern int TalkOpen(IntPtr handle);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_SetTalkData")]
    public static extern int SetTalkData(IntPtr handle, byte[] data, int len);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_SetTalkData2")]
    public static extern int SetTalkData2(IntPtr handle, int mode, byte[] data, int len);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_TalkClose")]
    public static extern int TalkClose(IntPtr handle);

    [DllImport("DevDll_924.dll", CallingConvention = CallingConvention.StdCall, EntryPoint = "dev_DisConnect")]
    public static extern int Disconnect(IntPtr handle);
}
"@

Add-Type -TypeDefinition $source
[CameraLanTalkNative]::SetDllDirectory($dllDir) | Out-Null

$handle = [IntPtr]::Zero
$pcmFrameSize = 320
$pending = New-Object byte[] 0
$chunks = 0
$pcmBytes = 0
$encodedBytes = 0

function Send-PcmFrame([IntPtr]$handle, [byte[]]$pcmFrame) {
    $talkRet = -999
    $sentLen = $pcmFrame.Length
    if ($script:sendMode -eq "pcm_mode1") {
        # dev_SetTalkData2 signature is (handle, mode, data, len). mode=1 lets the vendor DLL
        # encode 16-bit PCM into the camera talk format internally.
        $talkRet = [CameraLanTalkNative]::SetTalkData2($handle, 1, $pcmFrame, $pcmFrame.Length)
    } elseif ($script:sendMode -eq "pcm_mode0") {
        $talkRet = [CameraLanTalkNative]::SetTalkData2($handle, 0, $pcmFrame, $pcmFrame.Length)
    } elseif ($script:sendMode -eq "pcm_setdata") {
        $talkRet = [CameraLanTalkNative]::SetTalkData($handle, $pcmFrame, $pcmFrame.Length)
    } elseif ($script:sendMode -eq "encoded_setdata" -or $script:sendMode -eq "encoded_mode0" -or $script:sendMode -eq "encoded_mode1") {
        $encoded = New-Object byte[] 1024
        $encodedLen = 0
        $extra1 = 0
        $extra2 = 0
        $encodeRet = [CameraLanTalkNative]::EncodeAudio([IntPtr]::Zero, $pcmFrame, $pcmFrame.Length, 1, $encoded, [ref]$encodedLen, [ref]$extra1, [ref]$extra2)
        if ($encodeRet -ne 0 -or $encodedLen -le 0) {
            [void](Log-Line "LAN_TALK_ENCODE_ERROR mode=$script:sendMode ret=$encodeRet encodedLen=$encodedLen")
            return 0
        }
        $payload = New-Object byte[] $encodedLen
        [Array]::Copy($encoded, $payload, $encodedLen)
        $sentLen = $encodedLen
        if ($script:sendMode -eq "encoded_setdata") {
            $talkRet = [CameraLanTalkNative]::SetTalkData($handle, $payload, $payload.Length)
        } elseif ($script:sendMode -eq "encoded_mode0") {
            $talkRet = [CameraLanTalkNative]::SetTalkData2($handle, 0, $payload, $payload.Length)
        } else {
            $talkRet = [CameraLanTalkNative]::SetTalkData2($handle, 1, $payload, $payload.Length)
        }
    } else {
        [void](Log-Line "LAN_TALK_UNKNOWN_SEND_MODE=$script:sendMode")
        return 0
    }
    if (($script:chunks % 50) -eq 0) {
        [void](Log-Line "LAN_TALK_FRAME sendMode=$script:sendMode sentLen=$sentLen pcmLen=$($pcmFrame.Length) talkRet=$talkRet")
    }
    return [int]$sentLen
}

try {
    Log-Line "LAN_TALK_GATEWAY_START dllDir=$dllDir ip=$ip port=$portText sendMode=$sendMode"
    $handle = [CameraLanTalkNative]::DevInit()
    Log-Line "dev_Init handle=$handle"
    if ($handle -eq [IntPtr]::Zero) {
        throw "DEV_INIT_FAILED"
    }

    Log-Line ("dev_put_auth=" + [CameraLanTalkNative]::PutAuth($handle, $user, $password))
    Log-Line ("dev_put_IP=" + [CameraLanTalkNative]::PutIp($handle, $ip, $portText, "0", 0, 0, 0))
    Log-Line ("dev_Connect=" + [CameraLanTalkNative]::Connect($handle, 0))
    Start-Sleep -Seconds 5
    Log-Line ("dev_Start=" + [CameraLanTalkNative]::Start($handle))
    Log-Line ("dev_StartAudio=" + [CameraLanTalkNative]::StartAudio($handle))
    $fmt = 0
    Log-Line ("dev_GetTalkAudioFmt=" + [CameraLanTalkNative]::GetTalkAudioFmt($handle, [ref]$fmt) + " fmt=$fmt")
    Log-Line ("dev_TalkOpen=" + [CameraLanTalkNative]::TalkOpen($handle))
    if ($readyFile) {
        try {
            Set-Content -LiteralPath $readyFile -Value "ready" -Encoding ASCII
        } catch {}
    }
    Log-Line "LAN_TALK_READY"

    $inputStream = [Console]::OpenStandardInput()
    $buffer = New-Object byte[] 4096
    while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $combined = New-Object byte[] ($pending.Length + $read)
        if ($pending.Length -gt 0) {
            [Array]::Copy($pending, 0, $combined, 0, $pending.Length)
        }
        [Array]::Copy($buffer, 0, $combined, $pending.Length, $read)

        $offset = 0
        while (($combined.Length - $offset) -ge $pcmFrameSize) {
            $frame = New-Object byte[] $pcmFrameSize
            [Array]::Copy($combined, $offset, $frame, 0, $pcmFrameSize)
            $script:chunks += 1
            $script:pcmBytes += $pcmFrameSize
            $script:encodedBytes += Send-PcmFrame $handle $frame
            $offset += $pcmFrameSize
        }

        $remaining = $combined.Length - $offset
        $pending = New-Object byte[] $remaining
        if ($remaining -gt 0) {
            [Array]::Copy($combined, $offset, $pending, 0, $remaining)
        }
    }
    Log-Line "STDIN_CLOSED chunks=$chunks pcmBytes=$pcmBytes encodedBytes=$encodedBytes pending=$($pending.Length)"
}
catch {
    Log-Line "LAN_TALK_GATEWAY_ERROR=$($_.Exception.Message)"
    exit 2
}
finally {
    if ($handle -ne [IntPtr]::Zero) {
        try { [CameraLanTalkNative]::TalkClose($handle) | Out-Null; Log-Line "dev_TalkClose_CALLED" } catch {}
        try { [CameraLanTalkNative]::Disconnect($handle) | Out-Null; Log-Line "dev_DisConnect_CALLED" } catch {}
    }
    if ($readyFile) {
        try { Remove-Item -LiteralPath $readyFile -Force -ErrorAction SilentlyContinue } catch {}
    }
}
