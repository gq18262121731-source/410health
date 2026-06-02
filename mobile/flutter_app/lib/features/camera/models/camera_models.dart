enum CameraVideoMode {
  processed,
  raw,
}

class CameraSourceOption {
  final String cameraId;
  final String name;
  final bool enabled;
  final String source;
  final String sourceMode;

  const CameraSourceOption({
    required this.cameraId,
    required this.name,
    required this.enabled,
    required this.source,
    required this.sourceMode,
  });

  factory CameraSourceOption.fromJson(Map<String, dynamic> json) {
    return CameraSourceOption(
      cameraId: json['camera_id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Camera',
      enabled: json['enabled'] == true,
      source: json['source']?.toString() ?? '',
      sourceMode: json['source_mode']?.toString() ?? '',
    );
  }

  String get label => name.trim().isNotEmpty ? name.trim() : cameraId;
}

extension CameraVideoModeLabels on CameraVideoMode {
  String get label {
    return switch (this) {
      CameraVideoMode.processed => '处理后视频',
      CameraVideoMode.raw => '原视频',
    };
  }

  String get shortLabel {
    return switch (this) {
      CameraVideoMode.processed => '处理后',
      CameraVideoMode.raw => '原视频',
    };
  }
}

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
  final CameraOverlayStatus? processedOverlay;
  final CameraOverlayStatus? poseOverlay;
  final CameraOverlayStatus? fallOverlay;

  const CameraStreamStatus({
    required this.sourceFps,
    required this.measuredFps,
    required this.clients,
    this.lastError,
    this.processedOverlay,
    this.poseOverlay,
    this.fallOverlay,
  });

  factory CameraStreamStatus.fromJson(Map<String, dynamic> json) {
    return CameraStreamStatus(
      sourceFps: _toDouble(json['source_fps']) ?? 0,
      measuredFps: _toDouble(json['measured_fps']) ?? 0,
      clients: _toInt(json['clients']) ?? 0,
      lastError: json['last_error']?.toString(),
      processedOverlay: CameraOverlayStatus.fromDynamic(
        json['processed_overlay'],
      ),
      poseOverlay: CameraOverlayStatus.fromDynamic(json['pose_overlay']),
      fallOverlay: CameraOverlayStatus.fromDynamic(json['fall_overlay']),
    );
  }

  double get displayFps => sourceFps > 0 ? sourceFps : measuredFps;
}

class CameraVideoBridgeStatus {
  final String bridgeState;
  final String adapterVersion;
  final int cameraCount;
  final DateTime? updatedAt;
  final CameraVideoBridgeRecord? latest;
  final List<CameraVideoBridgeRecord> cameras;
  final List<String> notes;
  final CameraVisionServiceStatus visionService;

  const CameraVideoBridgeStatus({
    required this.bridgeState,
    required this.adapterVersion,
    required this.cameraCount,
    this.updatedAt,
    this.latest,
    required this.cameras,
    required this.notes,
    required this.visionService,
  });

  factory CameraVideoBridgeStatus.fromJson(Map<String, dynamic> json) {
    final latestMap = _toMap(json['latest']);
    return CameraVideoBridgeStatus(
      bridgeState: json['bridge_state']?.toString() ?? 'unknown',
      adapterVersion: json['adapter_version']?.toString() ?? 'unknown',
      cameraCount: _toInt(json['camera_count']) ?? 0,
      updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? ''),
      latest: latestMap == null
          ? null
          : CameraVideoBridgeRecord.fromJson(latestMap),
      cameras: _toList(json['cameras'])
          .map(_toMap)
          .whereType<Map<String, dynamic>>()
          .map(CameraVideoBridgeRecord.fromJson)
          .toList(growable: false),
      notes: _toList(json['notes'])
          .map((item) => item?.toString() ?? '')
          .where((item) => item.isNotEmpty)
          .toList(growable: false),
      visionService: CameraVisionServiceStatus.fromJson(
        _toMap(json['vision_service']) ?? const <String, dynamic>{},
      ),
    );
  }

  bool get isOnline =>
      bridgeState == 'running' ||
      bridgeState == 'mock' ||
      bridgeState == 'degraded';

  String get stateLabel {
    return switch (bridgeState) {
      'mock' => '预埋占位',
      'starting' => '启动中',
      'running' => '运行中',
      'degraded' => '降级运行',
      'stopped' => '已停止',
      'error' => '异常',
      _ => '未知',
    };
  }
}

class CameraVisionServiceStatus {
  final bool enabled;
  final String baseUrl;
  final String cameraId;
  final double pollHz;
  final DateTime? lastPollAt;
  final DateTime? lastOkAt;
  final String? lastError;
  final Map<String, dynamic>? health;
  final Map<String, dynamic>? source;
  final DateTime? latestReceivedAt;

  const CameraVisionServiceStatus({
    required this.enabled,
    required this.baseUrl,
    required this.cameraId,
    required this.pollHz,
    this.lastPollAt,
    this.lastOkAt,
    this.lastError,
    this.health,
    this.source,
    this.latestReceivedAt,
  });

