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
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  Future<CameraAudioStatus> getAudioStatus() async {
    final response = await _apiClient.get('camera/audio/status');
    return CameraAudioStatus.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
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
      Uri.parse('${_endpointConfig.wsBaseUrl}/ws/camera'),
    );
  }

  WebSocketChannel connectAudioListenStream() {
    return WebSocketChannel.connect(
      Uri.parse('${_endpointConfig.wsBaseUrl}/ws/camera/audio/listen'),
    );
  }
}
