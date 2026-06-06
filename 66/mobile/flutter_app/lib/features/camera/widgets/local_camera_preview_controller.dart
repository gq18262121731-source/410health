import 'package:flutter/widgets.dart';
import 'dart:typed_data';

abstract class LocalCameraPreviewController {
  bool get isSupported;

  Future<void> start();

  Future<void> stop();

  Widget build(BuildContext context);

  Future<Uint8List?> captureFrame();

  void dispose();
}