  factory CameraVisionServiceStatus.fromJson(Map<String, dynamic> json) {
    return CameraVisionServiceStatus(
      enabled: json['enabled'] != false,
      baseUrl: json['base_url']?.toString() ?? '',
      cameraId: json['camera_id']?.toString() ?? 'camera_01',
      pollHz: _toDouble(json['poll_hz']) ?? 0,
      lastPollAt: DateTime.tryParse(json['last_poll_at']?.toString() ?? ''),
      lastOkAt: DateTime.tryParse(json['last_ok_at']?.toString() ?? ''),
      lastError: json['last_error']?.toString(),
      health: _toMap(json['health']),
      source: _toMap(json['source']),
      latestReceivedAt:
          DateTime.tryParse(json['latest_received_at']?.toString() ?? ''),
    );
  }

  bool get isConnected => lastOkAt != null && lastError == null;

  String get stateLabel {
    if (!enabled) return '未启用';
    if (isConnected) return '已连接';
    if (lastError != null && lastError!.isNotEmpty) return '连接异常';
    return '等待连接';
  }

  String sourceValue(String key) {
    final value = source?[key];
    if (value == null) return '--';
    return value.toString();
  }
}

class CameraVideoBridgeRecord {
  final String cameraId;
  final String streamName;
  final String serviceState;
  final bool cameraLost;
  final bool captureStale;
  final int? frameAgeMs;
  final double? videoFps;
  final double? overlayFps;
  final double? wsFps;
  final String streamType;
  final String? streamUrl;
  final String? trackId;
  final List<double> bbox;
  final Map<String, dynamic>? target;
  final String fallState;
  final String risk;
  final double? fallProb;
  final String? snapshotUrl;
  final DateTime? timestamp;
  final DateTime? receivedAt;
  final bool stale;
  final String adapterVersion;
  final Map<String, dynamic> metadata;

  const CameraVideoBridgeRecord({
    required this.cameraId,
    required this.streamName,
    required this.serviceState,
    required this.cameraLost,
    required this.captureStale,
    this.frameAgeMs,
    this.videoFps,
    this.overlayFps,
    this.wsFps,
    required this.streamType,
    this.streamUrl,
    this.trackId,
    required this.bbox,
    this.target,
    required this.fallState,
    required this.risk,
    this.fallProb,
    this.snapshotUrl,
    this.timestamp,
    this.receivedAt,
    required this.stale,
    required this.adapterVersion,
    required this.metadata,
  });

  factory CameraVideoBridgeRecord.fromJson(Map<String, dynamic> json) {
    return CameraVideoBridgeRecord(
      cameraId: json['camera_id']?.toString() ?? '',
      streamName: json['stream_name']?.toString() ?? 'primary',
      serviceState: json['service_state']?.toString() ?? 'unknown',
      cameraLost: json['camera_lost'] == true,
      captureStale: json['capture_stale'] == true,
      frameAgeMs: _toInt(json['frame_age_ms']),
      videoFps: _toDouble(json['video_fps']),
      overlayFps: _toDouble(json['overlay_fps']),
      wsFps: _toDouble(json['ws_fps']),
      streamType: json['stream_type']?.toString() ?? 'ws_image',
      streamUrl: json['stream_url']?.toString(),
      trackId: json['track_id']?.toString(),
      bbox: _toDoubleList(json['bbox']),
      target: _toMap(json['target']),
      fallState: json['fall_state']?.toString() ?? 'unknown',
      risk: json['risk']?.toString() ?? 'unknown',
      fallProb: _toDouble(json['fall_prob']),
      snapshotUrl: json['snapshot_url']?.toString(),
      timestamp: DateTime.tryParse(json['timestamp']?.toString() ?? ''),
      receivedAt: DateTime.tryParse(json['received_at']?.toString() ?? ''),
      stale: json['stale'] == true,
      adapterVersion: json['adapter_version']?.toString() ?? 'unknown',
      metadata: _toMap(json['metadata']) ?? const <String, dynamic>{},
    );
  }

  bool get isOnline =>
      !cameraLost &&
      !stale &&
      (serviceState == 'running' ||
          serviceState == 'mock' ||
          serviceState == 'degraded');

  bool get hasRisk => risk == 'high' || risk == 'critical';

  String get serviceStateLabel {
    return switch (serviceState) {
      'mock' => '占位源',
      'starting' => '启动中',
      'running' => '运行中',
      'degraded' => '降级运行',
      'stopped' => '已停止',
      'error' => '异常',
      _ => '未知',
    };
  }

  String get riskLabel {
    return switch (risk) {
      'low' => '低风险',
      'medium' => '中风险',
      'high' => '高风险',
      'critical' => '紧急风险',
      _ => '未知风险',
    };
  }

  String get fallStateLabel {
    return switch (fallState) {
      'normal' => '未见跌倒',
      'suspected_fall' => '疑似跌倒',
      'confirmed_fall' => '已确认跌倒',
      'fallen' => '倒地',
      'recovery' => '恢复中',
      'error' => '分析异常',
      _ => '等待分析',
    };
  }

