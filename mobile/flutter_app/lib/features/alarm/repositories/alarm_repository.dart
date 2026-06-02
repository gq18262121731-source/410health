import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/server_endpoint_config.dart';
import '../../session/services/session_manager.dart';
import '../models/alarm_model.dart';

class AlarmRepository {
  final ApiClient _apiClient;
  final ServerEndpointConfig _endpointConfig;
  final SessionManager _sessionManager;

  AlarmRepository(
    this._apiClient, {
    required ServerEndpointConfig endpointConfig,
    required SessionManager sessionManager,
  })  : _endpointConfig = endpointConfig,
        _sessionManager = sessionManager;

  Future<List<AlarmRecord>> getAlarms({bool activeOnly = false}) async {
    final response = await _apiClient.get('alarms', queryParameters: {'active_only': activeOnly});
    return (response.data as List).map((e) => AlarmRecord.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<AlarmQueueItem>> getAlarmQueue() async {
    final response = await _apiClient.get('alarms/queue');
    return (response.data as List).map((e) => AlarmQueueItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<MobilePushRecord>> getMobilePushes() async {
    final response = await _apiClient.get('alarms/mobile-pushes');
    return (response.data as List).map((e) => MobilePushRecord.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> acknowledgeAlarm(String alarmId) async {
    await _apiClient.post('alarms/$alarmId/acknowledge');
  }

  String resolveSnapshotUrl(String rawUrl) {
    final normalized = rawUrl.trim();
    if (normalized.isEmpty) {
      return '';
    }
    final parsed = Uri.tryParse(normalized);
    if (parsed != null && parsed.hasScheme) {
      return normalized;
    }
    if (normalized.startsWith('/api/v1/')) {
      return '${_endpointConfig.origin}$normalized';
    }
    if (normalized.startsWith('/')) {
      return '${_endpointConfig.origin}$normalized';
    }
    return '${_endpointConfig.apiBaseUrl}camera/fall-detection/snapshot?path=${Uri.encodeQueryComponent(normalized)}';
  }

  WebSocketChannel connectToAlarms() {
    final token = _sessionManager.token;
    final uri = (token != null && token.trim().isNotEmpty)
        ? Uri.parse('${_endpointConfig.wsBaseUrl}/ws/alarms?token=${Uri.encodeQueryComponent(token)}')
        : Uri.parse('${_endpointConfig.wsBaseUrl}/ws/alarms');
    return WebSocketChannel.connect(uri);
  }
}
