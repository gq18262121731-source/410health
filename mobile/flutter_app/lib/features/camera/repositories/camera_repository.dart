import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/server_endpoint_config.dart';
import '../models/camera_models.dart';

class CameraRepository {
  final ApiClient _apiClient;
  final ServerEndpointConfig _endpointConfig;

  CameraRepository(
    this._apiClient, {
    required ServerEndpointConfig endpointConfig,
  }) : _endpointConfig = endpointConfig;

  Future<CameraStatus> getStatus() async {
    final response = await _apiClient.get('camera/status');
    return CameraStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<CameraStreamStatus> getStreamStatus() async {
    final response = await _apiClient.get('camera/stream-status');
    return CameraStreamStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<List<CameraSourceOption>> listCameraSources() async {
    final response = await _apiClient.get('camera-sources');
    final payload = Map<String, dynamic>.from(response.data as Map);
    final sources = payload['sources'] as List? ?? const [];
    return sources
        .whereType<Map>()
        .map((item) => CameraSourceOption.fromJson(Map<String, dynamic>.from(item)))
        .toList(growable: false);
  }

  Future<CameraVideoBridgeStatus> getVideoBridgeStatus() async {
    final response = await _apiClient.get('video-bridge/status');
    return CameraVideoBridgeStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<Map<String, dynamic>> pollVisionServiceOnce() async {
    final response = await _apiClient.post(
      'video-bridge/vision/poll-once',
      options: Options(receiveTimeout: const Duration(seconds: 8)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> probeVisionStream({
    required String host,
    int port = 10554,
    int timeoutMs = 1500,
  }) async {
    final response = await _apiClient.post(
      'video-bridge/vision/probe',
      data: <String, dynamic>{
        'host': host,
        'port': port,
        'timeout_ms': timeoutMs,
      },
      options: Options(receiveTimeout: const Duration(seconds: 10)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> switchVisionHost({
    required String host,
    String cameraId = 'camera_01',
    String username = 'admin',
    String password = '',
    int port = 10554,
    String mainPath = '/tcp/av0_0',
    String analysisPath = '/tcp/av0_1',
  }) async {
    final response = await _apiClient.post(
      'video-bridge/vision/switch-host',
      data: <String, dynamic>{
        'camera_id': cameraId,
        'host': host,
        'username': username,
        'password': password,
        'port': port,
        'main_path': mainPath,
        'analysis_path': analysisPath,
      },
      options: Options(receiveTimeout: const Duration(seconds: 15)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<CameraAudioStatus> getAudioStatus() async {
    final response = await _apiClient.get('camera/audio/status');
    return CameraAudioStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<Map<String, CameraDetectionRuntimeStatus>>
      getDetectionModelsStatus() async {
    final response = await _apiClient.get('camera/detection-models/status');
    return _parseDetectionModelsStatus(response.data);
  }

  Future<Map<String, CameraDetectionRuntimeStatus>> setDetectionModelsEnabled({
    bool? fallDetectionEnabled,
    bool? poseDetectionEnabled,
  }) async {
    final response = await _apiClient.post(
      'camera/detection-models/enabled',
      data: <String, dynamic>{
        if (fallDetectionEnabled != null)
          'fall_detection_enabled': fallDetectionEnabled,
        if (poseDetectionEnabled != null)
          'pose_detection_enabled': poseDetectionEnabled,
      },
    );
    return _parseDetectionModelsStatus(response.data);
  }

  Future<CameraDetectionRuntimeStatus> getFallDetectionStatus() async {
    final response = await _apiClient.get('camera/fall-detection/status');
    return CameraDetectionRuntimeStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<CameraDetectionRuntimeStatus> setFallDetectionEnabled(
      bool enabled) async {
    final statuses = await setDetectionModelsEnabled(
      fallDetectionEnabled: enabled,
    );
    return statuses['fall_detection']!;
  }

  Future<CameraDetectionRuntimeStatus> getPoseDetectionStatus() async {
    final response = await _apiClient.get('camera/pose-detection/status');
    return CameraDetectionRuntimeStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<CameraDetectionRuntimeStatus> setPoseDetectionEnabled(
      bool enabled) async {
    final statuses = await setDetectionModelsEnabled(
      poseDetectionEnabled: enabled,
    );
    return statuses['pose_detection']!;
  }

  Future<Map<String, dynamic>> simulateFallDetection({
    String scenario = 'critical',
    double? fallScore,
    String trackId = 'family-mobile-demo',
  }) async {
    final response = await _apiClient.post(
      'camera/fall-detection/simulate',
      data: <String, dynamic>{
        'scenario': scenario,
        if (fallScore != null) 'fall_score': fallScore,
        'track_id': trackId,
      },
      options: Options(receiveTimeout: const Duration(seconds: 20)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<PoseDetectionLatest> getPoseDetectionLatest() async {
    final response = await _apiClient.get('camera/pose-detection/latest');
    return PoseDetectionLatest.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<CameraFrameAnalysisStatus> getFrameAnalysisStatus() async {
    final response = await _apiClient.get('camera/analyze-frame/status');
    return CameraFrameAnalysisStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<Map<String, dynamic>> analyzeFrame(
    Uint8List imageBytes, {
    String sessionId = 'browser-preview',
    bool poseEnabled = true,
    bool fallEnabled = true,
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        imageBytes,
        filename: 'browser_frame.jpg',
        contentType: DioMediaType('image', 'jpeg'),
      ),
    });
    final response = await _apiClient.post(
      'camera/analyze-frame?session_id=$sessionId&pose_enabled=$poseEnabled&fall_enabled=$fallEnabled',
      data: formData,
      options: Options(receiveTimeout: const Duration(seconds: 20)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> analyzePoseFrame(
    Uint8List imageBytes, {
    String sessionId = 'browser-preview',
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        imageBytes,
        filename: 'browser_pose_frame.jpg',
        contentType: DioMediaType('image', 'jpeg'),
      ),
    });
    final response = await _apiClient.post(
      'camera/analyze-frame/pose?session_id=$sessionId',
      data: formData,
      options: Options(receiveTimeout: const Duration(seconds: 8)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> analyzeFallFrame(
    Uint8List imageBytes, {
    String sessionId = 'browser-preview',
  }) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        imageBytes,
        filename: 'browser_fall_frame.jpg',
        contentType: DioMediaType('image', 'jpeg'),
      ),
    });
    final response = await _apiClient.post(
      'camera/analyze-frame/fall?session_id=$sessionId',
      data: formData,
      options: Options(receiveTimeout: const Duration(seconds: 9)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> primeProcessedOverlay({
    bool includeFall = false,
  }) async {
    final response = await _apiClient.post(
      'camera/processed-overlay/prime?include_fall=$includeFall',
      options: Options(receiveTimeout: const Duration(seconds: 22)),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> getProcessedOverlayStatus() async {
    final response = await _apiClient.get('camera/processed-overlay/status');
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Uint8List> getCurrentFrameSnapshot({
    CameraVideoMode mode = CameraVideoMode.raw,
    String? bridgeSnapshotUrl,
    String? cameraId,
  }) async {
    final normalizedCameraId = cameraId?.trim();
    final path = bridgeSnapshotUrl ??
        ((normalizedCameraId != null && normalizedCameraId.isNotEmpty)
            ? (mode == CameraVideoMode.processed
                ? 'camera-sources/$normalizedCameraId/processed-snapshot'
                : 'camera-sources/$normalizedCameraId/snapshot')
            : switch (mode) {
                CameraVideoMode.processed => 'camera/processed-snapshot',
                CameraVideoMode.raw => 'camera/snapshot',
              });
    final response = await _apiClient.get(
      path,
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 5),
      ),
    );
    final data = response.data;
    if (data is Uint8List) return data;
    if (data is List<int>) return Uint8List.fromList(data);
    throw Exception('摄像头快照数据格式异常');
  }

  Future<CameraSetupConfig> getSetupConfig() async {
    final response = await _apiClient.get('camera/setup/config');
    return CameraSetupConfig.fromJson(
        Map<String, dynamic>.from(response.data as Map));
  }

  Future<CameraSetupConfig> saveSetupConfig(CameraSetupConfig config) async {
    final response = await _apiClient.post(
      'camera/setup/config',
      data: config.toJson(),
    );
    final payload = Map<String, dynamic>.from(response.data as Map);
    return CameraSetupConfig.fromJson(
        Map<String, dynamic>.from(payload['config'] as Map));
  }

  Future<Uint8List> testSetupSnapshot(CameraSetupConfig config) async {
    final response = await _apiClient.post(
      'camera/setup/test-snapshot',
      data: config.toJson(),
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 20),
      ),
    );
    final data = response.data;
    if (data is Uint8List) return data;
    if (data is List<int>) return Uint8List.fromList(data);
    throw Exception('快照数据格式异常');
  }

  Future<void> moveCamera(String direction,
      {String mode = 'continuous'}) async {
    await _apiClient.post(
      'camera/ptz',
      data: <String, dynamic>{
        'direction': direction,
        'mode': mode,
      },
    );
  }

  WebSocketChannel connectFrameStream({
    CameraVideoMode mode = CameraVideoMode.raw,
    String? bridgeStreamUrl,
    String? cameraId,
  }) {
    final normalizedCameraId = cameraId?.trim();
    final path = bridgeStreamUrl ??
        ((normalizedCameraId != null && normalizedCameraId.isNotEmpty)
            ? (mode == CameraVideoMode.processed
                ? '/ws/camera-sources/$normalizedCameraId/processed'
                : '/ws/camera-sources/$normalizedCameraId')
            : switch (mode) {
                CameraVideoMode.processed => '/ws/camera/processed',
                CameraVideoMode.raw => '/ws/camera',
              });
    return WebSocketChannel.connect(_resolveWebSocketUri(path));
  }

  WebSocketChannel connectAudioListenStream() {
    return WebSocketChannel.connect(
        Uri.parse('${_endpointConfig.wsBaseUrl}/ws/camera/audio/listen'));
  }

  Uri _resolveWebSocketUri(String source) {
    final parsed = Uri.tryParse(source);
    if (parsed != null && parsed.hasScheme) {
      return parsed;
    }
    final path = source.startsWith('/') ? source : '/$source';
    return Uri.parse('${_endpointConfig.wsBaseUrl}$path');
  }

  Map<String, CameraDetectionRuntimeStatus> _parseDetectionModelsStatus(
      Object? data) {
    final payload = Map<String, dynamic>.from(data as Map);
    return <String, CameraDetectionRuntimeStatus>{
      'fall_detection': CameraDetectionRuntimeStatus.fromJson(
        Map<String, dynamic>.from(payload['fall_detection'] as Map),
      ),
      'pose_detection': CameraDetectionRuntimeStatus.fromJson(
        Map<String, dynamic>.from(payload['pose_detection'] as Map),
      ),
    };
  }
}
