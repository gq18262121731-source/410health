$ErrorActionPreference = "Stop"

$dllDir = $env:CAMERA_P2P_DLL_DIR
$uid = $env:CAMERA_ACTIVEX_ID
$user = $env:CAMERA_USER
$password = $env:CAMERA_PASSWORD
$logFile = $env:CAMERA_P2P_TALK_LOG
$server = $env:CAMERA_P2P_SERVER

function Log-Line($message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    if ($logFile) {
        Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8
    }
    Write-Output $line
}

if ([string]::IsNullOrWhiteSpace($dllDir)) {
    $dllDir = "C:\Program Files (x86)\IPCam ActiveX\925"
}
if ([string]::IsNullOrWhiteSpace($uid)) {
    throw "CAMERA_ACTIVEX_ID_NOT_CONFIGURED"
}
if ([string]::IsNullOrWhiteSpace($user)) {
    $user = "admin"
}
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "CAMERA_PASSWORD_NOT_CONFIGURED"
}
if ([string]::IsNullOrWhiteSpace($server)) {
    # Android Demo uses this server/license string for VSTA*/PISR* devices.
    $server = "EFGFFBBOKAIEGHJAEDHJFEEOHMNGDCNJCDFKAKHLEBJHKEKMCAFCDLLLHAOCJPPMBHMNOMCJKGJEBGGHJHIOMFBDNPKNFEGCEGCBGCALMFOHBCGMFK"
}
if (-not (Test-Path -LiteralPath (Join-Path $dllDir "P2PAPI.dll"))) {
    throw "P2PAPI_DLL_NOT_FOUND: $dllDir"
}

Set-Location -LiteralPath $dllDir
$env:PATH = "$dllDir;$env:PATH"

$source = @"
using System;
using System.Runtime.InteropServices;

public static class CameraP2PTalkNative
{
    public const int MSG_TYPE_P2P_STATUS = 0;
    public const int P2P_STATUS_CONNECT_SUCCESS = 2;

    public static int LastMessageType = -1;
    public static int LastP2PStatus = -1;
    public static int MessageCallbackCount = 0;
    public static MessageCallback NativeMessageCallback = OnMessage;

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    public delegate void MessageCallback(int handle, int type, IntPtr msg, int len, IntPtr param);

    private static void OnMessage(int handle, int type, IntPtr msg, int len, IntPtr param)
    {
        LastMessageType = type;
        MessageCallbackCount += 1;
        if (type == MSG_TYPE_P2P_STATUS && msg != IntPtr.Zero && len > 0)
        {
            LastP2PStatus = len >= 4 ? Marshal.ReadInt32(msg) : Marshal.ReadByte(msg);
        }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetDllDirectory(string lpPathName);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_Initial();

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_InitialWithServer(string server);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_DeInitial();

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_CreateInstance(out int handle);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_DestroyInstance(int handle);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_Connect(int handle, string uid, string user, string pwd);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_Close(int handle);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_StartTalk(int handle);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_StopTalk(int handle);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_TalkData(int handle, byte[] data, int len);

    [DllImport("P2PAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    public static extern int P2PAPI_SetMessageCallBack(int handle, MessageCallback callback, IntPtr param);
}
"@

Add-Type -TypeDefinition $source
[CameraP2PTalkNative]::SetDllDirectory($dllDir) | Out-Null

$handle = 0
try {
    Log-Line "P2P_GATEWAY_START dllDir=$dllDir uid=$uid"
    $ret = [CameraP2PTalkNative]::P2PAPI_InitialWithServer($server)
    Log-Line "P2PAPI_InitialWithServer=$ret serverLen=$($server.Length)"
    if ($ret -ne 0) {
        $ret = [CameraP2PTalkNative]::P2PAPI_Initial()
        Log-Line "P2PAPI_Initial_FALLBACK=$ret"
    }
    $ret = [CameraP2PTalkNative]::P2PAPI_CreateInstance([ref]$handle)
    Log-Line "P2PAPI_CreateInstance=$ret handle=$handle"
    if ($ret -ne 0) {
        throw "P2PAPI_CreateInstance_FAILED:$ret"
    }
    $ret = [CameraP2PTalkNative]::P2PAPI_SetMessageCallBack($handle, [CameraP2PTalkNative]::NativeMessageCallback, [IntPtr]::Zero)
    Log-Line "P2PAPI_SetMessageCallBack=$ret"
    $ret = [CameraP2PTalkNative]::P2PAPI_Connect($handle, $uid, $user, $password)
    Log-Line "P2PAPI_Connect=$ret"
    if ($ret -ne 0) {
        throw "P2PAPI_Connect_FAILED:$ret"
    }
    $lastCallbackCount = -1
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        $callbackCount = [CameraP2PTalkNative]::MessageCallbackCount
        if ($callbackCount -ne $lastCallbackCount) {
            $lastCallbackCount = $callbackCount
            Log-Line "P2P_STATUS_WAIT attempt=$attempt callbacks=$callbackCount lastType=$([CameraP2PTalkNative]::LastMessageType) lastStatus=$([CameraP2PTalkNative]::LastP2PStatus)"
        }
        if ([CameraP2PTalkNative]::LastP2PStatus -eq [CameraP2PTalkNative]::P2P_STATUS_CONNECT_SUCCESS) {
            break
        }
    }
    if ([CameraP2PTalkNative]::LastP2PStatus -ne [CameraP2PTalkNative]::P2P_STATUS_CONNECT_SUCCESS) {
        Log-Line "P2P_STATUS_NOT_CONFIRMED lastStatus=$([CameraP2PTalkNative]::LastP2PStatus)"
    }
    $ret = -6
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        $ret = [CameraP2PTalkNative]::P2PAPI_StartTalk($handle)
        Log-Line "P2PAPI_StartTalk attempt=$attempt ret=$ret"
        if ($ret -eq 0) {
            break
        }
    }
    if ($ret -ne 0) {
        throw "P2PAPI_StartTalk_FAILED:$ret"
    }

    $inputStream = [Console]::OpenStandardInput()
    $buffer = New-Object byte[] 3200
    $chunks = 0
    $bytes = 0
    while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        if ($read -eq $buffer.Length) {
            $payload = $buffer
        } else {
            $payload = New-Object byte[] $read
            [Array]::Copy($buffer, $payload, $read)
        }
        $ret = [CameraP2PTalkNative]::P2PAPI_TalkData($handle, $payload, $read)
        $chunks += 1
        $bytes += $read
        if (($chunks % 50) -eq 0 -or $ret -ne 0) {
            Log-Line "P2PAPI_TalkData ret=$ret chunks=$chunks bytes=$bytes"
        }
    }
    Log-Line "STDIN_CLOSED chunks=$chunks bytes=$bytes"
}
catch {
    Log-Line "P2P_GATEWAY_ERROR=$($_.Exception.Message)"
    exit 2
}
finally {
    if ($handle -ne 0) {
        try { [CameraP2PTalkNative]::P2PAPI_StopTalk($handle) | Out-Null; Log-Line "P2PAPI_StopTalk_CALLED" } catch {}
        try { [CameraP2PTalkNative]::P2PAPI_Close($handle) | Out-Null; Log-Line "P2PAPI_Close_CALLED" } catch {}
        try { [CameraP2PTalkNative]::P2PAPI_DestroyInstance($handle) | Out-Null; Log-Line "P2PAPI_DestroyInstance_CALLED" } catch {}
    }
    try { [CameraP2PTalkNative]::P2PAPI_DeInitial() | Out-Null; Log-Line "P2PAPI_DeInitial_CALLED" } catch {}
}
