import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

class Omni7bVoiceService {
  final String apiKey;
  final String apiBase;
  final String model;

  late final Dio _dio;

  static const String _systemPrompt = '''
你是面向老人的AI健康守护助手，当前正处于智慧康养项目的演示体验环节。
你的任务是用简单、温和、充满关怀的拟人化口语和体验者（代入老人角色）对话，展现系统的智能化与温度。
约束要求：
1. 每次回答必须控制在2到3个短句，口语化、短平快，不要长篇大论，也不要表现出僵硬的机器感。
2. 如果被问及健康状况，优先用通俗易懂的话告诉对方目前的身体状态很不错、很平稳，切忌堆砌生硬的医学术语或具体数值分析。
3. 展现出你是一个随时待命、可靠且贴心的守护者，让听众感受到AI的陪伴感。
''';

  Omni7bVoiceService({
    required this.apiKey,
    required this.apiBase,
    this.model = 'qwen2.5-omni-7b',
  }) {
    _dio = Dio(
      BaseOptions(
        baseUrl: apiBase,
        headers: <String, Object>{
          'Authorization': 'Bearer $apiKey',
          'Content-Type': 'application/json',
        },
        sendTimeout: const Duration(seconds: 120),
        receiveTimeout: const Duration(seconds: 120),
      ),
    );
    _dio.interceptors.add(_LoggingInterceptor());
  }

  Future<String> sendMessage(String message) async {
    final response = await _postChat(
      messages: <Map<String, Object>>[
        <String, Object>{
          'role': 'system',
          'content': _systemPrompt,
        },
        <String, Object>{
          'role': 'user',
          'content': message,
        },
      ],
    );
    return _extractAssistantText(response.data);
  }

  Future<String> sendAudio(String audioPath) async {
    final audioInput = await _buildAudioInput(audioPath);
    final response = await _postChat(
      messages: <Map<String, Object>>[
        <String, Object>{
          'role': 'system',
          'content': _systemPrompt,
        },
        <String, Object>{
          'role': 'user',
          'content': <Map<String, Object>>[audioInput],
        },
      ],
    );
    return _extractAssistantText(response.data);
  }

  Future<String> sendTextWithAudio({
    required String text,
    required String audioPath,
  }) async {
    final audioInput = await _buildAudioInput(audioPath);
    final response = await _postChat(
      messages: <Map<String, Object>>[
        <String, Object>{
          'role': 'system',
          'content': _systemPrompt,
        },
        <String, Object>{
          'role': 'user',
          'content': <Map<String, Object>>[
            <String, Object>{
              'type': 'text',
              'text': text,
            },
            audioInput,
          ],
        },
      ],
    );
    return _extractAssistantText(response.data);
  }

  Future<Response<dynamic>> _postChat({
    required List<Map<String, Object>> messages,
  }) async {
    try {
      final response = await _dio.post(
        '/chat/completions',
        data: <String, Object>{
          'model': model,
          'messages': messages,
          'stream': false,
          'max_tokens': 2048,
        },
      );
      if (response.statusCode == 200) {
        return response;
      }
      throw Exception('API error: ${response.statusCode}');
    } on DioException catch (error) {
      final data = error.response?.data;
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          throw Exception(detail);
        }
      }
      throw Exception('Network error: ${error.message}');
    }
  }

  Future<Map<String, Object>> _buildAudioInput(String audioPath) async {
    final file = File(audioPath);
    if (!file.existsSync()) {
      throw Exception('Audio file not found: $audioPath');
    }

    final bytes = await file.readAsBytes();
    final base64Audio = base64Encode(bytes);
    final format = _normalizeAudioFormat(audioPath.split('.').last);

    return <String, Object>{
      'type': 'input_audio',
      'input_audio': <String, Object>{
        'data': 'data:;base64,$base64Audio',
        'format': format,
      },
    };
  }

  String _normalizeAudioFormat(String extension) {
    final lower = extension.trim().toLowerCase();
    switch (lower) {
      case 'wav':
      case 'wave':
        return 'wav';
      case 'mp3':
      case 'mpeg':
        return 'mp3';
      case 'm4a':
      case 'aac':
      case 'mp4':
        return 'aac';
      case 'amr':
      case '3gp':
      case '3gpp':
        return lower;
      default:
        return 'wav';
    }
  }

  String _extractAssistantText(dynamic data) {
    if (data is! Map<String, dynamic>) {
      return '';
    }

    final choices = data['choices'];
    if (choices is! List || choices.isEmpty) {
      return '';
    }

    final first = choices.first;
    if (first is! Map<String, dynamic>) {
      return '';
    }

    final message = first['message'];
    if (message is! Map<String, dynamic>) {
      return '';
    }

    final content = message['content'];
    if (content is String) {
      return content;
    }
    if (content is List) {
      return content
          .whereType<Map<String, dynamic>>()
          .map((item) => item['text'])
          .whereType<String>()
          .join();
    }
    return '';
  }

  void dispose() {
    _dio.close();
  }
}

class _LoggingInterceptor extends Interceptor {
  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    debugPrint('[request] ${options.method} ${options.path}');
    super.onRequest(options, handler);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    debugPrint('[response] ${response.statusCode}');
    super.onResponse(response, handler);
  }

  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    debugPrint('[error] ${err.message}');
    super.onError(err, handler);
  }
}
