import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/agent_provider.dart';

class AiChatDialog extends StatefulWidget {
  final String? deviceMac;
  
  const AiChatDialog({super.key, this.deviceMac});

  @override
  State<AiChatDialog> createState() => _AiChatDialogState();
}

class _AiChatDialogState extends State<AiChatDialog> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();

  final List<String> _presetPrompts = [
    '提供最近一天的健康情况',
    '今天有任何异常体征吗？',
    '心率波动正常吗？',
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AgentProvider>().init('你好！我是智能守护助手，可以直接向我提问老人的健康状况。');
    });
  }

  void _sendMessage(String text) {
    if (text.trim().isEmpty) return;
    _textController.clear();
    _focusNode.unfocus();
    
    context.read<AgentProvider>().sendMessage(text, deviceMac: widget.deviceMac);
    _scrollToBottom();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0C1D24),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        border: Border.all(color: Colors.white10),
      ),
      padding: EdgeInsets.only(
        top: 16,
        left: 16,
        right: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.auto_awesome, color: Color(0xFFFF875A)),
                  SizedBox(width: 8),
                  Text('智能守护助手', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                ],
              ),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white54),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),
          const Divider(color: Colors.white10, height: 24),
          
          Flexible(
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.4,
              ),
              child: Consumer<AgentProvider>(
                builder: (context, provider, child) {
                  WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
                  
                  final showLoading = provider.status == AgentStatus.loading;

                  return ListView.builder(
                    controller: _scrollController,
                    shrinkWrap: true,
                    itemCount: provider.messages.length + (showLoading ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == provider.messages.length) {
                        return _buildLoadingBubble();
                      }
                      
                      final msg = provider.messages[index];
                      final isUser = msg.role == 'user';
                      final isStreaming = !isUser && 
                          provider.status == AgentStatus.streaming &&
                          index == provider.messages.length - 1;
                      
                      return _buildMessageBubble(msg.content, isUser, isStreaming: isStreaming);
                    },
                  );
                },
              ),
            ),
          ),
          
          const SizedBox(height: 16),
          _buildPresetChips(),
          const SizedBox(height: 12),
          
          // Input Area
          Container(
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.05),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    focusNode: _focusNode,
                    style: const TextStyle(color: Colors.white),
                    decoration: const InputDecoration(
                      hintText: '向助手提问...',
                      hintStyle: TextStyle(color: Colors.white30),
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    ),
                    onSubmitted: _sendMessage,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send, color: Color(0xFFFF875A)),
                  onPressed: () => _sendMessage(_textController.text),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPresetChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: _presetPrompts.map((prompt) {
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ActionChip(
              backgroundColor: Colors.white.withOpacity(0.05),
              side: BorderSide(color: const Color(0xFFFF875A).withOpacity(0.3)),
              label: Text(prompt, style: const TextStyle(color: Color(0xFFFF875A), fontSize: 12)),
              onPressed: () => _sendMessage(prompt),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildMessageBubble(String text, bool isUser, {bool isStreaming = false}) {
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFFFF875A) : Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(16).copyWith(
            bottomRight: Radius.circular(isUser ? 0 : 16),
            bottomLeft: Radius.circular(isUser ? 16 : 0),
          ),
        ),
        child: RichText(
          text: TextSpan(
            text: text.isEmpty && isStreaming ? '思考中...' : text,
            style: TextStyle(
              color: isUser ? const Color(0xFF08161B) : Colors.white.withOpacity(0.9),
              fontSize: 14,
              height: 1.5,
              fontWeight: isUser ? FontWeight.w500 : FontWeight.normal,
            ),
            children: isStreaming && text.isNotEmpty
                ? [
                    const TextSpan(
                      text: ' ▌',
                      style: TextStyle(color: Color(0xFFFF875A), fontWeight: FontWeight.bold),
                    ),
                  ]
                : null,
          ),
        ),
      ),
    );
  }

  Widget _buildLoadingBubble() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(16).copyWith(bottomLeft: const Radius.circular(0)),
        ),
        child: const SizedBox(
          width: 24,
          height: 12,
          child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFFF875A)),
        ),
      ),
    );
  }
}

