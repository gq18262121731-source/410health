import 'package:flutter/widgets.dart';
import 'dart:typed_data';

import 'local_camera_preview_controller.dart';

LocalCameraPreviewController createLocalCameraPreviewController({
  ValueChanged<bool>? onReadyChanged,
  ValueChanged<String?>? onErrorChanged,
}) {
  return _UnsupportedLocalCameraPreviewController(
    onReadyChanged: onReadyChanged,
    onErrorChanged: onErrorChanged,
  );
}

class _UnsupportedLocalCameraPreviewController
    implements LocalCameraPreviewController {
  final ValueChanged<bool>? onReadyChanged;
  final ValueChanged<String?>? onErrorChanged;

  _UnsupportedLocalCameraPreviewController({
    this.onReadyChanged,
    this.onErrorChanged,
  });

  @override
  bool get isSupported => false;

  @override
  Future<void> start() async {
    onReadyChanged?.call(false);
    onErrorChanged?.call('LOCAL_CAMERA_PREVIEW_WEB_ONLY');
  }

  @override
  Future<void> stop() async {
    onReadyChanged?.call(false);
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();

  @override
  Future<Uint8List?> captureFrame() async => null;

  @override
  void dispose() {}
}
