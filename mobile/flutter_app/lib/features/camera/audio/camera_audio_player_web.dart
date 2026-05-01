import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:web_audio' as web_audio;

import 'camera_audio_player_base.dart';

CameraAudioPlayer createCameraAudioPlayer() => _WebCameraAudioPlayer();

class _WebCameraAudioPlayer implements CameraAudioPlayer {
  final StreamController<double> _levels = StreamController<double>.broadcast();

  web_audio.AudioContext? _context;
  int _sampleRate = 8000;
  double _nextTime = 0;

  @override
  bool get isSupported => true;

  @override
  String? get unsupportedReason => null;

  @override
  Stream<double> get levels => _levels.stream;

  @override
  Future<void> start({required int sampleRate}) async {
    _sampleRate = sampleRate <= 0 ? 8000 : sampleRate;
    _context ??= web_audio.AudioContext();
    if (_context!.state == 'suspended') {
      await _context!.resume();
    }
    _nextTime = _now(_context!) + 0.08;
  }

  @override
  void playPcm16(Uint8List bytes) {
    final context = _context;
    if (context == null || bytes.lengthInBytes < 2) return;

    final sampleCount = bytes.lengthInBytes ~/ 2;
    final byteData = bytes.buffer.asByteData(
      bytes.offsetInBytes,
      bytes.lengthInBytes,
    );
    final audioBuffer = context.createBuffer(1, sampleCount, _sampleRate);
    final channel = audioBuffer.getChannelData(0);

    double peak = 0;
    for (var i = 0; i < sampleCount; i += 1) {
      final value = byteData.getInt16(i * 2, Endian.little) / 32768.0;
      channel[i] = value;
      peak = math.max(peak, value.abs());
    }
    if (!_levels.isClosed) {
      _levels.add((peak * 100).clamp(0, 100).toDouble());
    }

    final source = context.createBufferSource();
    source.buffer = audioBuffer;
    final destination = context.destination;
    if (destination == null) return;
    source.connectNode(destination);

    final currentTime = _now(context);
    final startAt = math.max(currentTime + 0.02, _nextTime).toDouble();
    source.start(startAt);
    final duration =
        (audioBuffer.duration ?? sampleCount / _sampleRate).toDouble();
    _nextTime = startAt + duration;

    // 避免网络抖动后排队太长，宁可轻微丢帧也不要越听越延迟。
    if (_nextTime - currentTime > 0.6) {
      _nextTime = currentTime + 0.12;
    }
  }

  double _now(web_audio.AudioContext context) {
    return (context.currentTime ?? 0).toDouble();
  }

  @override
  Future<void> stop() async {
    _nextTime = 0;
    if (!_levels.isClosed) {
      _levels.add(0);
    }
  }

  @override
  void dispose() {
    _context?.close();
    _levels.close();
  }
}
