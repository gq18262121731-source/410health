import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_soloud/flutter_soloud.dart';

import 'camera_audio_player_base.dart';

class SoLoudCameraAudioPlayer implements CameraAudioPlayer {
  static Future<void>? _initFuture;

  final StreamController<double> _levels = StreamController<double>.broadcast();
  Timer? _decayTimer;
  AudioSource? _source;
  SoundHandle? _handle;
  bool _started = false;
  double _lastLevel = 0;
  int _sampleRate = 8000;

  @override
  bool get isSupported => true;

  @override
  String? get unsupportedReason => null;

  @override
  Stream<double> get levels => _levels.stream;

  @override
  Future<void> start({required int sampleRate}) async {
    await _ensureInitialized();
    await stop();
    _sampleRate = sampleRate <= 0 ? 8000 : sampleRate;
    _source = SoLoud.instance.setBufferStream(
      maxBufferSizeDuration: const Duration(seconds: 6),
      bufferingType: BufferingType.preserved,
      bufferingTimeNeeds: 0.35,
      sampleRate: _sampleRate,
      channels: Channels.mono,
      format: BufferType.s16le,
    );
    _started = false;
    _lastLevel = 0;
    _emitLevel(0);
    _startDecayTimer();
  }

  @override
  void playPcm16(Uint8List bytes) {
    final source = _source;
    if (source == null || bytes.isEmpty) {
      return;
    }

    try {
      SoLoud.instance.addAudioDataStream(source, bytes);
      if (!_started) {
        _handle = SoLoud.instance.play(source, volume: 0.9);
        _started = true;
      }
      _lastLevel = math.max(_computePeak(bytes), _lastLevel * 0.65);
      _emitLevel(_lastLevel);
    } catch (_) {
      // Keep the UI alive even if a chunk is rejected because the stream buffer is rotating.
    }
  }

  @override
  Future<void> stop() async {
    _decayTimer?.cancel();
    _decayTimer = null;
    final handle = _handle;
    final source = _source;
    _handle = null;
    _source = null;
    _started = false;
    _lastLevel = 0;
    _emitLevel(0);

    if (!SoLoud.instance.isInitialized) {
      return;
    }

    if (source != null) {
      try {
        SoLoud.instance.setDataIsEnded(source);
      } catch (_) {}
    }
    if (handle != null) {
      try {
        await SoLoud.instance.stop(handle);
      } catch (_) {}
    }
    if (source != null) {
      try {
        await SoLoud.instance.disposeSource(source);
      } catch (_) {}
    }
  }

  @override
  void dispose() {
    unawaited(stop());
    if (!_levels.isClosed) {
      _levels.close();
    }
  }

  static Future<void> _ensureInitialized() async {
    if (SoLoud.instance.isInitialized) {
      return;
    }
    _initFuture ??= SoLoud.instance.init();
    await _initFuture;
  }

  void _startDecayTimer() {
    _decayTimer?.cancel();
    _decayTimer = Timer.periodic(const Duration(milliseconds: 120), (_) {
      if (_lastLevel <= 0.4) {
        _lastLevel = 0;
      } else {
        _lastLevel *= 0.82;
      }
      _emitLevel(_lastLevel);
    });
  }

  double _computePeak(Uint8List bytes) {
    if (bytes.lengthInBytes < 2) {
      return 0;
    }
    final byteData =
        bytes.buffer.asByteData(bytes.offsetInBytes, bytes.lengthInBytes);
    final sampleCount = bytes.lengthInBytes ~/ 2;
    double peak = 0;
    for (var index = 0; index < sampleCount; index += 1) {
      final value = byteData.getInt16(index * 2, Endian.little).abs() / 32768.0;
      if (value > peak) {
        peak = value;
      }
    }
    return peak * 100;
  }

  void _emitLevel(double level) {
    if (_levels.isClosed) {
      return;
    }
    _levels.add(level.clamp(0, 100));
  }
}
