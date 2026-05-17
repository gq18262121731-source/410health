// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:async';
import 'dart:convert';
import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

import 'local_camera_preview_controller.dart';

class _WebLocalCameraPreviewController implements LocalCameraPreviewController {
  final ValueChanged<bool>? onReadyChanged;
  final ValueChanged<String?>? onErrorChanged;
  final String _viewType =
      'local-camera-preview-${DateTime.now().microsecondsSinceEpoch}';
  late final html.VideoElement _video;
  late final html.CanvasElement _canvas;
  html.MediaStream? _stream;
  bool _registered = false;
  bool _disposed = false;
  int? _renderHandle;

  _WebLocalCameraPreviewController({
    this.onReadyChanged,
    this.onErrorChanged,
  }) {
    _video = html.VideoElement()
      ..autoplay = true
      ..muted = true
      ..setAttribute('playsinline', 'true')
      ..setAttribute('webkit-playsinline', 'true')
      ..style.display = 'block'
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'cover'
      ..style.position = 'absolute'
      ..style.left = '0'
      ..style.top = '0'
      ..style.zIndex = '1'
      ..style.pointerEvents = 'auto'
      ..style.backgroundColor = '#0F172A';
    _canvas = html.CanvasElement()
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.display = 'none'
      ..style.position = 'absolute'
      ..style.left = '0'
      ..style.top = '0'
      ..style.zIndex = '0'
      ..style.backgroundColor = '#0F172A';
  }

  @override
  bool get isSupported =>
      html.window.navigator.mediaDevices != null &&
      html.window.isSecureContext == true;

