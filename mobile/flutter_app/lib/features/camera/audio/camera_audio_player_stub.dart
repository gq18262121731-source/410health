import 'dart:async';
import 'dart:typed_data';

import 'camera_audio_player_base.dart';

CameraAudioPlayer createCameraAudioPlayer() => _UnsupportedCameraAudioPlayer();

class _UnsupportedCameraAudioPlayer implements CameraAudioPlayer {
  final StreamController<double> _levels = StreamController<double>.broadcast();

  @override
  bool get isSupported => false;

  @override
  String get unsupportedReason =>
      'Live camera audio playback is only available in the web preview for now.';

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
