# P2P Readonly CGI Verification - 2026-05-29

## Scope

This document closes the P2P `writeCgi` readonly verification branch.

The current project mainline returns to RTSP/video runtime metrics in `video_adapter` / `video_bridge` and `/status`. Camera configuration changes are explicitly out of scope for this stage.

## Verified P2P Context

- Virtual device ID: `AAC2621503XMSV`
- Resolved P2P client ID: `VSTK741568WWXWW`
- Resolution endpoint: `https://vuid.eye4.cn?vuid=AAC2621503XMSV`
- SDK initialization: `VSTK` prefix server parameter
- Android JNI path: `com.vstarcam.JNIApi`
- Verified sequence: `init -> create -> connect -> login -> writeCgi`
- Observed result: `connect result=3`, `login result=true`, `writeCgi result=true`

## Available Readonly CGI

The only verified useful readonly CGI is:

```text
get_status.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***
```

It returns a status blob of about `2410` bytes and includes device/runtime fields such as:

- `deviceid="VSTK741568WWXWW"`
- `realdeviceid="AAC2621503XMSV"`
- `sys_ver="10.194.120.53"`
- `app_version="ZH120.8.53.22"`
- `sensor_name="os02n10"`
- `sensor_width=2304`
- `sensor_hight=1296`
- `support_record_resolution_switch=1`
- `support_rtspTls=1`

It does not expose `enc_framerate`, `sub_enc_framerate`, `fps`, `bitrate`, or per-stream encoding profiles.

## Verified Unsupported CGI

The following readonly candidates were tested through the working `writeCgi` path and returned a 24-byte response containing `result=-2`:

- `get_factory_param.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_camera_params.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_params.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_rtsp.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_video_params.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_media.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_videostream.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_livestream.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_misc.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `get_wifi.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `videostream.cgi?cmd=get&loginuse=admin&loginpas=***&user=admin&pwd=***`
- `livestream.cgi?cmd=get&loginuse=admin&loginpas=***&user=admin&pwd=***`
- `media_info.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `video_info.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `system_status.cgi?loginuse=admin&loginpas=***&user=admin&pwd=***`
- `camera_control.cgi?param=104&loginuse=admin&loginpas=***&user=admin&pwd=***`
- `camera_control.cgi?param=104&value=0&loginuse=admin&loginpas=***&user=admin&pwd=***`

## Why CGI Guessing Stops Here

- The P2P connection and login path is already proven, so the `result=-2` responses are not caused by failed login.
- Common RTSP/video/media CGI names are not accepted by this firmware through the exposed Android `writeCgi` API.
- The Android APK exposes only `writeCgi`, `checkMode`, and `checkBuffer`; it does not expose `PPPPGetSystemParams`.
- The older vendor SDK suggests basic camera parameters are read through native `PPPPGetSystemParams(MSG_TYPE_GET_CAMERA_PARAMS)`, not through the tested CGI strings.
- Continuing to guess unknown CGI names increases risk without improving the main project objective.

If true vendor-side encoding parameters are needed later, open a separate branch for the old Android SDK `vstc2_jni` / `PPPPGetSystemParams` path. Do not mix that work into the RTSP/video runtime mainline.

## Mainline Runtime Metrics

From this point, the system should use measured RTSP/runtime metrics as the source of truth for video status:

- `capture_fps`: measured fresh frames received by the capture worker.
- `source_fps`: RTSP/OpenCV/FFmpeg declared or probed source FPS.
- `processed_fps`: downstream processing FPS, normally detection/analysis worker FPS.
- `broadcast_fps`: frames sent to playback clients or WebRTC render/output cadence.
- `frame_age_ms`: age of the latest fresh frame.
- `reconnect_count`: capture reconnect/restart count.
- `last_error`: latest capture or stream error.
- `stream_width`: measured frame width.
- `stream_height`: measured frame height.

Do not present repeated render FPS as fresh camera FPS. Display/render FPS and fresh capture FPS must remain separate fields.

## `/status` Field Mapping Suggestion

Current backend fields already cover most of the required runtime indicators:

| Target field | Current source |
| --- | --- |
| `capture_fps` | `/status.main_stream.capture_fps`, `/status.analysis_stream.capture_fps`, or `/status.cameras[].capture_fps` |
| `source_fps` | `/status.cameras[].capture_process_source_fps` |
| `processed_fps` | `/status.pipeline.detection_worker_fps` or `/status.detection[].detection_fps` |
| `broadcast_fps` | Not currently explicit; add later from WebRTC/video bridge send loop if needed |
| `frame_age_ms` | `/status.main_stream.frame_age_ms`, `/status.analysis_stream.frame_age_ms`, or `/status.cameras[].frame_age_ms` |
| `reconnect_count` | `/status.main_stream.restart_count`, `/status.analysis_stream.restart_count`, or `/status.cameras[].reconnect_count` |
| `last_error` | `/status.main_stream.last_error`, `/status.analysis_stream.last_error`, `/status.cameras[].last_error`, `/status.cameras[].capture_process_last_error` |
| `stream_width` | `/status.main_stream.frame_width`, `/status.analysis_stream.frame_width`, or `/status.cameras[].frame_width` |
| `stream_height` | `/status.main_stream.frame_height`, `/status.analysis_stream.frame_height`, or `/status.cameras[].frame_height` |

Recommended presentation split:

- `fresh_capture_fps`: use capture worker FPS.
- `declared_source_fps`: use capture process source FPS.
- `processed_fps`: use detection/analysis worker FPS.
- `broadcast_fps`: add only when measured at WebRTC/video bridge output.
- `render_fps`: frontend-only metric, never treated as camera fresh FPS.

## Logs

- Summary report: `D:\vision_service\logs\runtime_debug\p2p_writecgi_android\p2p_readonly_cgi_enum_report_20260529.txt`
- Initial enum logs: `D:\vision_service\logs\runtime_debug\p2p_writecgi_android\enum_readonly_20260529`
- Escaped auth enum logs: `D:\vision_service\logs\runtime_debug\p2p_writecgi_android\enum_readonly_escaped_20260529`
- Camera-control enum logs: `D:\vision_service\logs\runtime_debug\p2p_writecgi_android\camera_control_readonly_20260529`
- Android probe APK: `D:\vision_service\logs\runtime_debug\p2p_writecgi_android\p2p-readcgi.apk`

