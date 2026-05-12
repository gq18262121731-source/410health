import 'dart:typed_data';

abstract class CameraAudioPlayer {
  bool get isSupported;
  String? get unsupportedReason;
  Stream<double> get levels;

  Future<void> start({required int sampleRate});

  void playPcm16(Uint8List bytes);

  Future<void> stop();

  void dispose();
}
