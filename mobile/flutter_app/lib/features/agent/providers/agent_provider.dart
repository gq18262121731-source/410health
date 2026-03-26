import 'package:flutter/material.dart';
import '../repositories/agent_repository.dart';

enum AgentStatus { initial, loading, streaming, loaded, error }

class AgentProvider extends ChangeNotifier {
  final AgentRepository _repository;

  AgentStatus _status = AgentStatus.initial;
  String? _errorMessage;
  final List<AgentMessage> _messages = [];

  AgentProvider(this._repository);

  AgentStatus get status => _status;
  String? get errorMessage => _errorMessage;
  List<AgentMessage> get messages => _messages;

  /// Setup initial chat greeting
  void init([String? initialGreeting]) {
    _messages.clear();
    if (initialGreeting != null) {
      _messages.add(AgentMessage(role: 'assistant', content: initialGreeting));
    }
    _status = AgentStatus.loaded;
    notifyListeners();
  }

  Future<void> sendMessage(String text, {String? deviceMac}) async {
    if (text.trim().isEmpty) return;

    // Add user message immediately for snappy UI
    final userMsg = AgentMessage(role: 'user', content: text);
    _messages.add(userMsg);

    _status = AgentStatus.loading;
    _errorMessage = null;
    notifyListeners();

    // Add placeholder assistant message for streaming content
    final assistantMsg = AgentMessage(role: 'assistant', content: '');
    _messages.add(assistantMsg);
    notifyListeners();

    try {
      _status = AgentStatus.streaming;
      notifyListeners();

      await for (final delta
          in _repository.streamAgentAnalysis(text, deviceMac)) {
        assistantMsg.content += delta;
        // Notify on every delta for true streaming effect
        notifyListeners();
      }

      _status = AgentStatus.loaded;
    } catch (e) {
      _errorMessage = '无法连接到健康助手，请重试。';
      _status = AgentStatus.error;
      if (assistantMsg.content.isEmpty) {
        assistantMsg.content = '连接失败，请重试。';
      }
    }
    notifyListeners();
  }
}
