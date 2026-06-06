import 'package:ai_health_iot_flutter/features/camera/models/camera_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('camera video mode labels match family camera switch text', () {
    expect(CameraVideoMode.processed.label, '处理后视频');
    expect(CameraVideoMode.processed.shortLabel, '处理后');
    expect(CameraVideoMode.raw.label, '原视频');
    expect(CameraVideoMode.raw.shortLabel, '原视频');
  });
}
