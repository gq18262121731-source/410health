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

  Future<CameraAudioStatus> getAudioStatus() async {
    final response = await _apiClient.get('camera/audio/status');
    return CameraAudioStatus.fromJson(
        Map<String, dynamic>.from(response.data as Map));
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

  WebSocketChannel connectFrameStream() {
    return WebSocketChannel.connect(
        Uri.parse('${_endpointConfig.wsBaseUrl}/ws/camera'));
  }

  WebSocketChannel connectAudioListenStream() {
    return WebSocketChannel.connect(
        Uri.parse('${_endpointConfig.wsBaseUrl}/ws/camera/audio/listen'));
  }
}
