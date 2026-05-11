// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

import 'local_camera_preview_controller.dart';

class _WebLocalCameraPreviewController
    implements LocalCameraPreviewController {
  final ValueChanged<bool>? onReadyChanged;
  final ValueChanged<String?>? onErrorChanged;
  final String _viewType =
      'local-camera-preview-${DateTime.now().microsecondsSinceEpoch}';
  late final html.VideoElement _video;
  html.MediaStream? _stream;
  bool _registered = false;

  _WebLocalCameraPreviewController({
    this.onReadyChanged,
    this.onErrorChanged,
  }) {
    _video = html.VideoElement()
      ..autoplay = true
      ..muted = true
      ..setAttribute('playsinline', 'true')
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'cover'
      ..style.backgroundColor = '#0F172A';
  }

  @override
  bool get isSupported =>
      html.window.navigator.mediaDevices != null &&
      html.window.isSecureContext == true;

  @override
  Future<void> start() async {
    if (!isSupported) {
      onReadyChanged?.call(false);
      onErrorChanged?.call('浏览器需要 HTTPS 或 localhost 才能直接调用摄像头');
      return;
    }
    if (!_registered) {
      ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) => _video);
      _registered = true;
    }

    try {
      _stream ??= await html.window.navigator.mediaDevices!.getUserMedia({
        'video': {
          'width': {'ideal': 1280},
          'height': {'ideal': 720},
          'frameRate': {'ideal': 30, 'max': 30},
          'facingMode': 'user',
        },
        'audio': false,
      });
      _video.srcObject = _stream;
      await _video.play();
      onReadyChanged?.call(true);
      onErrorChanged?.call(null);
    } catch (error) {
      onReadyChanged?.call(false);
      onErrorChanged?.call('无法打开本地摄像头：$error');
    }
  }

  @override
  Future<void> stop() async {
    _video.pause();
    _video.srcObject = null;
    _stream?.getTracks().forEach((track) => track.stop());
    _stream = null;
    onReadyChanged?.call(false);
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }

  @override
  Future<Uint8List?> captureFrame() async {
    if (_video.videoWidth <= 0 || _video.videoHeight <= 0) {
      return null;
    }
    final canvas = html.CanvasElement(
      width: _video.videoWidth,
      height: _video.videoHeight,
    );
    final context = canvas.context2D;
    context.drawImageScaled(_video, 0, 0, _video.videoWidth, _video.videoHeight);
    final blob = await canvas.toBlob('image/jpeg', 0.82);
    final reader = html.FileReader();
    reader.readAsArrayBuffer(blob);
    await reader.onLoad.first;
    final result = reader.result;
    if (result is ByteBuffer) {
      return Uint8List.view(result);
    }
    return null;
  }

  @override
  void dispose() {
    stop();
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
