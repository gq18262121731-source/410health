import 'dart:async';
import 'dart:typed_data';

import 'camera_audio_player_base.dart';

CameraAudioPlayer createPlatformCameraAudioPlayer() => _WebCameraAudioPlayer();

class _WebCameraAudioPlayer implements CameraAudioPlayer {
  final StreamController<double> _levels = StreamController<double>.broadcast();

  @override
  bool get isSupported => false;

  @override
  String get unsupportedReason =>
      'Web PCM playback is temporarily disabled in this build to keep the mobile client stable.';

  @override
  Stream<double> get levels => _levels.stream;

  @override
  Future<void> start({required int sampleRate}) async {
    throw UnsupportedError(unsupportedReason);
  }

  @override
  void playPcm16(Uint8List bytes) {}

  @override
  Future<void> stop() async {}

  @override
  void dispose() {
    _levels.close();
  }
}
