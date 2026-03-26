import 'dart:async';
import 'dart:convert';
import '../../../core/network/api_client.dart';

class AgentMessage {
  final String role;
  String content;

  AgentMessage({required this.role, required this.content});

  factory AgentMessage.fromJson(Map<String, dynamic> json) {
    return AgentMessage(
      role: json['role'] ?? 'assistant',
      content: json['content'] ?? '',
    );
  }
}

class AgentRepository {
  final ApiClient _apiClient;

  AgentRepository(this._apiClient);

  /// Streams the agent response, yielding delta text chunks.
  /// The caller should listen to this stream and progressively build the message.
  Stream<String> streamAgentAnalysis(String message, String? deviceMac) async* {
    if (deviceMac == null || deviceMac.isEmpty) {
      yield '尚未绑定设备，无法分析老人的健康状况。请先在首页完成设备登记和绑定。';
      return;
    }

    final payload = {
      'question': message,
      'device_mac': deviceMac,
      'role': 'family',
      'mode': 'qwen',
    };

    try {
      final response = await _apiClient.postStream(
        '/chat/analyze/device/stream',
        data: payload,
      );

      final stream = response.data?.stream;
      if (stream == null) {
        yield '无法获取流式响应。';
        return;
      }

      String buffer = '';
      await for (final chunk in stream) {
        buffer += utf8.decode(chunk);
        // Process complete NDJSON lines
        while (buffer.contains('\n')) {
          final newlineIndex = buffer.indexOf('\n');
          final line = buffer.substring(0, newlineIndex).trim();
          buffer = buffer.substring(newlineIndex + 1);

          if (line.isEmpty) continue;
          try {
            final event = jsonDecode(line) as Map<String, dynamic>;
            final type = event['type'] as String?;
            if (type == 'answer.delta') {
              final delta = event['delta'] as String? ?? '';
              if (delta.isNotEmpty) {
                yield delta;
              }
            }
            // answer.completed is handled implicitly when stream ends
          } catch (_) {
            // Skip malformed lines
          }
        }
      }
    } catch (e) {
      yield '请求分析失败: $e';
    }
  }
}
