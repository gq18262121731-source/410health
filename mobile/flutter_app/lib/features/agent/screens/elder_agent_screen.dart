import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/agent_provider.dart';
import '../../voice/providers/voice_provider.dart';
import '../../../widgets/logout_action.dart';

class ElderAgentScreen extends StatefulWidget {
  final String? deviceMac;

  const ElderAgentScreen({super.key, this.deviceMac});

  @override
  State<ElderAgentScreen> createState() => _ElderAgentScreenState();
}

class _ElderAgentScreenState extends State<ElderAgentScreen> {
  final ScrollController _scrollController = ScrollController();

  final List<String> _presetPrompts = [
    '我今天的健康情况怎么样？',
    '我的心率波动正常吗？',
    '今天有任何健康风险吗？',
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AgentProvider>().init('您好！我是您的智能健康助手。您可以直接点击下方的按钮问我问题，或者长按话筒跟我说话。');
    });
  }

  void _sendMessage(String text) {
    if (text.trim().isEmpty) return;
    context.read<AgentProvider>().sendMessage(text, deviceMac: widget.deviceMac).then((_) {
      _handleAssistantResponse();
    });
    _scrollToBottom();
  }

  void _handleAssistantResponse() {
    final messages = context.read<AgentProvider>().messages;
    if (messages.isNotEmpty && messages.last.role == 'assistant') {
      final lastContent = messages.last.content;
      if (lastContent.isNotEmpty) {
        context.read<VoiceProvider>().processTts(lastContent);
      }
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 300), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 500),
          curve: Curves.easeOut,
        );
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final agentProvider = context.watch<AgentProvider>();
    final voiceProvider = context.watch<VoiceProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        title: const Text('智能助手', style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        actions: const [LogoutAction()],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(24),
              itemCount: agentProvider.messages.length + (agentProvider.status == AgentStatus.loading ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == agentProvider.messages.length) {
                  return _buildLoadingBubble();
                }
                final msg = agentProvider.messages[index];
                return _buildMessageBubble(msg.content, msg.role == 'user');
              },
            ),
          ),
          if (agentProvider.status != AgentStatus.loading && agentProvider.status != AgentStatus.streaming)
            _buildPresetSection(),
          _buildVoiceInputSection(voiceProvider, agentProvider),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(String text, bool isUser) {
    return Column(
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.symmetric(vertical: 12),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: isUser ? const Color(0xFFFF875A).withOpacity(0.1) : Colors.white.withOpacity(0.05),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: isUser ? const Color(0xFFFF875A).withOpacity(0.3) : Colors.white10,
            ),
          ),
          child: Text(
            text,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 28,
              height: 1.4,
              fontWeight: isUser ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ),
        if (!isUser) const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildLoadingBubble() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 12),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(24),
      ),
      child: const Center(
        child: CircularProgressIndicator(color: Color(0xFFFF875A)),
      ),
    );
  }

  Widget _buildPresetSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
      child: Column(
        children: _presetPrompts.map((prompt) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => _sendMessage(prompt),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white.withOpacity(0.05),
                  foregroundColor: const Color(0xFFFF875A),
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                    side: const BorderSide(color: Colors.white12),
                  ),
                ),
                child: Text(prompt, style: const TextStyle(fontSize: 22)),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildVoiceInputSection(VoiceProvider voiceProvider, AgentProvider agentProvider) {
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1D24),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(32)),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 10, offset: const Offset(0, -5)),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('长按话筒跟我说话', style: TextStyle(color: Colors.white54, fontSize: 18)),
          const SizedBox(height: 20),
          GestureDetector(
            onLongPressStart: (_) {
              // Simulated voice start
            },
            onLongPressEnd: (_) {
              // Simulated voice transcription
              _sendMessage('我的健康状态还好吗？');
            },
            child: CircleAvatar(
              radius: 50,
              backgroundColor: const Color(0xFFFF875A),
              child: const Icon(Icons.mic, size: 50, color: Color(0xFF08161B)),
            ),
          ),
        ],
      ),
    );
  }
}