  @override
  Future<void> start() async {
    if (_disposed) return;
    // ignore: avoid_print
    print('[LocalCameraPreviewWeb] start supported=$isSupported registered=$_registered');

    if (!isSupported) {
      _notifyReady(false);
      _notifyError('浏览器需要 HTTPS 或 localhost 才能直接调用摄像头');
      return;
    }
    if (!_registered) {
      ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) {
        final wrapper = html.DivElement()
          ..style.width = '100%'
          ..style.height = '100%'
          ..style.position = 'relative'
          ..style.overflow = 'hidden'
          ..style.backgroundColor = '#0F172A';
        wrapper.children.clear();
        wrapper.children.add(_canvas);
        wrapper.children.add(_video);
        return wrapper;
      });
      _registered = true;
    }

    try {
      final existingStream = _stream;
      final stream = existingStream ??
          await html.window.navigator.mediaDevices!.getUserMedia({
            'video': {
              'width': {'ideal': 960},
              'height': {'ideal': 540},
              'frameRate': {'ideal': 20, 'max': 24},
            },
            'audio': false,
          });
      // ignore: avoid_print
      print('[LocalCameraPreviewWeb] getUserMedia ok tracks=${stream.getTracks().length}');

      if (_disposed) {
        if (existingStream == null) {
          _stopStreamTracks(stream);
        }
        return;
      }

      _stream = stream;
      _video.srcObject = stream;
      await _video.play();
      // ignore: avoid_print
      print('[LocalCameraPreviewWeb] play ok display=${_video.style.display} size=${_video.videoWidth}x${_video.videoHeight}');
      _notifyReady(true);
      _notifyError(null);
    } catch (error) {
      // ignore: avoid_print
      print('[LocalCameraPreviewWeb] start failed error=$error');
      _notifyReady(false);
      _notifyError(_humanizeOpenError(error));
    }
  }

  @override
  Future<void> stop() async {
    _stopCurrentStream(notify: true);
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }

  @override
  Future<Uint8List?> captureFrame() async {
    if (_disposed || _stream == null) {
      return null;
    }

    try {
      if (_video.videoWidth <= 0 || _video.videoHeight <= 0) {
        await _video.onLoadedMetadata.first.timeout(
          const Duration(milliseconds: 800),
          onTimeout: () => html.Event('timeout'),
        );
      }
      if (_video.videoWidth <= 0 || _video.videoHeight <= 0) {
        _notifyError('摄像头画面尚未就绪，暂时无法抽帧');
        return null;
      }

      final canvas = html.CanvasElement(
        width: _analysisWidth,
        height: _analysisHeight,
      );
      final context = canvas.context2D;
      context.drawImageScaled(
        _video,
        0,
        0,
        _analysisWidth,
        _analysisHeight,
      );
      final bytes = await _encodeCanvasToBytes(canvas);
      if (bytes != null && bytes.isNotEmpty) {
        _notifyError(null);
        return bytes;
      }
      _notifyError('本地视频抽帧失败：浏览器没有返回图像数据');
    } catch (error) {
      _notifyError('本地视频抽帧失败：$error');
    }
    return null;
  }

  Future<Uint8List?> _encodeCanvasToBytes(html.CanvasElement canvas) async {
    try {
      final blob = await canvas.toBlob('image/jpeg');
      if (blob != null) {
        final completer = Completer<Uint8List?>();
        final reader = html.FileReader();
        reader.onLoadEnd.listen((_) {
          final result = reader.result;
          if (result is ByteBuffer) {
            completer.complete(result.asUint8List());
          } else if (result is Uint8List) {
            completer.complete(result);
          } else {
            completer.complete(null);
          }
        });
        reader.onError.listen((_) => completer.complete(null));
        reader.readAsArrayBuffer(blob);
        final bytes = await completer.future.timeout(
          const Duration(milliseconds: 800),
          onTimeout: () => null,
        );
        if (bytes != null && bytes.isNotEmpty) {
          return bytes;
        }
      }
    } catch (_) {
      // ignore and use the data-url fallback
    }

    final dataUrl = canvas.toDataUrl('image/jpeg', 0.72);
    final commaIndex = dataUrl.indexOf(',');
    if (commaIndex > 0) {
      return base64Decode(dataUrl.substring(commaIndex + 1));
    }
    return null;
  }

  int get _analysisWidth {
    final width = _video.videoWidth;
    if (width <= 0) return 640;
    return width > 640 ? 640 : width;
  }

  int get _analysisHeight {
    final width = _video.videoWidth;
    final height = _video.videoHeight;
    if (width <= 0 || height <= 0) return 360;
    return ((height * _analysisWidth) / width).round().clamp(1, 720);
  }

  @override
  void dispose() {
    _disposed = true;
    _stopCurrentStream(notify: false);
  }

  void _stopCurrentStream({required bool notify}) {
    _video.pause();
    _video.srcObject = null;

    final stream = _stream;
    _stream = null;
    if (stream != null) {
      _stopStreamTracks(stream);
    }

    if (notify) {
      _notifyReady(false);
    }
  }

  void _stopStreamTracks(html.MediaStream stream) {
    final tracks = stream.getTracks();
    for (var index = 0; index < tracks.length; index += 1) {
      tracks[index].stop();
    }
  }

  void _notifyReady(bool ready) {
    if (!_disposed) {
      onReadyChanged?.call(ready);
    }
  }

  void _notifyError(String? error) {
    if (!_disposed) {
      onErrorChanged?.call(error);
    }
  }

  String _humanizeOpenError(Object error) {
    final raw = error.toString();
    if (raw.contains('NotAllowedError') || raw.contains('Permission denied')) {
      return '浏览器摄像头权限被拒绝，请点击地址栏摄像头图标并允许访问。';
    }
    if (raw.contains('NotFoundError') || raw.contains('DevicesNotFoundError')) {
      return '没有找到可用摄像头，请确认摄像头已连接并未被禁用。';
    }
    if (raw.contains('NotReadableError') || raw.contains('TrackStartError')) {
      return '摄像头可能被微信、会议软件或其他浏览器占用，请关闭占用程序后刷新页面。';
    }
    if (raw.contains('OverconstrainedError')) {
      return '摄像头不支持当前分辨率或帧率，已放宽参数，请刷新页面重试。';
    }
    if (raw.contains('SecurityError')) {
      return '当前页面不允许调用摄像头，请使用 http://127.0.0.1:5182 或 HTTPS。';
    }
    return '无法打开本地摄像头：$raw';
  }
}

LocalCameraPreviewController createLocalCameraPreviewController({
  ValueChanged<bool>? onReadyChanged,
  ValueChanged<String?>? onErrorChanged,
}) {
  return _WebLocalCameraPreviewController(
    onReadyChanged: onReadyChanged,
    onErrorChanged: onErrorChanged,
  );
}
