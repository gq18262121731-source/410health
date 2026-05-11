class CameraStatus {
  final bool configured;
  final bool online;
  final String? error;
  final String? ip;
  final int? port;
  final String? path;
  final double? latencyMs;
  final String? source;

  const CameraStatus({
    required this.configured,
    required this.online,
    this.error,
    this.ip,
    this.port,
    this.path,
    this.latencyMs,
    this.source,
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
      source: json['source']?.toString(),
    );
  }

  String get label {
    if (!configured) return '未配置';
    return online ? '在线' : '离线';
  }

  String get endpoint {
    if (ip == null || port == null || path == null) {
      return '等待后端摄像头配置';
    }
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
    return listenSupported ? '可监听' : '不可监听';
  }
}

class CameraSetupConfig {
  final String sourceMode;
  final int localIndex;
  final String localBackend;
  final String ip;
  final String user;
  final String password;
  final int rtspPort;
  final String rtspPath;
  final String streamRtspPath;
  final String audioRtspPath;
  final int onvifPort;

  const CameraSetupConfig({
    required this.sourceMode,
    required this.localIndex,
    required this.localBackend,
    required this.ip,
    required this.user,
    required this.password,
    required this.rtspPort,
    required this.rtspPath,
    required this.streamRtspPath,
    required this.audioRtspPath,
    required this.onvifPort,
  });

  factory CameraSetupConfig.fromJson(Map<String, dynamic> json) {
    return CameraSetupConfig(
      sourceMode: json['camera_source_mode']?.toString() ?? 'local',
      localIndex: _toInt(json['camera_local_index']) ?? 0,
      localBackend: json['camera_local_backend']?.toString() ?? 'any',
      ip: json['camera_ip']?.toString() ?? '',
      user: json['camera_user']?.toString() ?? 'admin',
      password: json['camera_password']?.toString() ?? '',
      rtspPort: _toInt(json['camera_rtsp_port']) ?? 10554,
      rtspPath: json['camera_rtsp_path']?.toString() ?? '/tcp/av0_0',
      streamRtspPath:
          json['camera_stream_rtsp_path']?.toString() ?? '/tcp/av0_1',
      audioRtspPath: json['camera_audio_rtsp_path']?.toString() ?? '/tcp/av0_1',
      onvifPort: _toInt(json['camera_onvif_port']) ?? 10080,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'camera_source_mode': sourceMode,
      'camera_local_index': localIndex,
      'camera_local_backend': localBackend,
      'camera_ip': ip,
      'camera_user': user,
      'camera_password': password,
      'camera_rtsp_port': rtspPort,
      'camera_rtsp_path': rtspPath,
      'camera_stream_rtsp_path': streamRtspPath,
      'camera_audio_rtsp_path': audioRtspPath,
      'camera_onvif_port': onvifPort,
    };
  }

  CameraSetupConfig copyWith({
    String? sourceMode,
    int? localIndex,
    String? localBackend,
    String? ip,
    String? user,
    String? password,
    int? rtspPort,
    String? rtspPath,
    String? streamRtspPath,
    String? audioRtspPath,
    int? onvifPort,
  }) {
    return CameraSetupConfig(
      sourceMode: sourceMode ?? this.sourceMode,
      localIndex: localIndex ?? this.localIndex,
      localBackend: localBackend ?? this.localBackend,
      ip: ip ?? this.ip,
      user: user ?? this.user,
      password: password ?? this.password,
      rtspPort: rtspPort ?? this.rtspPort,
      rtspPath: rtspPath ?? this.rtspPath,
      streamRtspPath: streamRtspPath ?? this.streamRtspPath,
      audioRtspPath: audioRtspPath ?? this.audioRtspPath,
      onvifPort: onvifPort ?? this.onvifPort,
    );
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
