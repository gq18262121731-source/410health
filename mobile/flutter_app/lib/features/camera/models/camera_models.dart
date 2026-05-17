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
  final double captureFps;
  final double sourceFps;
  final double measuredFps;
  final double broadcastFps;
  final double mjpegFps;
  final int clients;
  final int mjpegClients;
  final int mjpegTotal;
  final int mjpegBytesTotal;
  final String? activeUrl;
  final String? lastError;

  const CameraStreamStatus({
    required this.captureFps,
    required this.sourceFps,
    required this.measuredFps,
    required this.broadcastFps,
    required this.mjpegFps,
    required this.clients,
    required this.mjpegClients,
    required this.mjpegTotal,
    required this.mjpegBytesTotal,
    this.activeUrl,
    this.lastError,
  });

  factory CameraStreamStatus.fromJson(Map<String, dynamic> json) {
    return CameraStreamStatus(
      captureFps: _toDouble(json['capture_fps']) ?? 0,
      sourceFps: _toDouble(json['source_fps']) ?? 0,
      measuredFps: _toDouble(json['measured_fps']) ?? 0,
      broadcastFps: _toDouble(json['broadcast_fps']) ?? 0,
      mjpegFps: _toDouble(json['mjpeg_fps']) ?? 0,
      clients: _toInt(json['clients']) ?? 0,
      mjpegClients: _toInt(json['mjpeg_clients']) ?? 0,
      mjpegTotal: _toInt(json['mjpeg_total']) ?? 0,
      mjpegBytesTotal: _toInt(json['mjpeg_bytes_total']) ?? 0,
      activeUrl: json['active_url']?.toString(),
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

class CameraDetectionRuntimeStatus {
  final bool enabled;
  final bool running;
  final bool processRunning;
  final int? pid;
  final String? profile;
  final String? lastError;
  final Map<String, dynamic>? lastEvent;
  final Map<String, dynamic>? multimodalReview;

  const CameraDetectionRuntimeStatus({
    required this.enabled,
    required this.running,
    required this.processRunning,
    this.pid,
    this.profile,
    this.lastError,
    this.lastEvent,
    this.multimodalReview,
  });

  factory CameraDetectionRuntimeStatus.fromJson(Map<String, dynamic> json) {
    return CameraDetectionRuntimeStatus(
      enabled: json['enabled'] == true,
      running: json['running'] == true,
      processRunning: json['process_running'] == true,
      pid: _toInt(json['pid']),
      profile: json['profile']?.toString(),
      lastError: json['last_error']?.toString(),
      lastEvent: _toMap(json['last_event']),
      multimodalReview: _toMap(json['multimodal_review']),
    );
  }

  String get stateLabel {
    if (!enabled) return '未启用';
    if (processRunning) return '运行中';
    if (running) return '启动中';
    return '未运行';
  }
}

class CameraFrameAnalysisStatus {
  final bool enabled;
  final bool running;
  final int? pid;
  final String? lastError;
  final double? lastOkAt;
  final int restartCount;
  final double timeoutSeconds;

  const CameraFrameAnalysisStatus({
    required this.enabled,
    required this.running,
    this.pid,
    this.lastError,
    this.lastOkAt,
    required this.restartCount,
    required this.timeoutSeconds,
  });

  factory CameraFrameAnalysisStatus.fromJson(Map<String, dynamic> json) {
    final primaryWorker = _toMap(json['pose']) ??
        _toMap(json['full']) ??
        _toMap(json['fall']);
    if (primaryWorker != null) {
      return CameraFrameAnalysisStatus(
        enabled: json['enabled'] != false,
        running: primaryWorker['running'] == true,
        pid: _toInt(primaryWorker['pid']),
        lastError: primaryWorker['last_error']?.toString(),
        lastOkAt: _toDouble(primaryWorker['last_ok_at']),
        restartCount: _toInt(primaryWorker['restart_count']) ?? 0,
        timeoutSeconds: _toDouble(primaryWorker['timeout_seconds']) ?? 20,
      );
    }
    return CameraFrameAnalysisStatus(
      enabled: json['enabled'] == true,
      running: json['running'] == true,
      pid: _toInt(json['pid']),
      lastError: json['last_error']?.toString(),
      lastOkAt: _toDouble(json['last_ok_at']),
      restartCount: _toInt(json['restart_count']) ?? 0,
      timeoutSeconds: _toDouble(json['timeout_seconds']) ?? 20,
    );
  }

  String get stateLabel {
    if (!enabled) return '接口未启用';
    if (running) return 'worker 已启动';
    return '等待首帧启动';
  }
}

class PoseDetectionLatest {
  final String? backend;
  final String? profile;
  final int frameWidth;
  final int frameHeight;
  final List<PoseTrack> tracks;

  const PoseDetectionLatest({
    this.backend,
    this.profile,
    required this.frameWidth,
    required this.frameHeight,
    required this.tracks,
  });

  factory PoseDetectionLatest.fromJson(Map<String, dynamic> json) {
    final rawTracks = _toList(json['tracks']);
    return PoseDetectionLatest(
      backend: json['backend']?.toString(),
      profile: json['profile']?.toString(),
      frameWidth: _toInt(json['frame_width']) ?? 640,
      frameHeight: _toInt(json['frame_height']) ?? 480,
      tracks: rawTracks
          .map(_toMap)
          .whereType<Map<String, dynamic>>()
          .map(PoseTrack.fromJson)
          .toList(),
    );
  }

  PoseTrack? get primaryTrack => tracks.isEmpty ? null : tracks.first;

  String get postureLabel {
    final label = primaryTrack?.stateLabel;
    if (label == null || label.isEmpty) return '暂无目标';
    return switch (label) {
      'upright' => '正常站立/活动',
      'leaning' => '弯腰/前倾',
      'slumped' => '低位姿态',
      'fall_like' => '疑似跌倒姿态',
      'hand_to_chest_or_abdomen' => '手部靠近胸腹',
      'unknown' => '姿态不明确',
      'normal_activity' => '正常站立/活动',
      'low_posture' => '低位姿态',
      'floor_risk' => '地面停留风险',
      _ => label,
    };
  }
}

class PoseTrack {
  final int trackId;
  final List<double> bbox;
  final double poseScore;
  final String stateLabel;
  final double stateScore;
  final List<PoseKeypoint> keypoints;
  final Map<String, dynamic> features;

  const PoseTrack({
    required this.trackId,
    required this.bbox,
    required this.poseScore,
    required this.stateLabel,
    required this.stateScore,
    required this.keypoints,
    required this.features,
  });

  factory PoseTrack.fromJson(Map<String, dynamic> json) {
    return PoseTrack(
      trackId: _toInt(json['track_id']) ?? 0,
      bbox: _toDoubleList(json['bbox']),
      poseScore: _toDouble(json['pose_score']) ?? 0,
      stateLabel: json['state_label']?.toString() ?? 'unknown',
      stateScore: _toDouble(json['state_score']) ?? 0,
      keypoints: _toList(json['keypoints'])
          .map(PoseKeypoint.fromRaw)
          .whereType<PoseKeypoint>()
          .toList(),
      features: _toMap(json['features']) ?? const <String, dynamic>{},
    );
  }

  bool get isRisk => stateLabel == 'floor_risk' || stateLabel == 'fall_like';

  bool get isWarning =>
      stateLabel == 'low_posture' ||
      stateLabel == 'leaning' ||
      stateLabel == 'slumped' ||
      stateLabel == 'hand_to_chest_or_abdomen';

  String get eventLabel {
    return switch (stateLabel) {
      'floor_risk' => '地面停留风险',
      'fall_like' => '疑似跌倒姿态',
      'low_posture' || 'slumped' => '低位姿态',
      'leaning' => '弯腰/前倾动作',
      'hand_to_chest_or_abdomen' => '手部靠近胸腹',
      'upright' || 'normal_activity' => '正常活动',
      'unknown' => '人体姿态不明确',
      _ => stateLabel,
    };
  }
}

class PoseKeypoint {
  final double x;
  final double y;
  final double confidence;

  const PoseKeypoint({
    required this.x,
    required this.y,
    required this.confidence,
  });

  static PoseKeypoint? fromRaw(Object? raw) {
    final values = _toDoubleList(raw);
    if (values.length < 2) return null;
    return PoseKeypoint(
      x: values[0],
      y: values[1],
      confidence: values.length >= 3 ? values[2] : 1,
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

Map<String, dynamic>? _toMap(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

List<dynamic> _toList(Object? value) {
  if (value is List) return value;
  return const <dynamic>[];
}

List<double> _toDoubleList(Object? value) {
  return _toList(value)
      .map(_toDouble)
      .whereType<double>()
      .toList(growable: false);
}
