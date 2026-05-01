class CameraStatus {
  final bool configured;
  final bool online;
  final String? error;
  final String? ip;
  final int? port;
  final String? path;
  final double? latencyMs;

  const CameraStatus({
    required this.configured,
    required this.online,
    this.error,
    this.ip,
    this.port,
    this.path,
    this.latencyMs,
  });

  factory CameraStatus.fromJson(Map<String, dynamic> json) {
    return CameraStatus(
      configured: json['configured'] == true,
      online: json['online'] == true,
      error: json['error']?.toString(),
      ip: json['ip']?.toString(),
      port: _toInt(json['port']),
      path: json['path']?.toString(),
      latencyMs: _toDouble(json['latency_ms']),
    );
  }

  String get label {
    if (!configured) return '未配置';
    return online ? '在线' : '离线';
  }

  String get endpoint {
    if (ip == null || port == null || path == null) return '等待后端配置';
    return '$ip:$port$path';
  }
}

class CameraStreamStatus {
  final double sourceFps;
  final double measuredFps;
  final int clients;
  final String? lastError;

  const CameraStreamStatus({
    required this.sourceFps,
    required this.measuredFps,
    required this.clients,
    this.lastError,
  });

  factory CameraStreamStatus.fromJson(Map<String, dynamic> json) {
    return CameraStreamStatus(
      sourceFps: _toDouble(json['source_fps']) ?? 0,
      measuredFps: _toDouble(json['measured_fps']) ?? 0,
      clients: _toInt(json['clients']) ?? 0,
      lastError: json['last_error']?.toString(),
    );
  }

  double get displayFps => sourceFps > 0 ? sourceFps : measuredFps;
}

class CameraAudioStatus {
  final bool configured;
  final bool listenSupported;
  final bool talkSupported;
  final String? checkedUrl;
  final String? audioCodec;
  final int? sampleRate;
  final int? channels;
  final String? source;
  final String? error;

  const CameraAudioStatus({
    required this.configured,
    required this.listenSupported,
    required this.talkSupported,
    this.checkedUrl,
    this.audioCodec,
    this.sampleRate,
    this.channels,
    this.source,
    this.error,
  });

  factory CameraAudioStatus.fromJson(Map<String, dynamic> json) {
    return CameraAudioStatus(
      configured: json['configured'] == true,
      listenSupported: json['listen_supported'] == true,
      talkSupported: json['talk_supported'] == true,
      checkedUrl: json['checked_url']?.toString(),
      audioCodec: json['audio_codec']?.toString(),
      sampleRate: _toInt(json['sample_rate']),
      channels: _toInt(json['channels']),
      source: json['source']?.toString(),
      error: json['error']?.toString(),
    );
  }

  String get listenLabel {
    if (!configured) return '未配置';
    return listenSupported ? '可监听' : '暂不支持监听';
  }
}

int? _toInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}

double? _toDouble(Object? value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '');
}