  String get targetLabel {
    final targetMap = target;
    if (targetMap == null) return '未识别目标';
    final label = targetMap['label']?.toString();
    final targetId =
        targetMap['target_id']?.toString() ?? targetMap['user_id']?.toString();
    final matched = targetMap['matched'] == true;
    if (targetId != null && targetId.isNotEmpty) {
      return matched ? '已匹配 $targetId' : targetId;
    }
    if (label != null && label.isNotEmpty) return label;
    return matched ? '已匹配目标' : '未匹配目标';
  }

  String get displaySource =>
      metadata['display_source']?.toString() ?? '--';

  String get analysisSource =>
      metadata['analysis_source']?.toString() ?? streamName;

  int get poseKeypointCount {
    final value = metadata['pose_keypoint_count'];
    final parsed = _toInt(value);
    if (parsed != null) return parsed;
    final pose = _toMap(metadata['pose']);
    final keypoints = _toList(pose?['keypoints']);
    return keypoints.length;
  }
}

class CameraOverlayStatus {
  final String type;
  final bool hasRenderableOverlay;
  final bool posePayloadValid;
  final bool poseFallbackValid;
  final int poseTrackCount;
  final bool fallPayloadValid;
  final bool fallFallbackValid;
  final bool poseFallbackRunning;
  final bool fallFallbackRunning;

  const CameraOverlayStatus({
    required this.type,
    required this.hasRenderableOverlay,
    required this.posePayloadValid,
    required this.poseFallbackValid,
    required this.poseTrackCount,
    required this.fallPayloadValid,
    required this.fallFallbackValid,
    required this.poseFallbackRunning,
    required this.fallFallbackRunning,
  });

  factory CameraOverlayStatus.fromJson(Map<String, dynamic> json) {
    return CameraOverlayStatus(
      type: json['type']?.toString() ?? 'unknown',
      hasRenderableOverlay: json['has_renderable_overlay'] == true,
      posePayloadValid: json['pose_payload_valid'] == true,
      poseFallbackValid: json['pose_fallback_valid'] == true,
      poseTrackCount: _toInt(json['pose_track_count']) ?? 0,
      fallPayloadValid:
          json['fall_payload_valid'] == true || json['event_valid'] == true,
      fallFallbackValid:
          json['fall_fallback_valid'] == true || json['fallback_valid'] == true,
      poseFallbackRunning: json['pose_fallback_running'] == true,
      fallFallbackRunning: json['fall_fallback_running'] == true,
    );
  }

  static CameraOverlayStatus? fromDynamic(Object? value) {
    final map = _toMap(value);
    return map == null ? null : CameraOverlayStatus.fromJson(map);
  }

  String get label {
    if (hasRenderableOverlay) {
      if (poseTrackCount > 0) return '已绘制骨架 $poseTrackCount 个';
      if (fallPayloadValid || fallFallbackValid) return '已绘制跌倒框';
      return '已绘制处理标注';
    }
    if (poseFallbackRunning || fallFallbackRunning) return '正在生成处理标注';
    return '当前无可绘制目标';
  }
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
  final Map<String, dynamic>? decisionDebug;

  const CameraDetectionRuntimeStatus({
    required this.enabled,
    required this.running,
    required this.processRunning,
    this.pid,
    this.profile,
    this.lastError,
    this.lastEvent,
    this.multimodalReview,
    this.decisionDebug,
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
      decisionDebug: _toMap(json['decision_debug']),
    );
  }

  String get stateLabel {
    if (!enabled) return '未启用';
    if (processRunning) return '运行中';
    if (running) return '启动中';
    return '未运行';
  }

  bool get hasRenderableEvent {
    final event = lastEvent;
    if (event == null) return false;
    final bbox = event['bbox'];
    if (bbox is List && bbox.length >= 4) return true;
    final detections = event['detections'];
    if (detections is List && detections.isNotEmpty) return true;
    return false;
  }

  String get decisionStatusLabel {
    final debug = decisionDebug;
    if (debug == null) return '等待跌倒判定';
    final status = debug['status_label']?.toString() ?? '';
    switch (status) {
      case 'admitted':
        return '已形成正式跌倒告警';
      case 'deduped':
        return '同一跌倒事件已去重，避免重复弹窗';
      case 'suppressed':
      case 'suppressed_by_alarm_service':
        return '当前帧已识别异常，但未满足正式告警条件';
      case 'observing':
        return '疑似跌倒观察中，等待更多连续证据';
      default:
        return '等待跌倒判定';
    }
  }

  String get decisionReasonLabel {
    final debug = decisionDebug;
    if (debug == null) return '';
    final reasons = (debug['suppress_reasons'] is List)
        ? (debug['suppress_reasons'] as List)
            .map((item) => item?.toString() ?? '')
            .where((item) => item.isNotEmpty)
            .toList(growable: false)
        : const <String>[];
    if (reasons.isEmpty) return '';
    return '未触发原因：${reasons.join(" / ")}';
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
    final primaryWorker =
        _toMap(json['pose']) ?? _toMap(json['full']) ?? _toMap(json['fall']);
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

  bool get hasBBox => bbox.length >= 4;
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
