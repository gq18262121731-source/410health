import argparse
import ctypes
import json
import os
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SDK_DIR = ROOT / "摄像头说明书" / "extracted" / "SDK_phone (2)" / "SDK_phone" / "Lib" / "win32"


class CameraSdkGateway:
    def __init__(self, sdk_dir):
        self.sdk_dir = sdk_dir
        self.dll_path = sdk_dir / "P2PAPI.dll"
        self.dll = None
        self.load_error = None
        self.python_bitness = struct.calcsize("P") * 8
        self._load()

    @property
    def loadable(self):
        return self.dll is not None

    def _load(self):
        if self.python_bitness != 32:
            self.load_error = "This gateway must run with 32-bit Python because bundled SDK DLLs are x86."
            return
        if not self.dll_path.exists():
            self.load_error = "SDK DLL not found: {}".format(self.dll_path)
            return
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(str(self.sdk_dir))
            self.dll = ctypes.WinDLL(str(self.dll_path))
            self._configure_signatures()
        except OSError as exc:
            self.load_error = "{}: {}".format(exc.__class__.__name__, exc)

    def _configure_signatures(self):
        if self.dll is None:
            return

        self.dll.P2PAPI_Initial.restype = ctypes.c_long
        self.dll.P2PAPI_DeInitial.restype = ctypes.c_long
        self.dll.P2PAPI_GetAPIVersion.restype = ctypes.c_long
        self.dll.P2PAPI_CreateInstance.argtypes = [ctypes.POINTER(ctypes.c_long)]
        self.dll.P2PAPI_CreateInstance.restype = ctypes.c_long
        self.dll.P2PAPI_DestroyInstance.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_DestroyInstance.restype = ctypes.c_long
        self.dll.P2PAPI_Connect.argtypes = [ctypes.c_long, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self.dll.P2PAPI_Connect.restype = ctypes.c_long
        self.dll.P2PAPI_Close.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_Close.restype = ctypes.c_long
        self.dll.P2PAPI_StartAudio.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_StartAudio.restype = ctypes.c_long
        self.dll.P2PAPI_StopAudio.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_StopAudio.restype = ctypes.c_long
        self.dll.P2PAPI_StartTalk.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_StartTalk.restype = ctypes.c_long
        self.dll.P2PAPI_StopTalk.argtypes = [ctypes.c_long]
        self.dll.P2PAPI_StopTalk.restype = ctypes.c_long
        self.dll.P2PAPI_TalkData.argtypes = [ctypes.c_long, ctypes.c_char_p, ctypes.c_int]
        self.dll.P2PAPI_TalkData.restype = ctypes.c_long

    def status(self):
        return {
            "ok": self.loadable,
            "python_bitness": self.python_bitness,
            "sdk_dir": str(self.sdk_dir),
            "dll_path": str(self.dll_path),
            "sdk_version": None,
            "error": self.load_error,
            "missing_dependency_hint": "XQP2P_API.dll" if self.load_error and "WinError 126" in self.load_error else None,
            "implemented": {
                "listen": False,
                "talk": False,
                "status": True,
            },
        }


class GatewayHandler(BaseHTTPRequestHandler):
    gateway = None

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature.
        return

    def do_GET(self):  # noqa: N802 - stdlib hook.
        route = urlparse(self.path).path
        if route in {"/", "/health", "/sdk/status"}:
            self._json(self.gateway.status(), status=200)
            return
        self._json({"error": "NOT_FOUND"}, status=404)

    def do_POST(self):  # noqa: N802 - stdlib hook.
        route = urlparse(self.path).path
        if route in {"/audio/listen/start", "/audio/listen/stop", "/audio/talk/start", "/audio/talk/stop"}:
            self._json(
                {
                    "ok": False,
                    "error": "NOT_IMPLEMENTED",
                    "message": "SDK DLL loading is scaffolded. Audio session wiring is the next step.",
                },
                status=501,
            )
            return
        self._json({"error": "NOT_FOUND"}, status=404)

    def _json(self, payload, status):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description="32-bit camera audio SDK gateway.")
    parser.add_argument("--host", default=os.environ.get("CAMERA_AUDIO_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CAMERA_AUDIO_GATEWAY_PORT", "8765")))
    parser.add_argument("--sdk-dir", default=os.environ.get("CAMERA_SDK_DLL_DIR", str(DEFAULT_SDK_DIR)))
    args = parser.parse_args()

    GatewayHandler.gateway = CameraSdkGateway(Path(args.sdk_dir))
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print("Camera audio gateway listening on http://{}:{}".format(args.host, args.port))
    print(json.dumps(GatewayHandler.gateway.status(), ensure_ascii=False, indent=2))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
