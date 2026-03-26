import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/voice_provider.dart';
import '../../../widgets/logout_action.dart';

class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen> {
  final TextEditingController _ttsController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<VoiceProvider>().checkStatus();
    });
  }

  @override
  void dispose() {
    _ttsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final voiceProvider = context.watch<VoiceProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        title: const Text('语音交互', style: TextStyle(color: Colors.white, fontSize: 18)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: const [LogoutAction()],
      ),
      body: _buildBody(voiceProvider),
    );
  }

  Widget _buildBody(VoiceProvider provider) {
    if (provider.status == VoiceLoadStatus.loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFFFF875A)));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStatusCard(provider),
          const SizedBox(height: 32),
          if (provider.isVoiceAvailable) ...[
            _buildAsrSection(provider),
            const SizedBox(height: 48),
            _buildTtsSection(provider),
          ] else
            _buildDisabledFallback(),
        ],
      ),
    );
  }

  Widget _buildStatusCard(VoiceProvider provider) {
    final isConfigured = provider.isVoiceAvailable;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isConfigured ? Colors.greenAccent.withOpacity(0.2) : Colors.redAccent.withOpacity(0.2),
        ),
      ),
      child: Row(
        children: [
          Icon(
            isConfigured ? Icons.check_circle : Icons.error_outline,
            color: isConfigured ? Colors.greenAccent : Colors.redAccent,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isConfigured ? '语音服务已就绪' : '语音服务未配置',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
                if (isConfigured)
                  Text(
                    '算力提供商: ${provider.voiceStatus?.serviceProvider ?? "默认"}',
                    style: const TextStyle(color: Colors.white30, fontSize: 12),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAsrSection(VoiceProvider provider) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('语音转文字 (ASR)', style: TextStyle(color: Colors.white70, fontSize: 14)),
        const SizedBox(height: 16),
        Center(
          child: GestureDetector(
            onLongPress: () {
              // MVP 模拟：长按发送一段假录音
              provider.processAsr("MOCK_AUDIO_BASE64_DATA");
            },
            child: CircleAvatar(
              radius: 40,
              backgroundColor: provider.isProcessing ? const Color(0xFFFF875A) : Colors.white10,
              child: Icon(
                provider.isProcessing ? Icons.graphic_eq : Icons.mic,
                color: provider.isProcessing ? const Color(0xFF08161B) : Colors.white70,
                size: 32,
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Center(
          child: Text(
            provider.isProcessing ? '正在识别...' : '长按模拟录音',
            style: const TextStyle(color: Colors.white24, fontSize: 12),
          ),
        ),
        if (provider.lastAsrText.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 16),
            padding: const EdgeInsets.all(16),
            width: double.infinity,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.03),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              '识别结果: ${provider.lastAsrText}',
              style: const TextStyle(color: Color(0xFFFF875A), fontSize: 14),
            ),
          ),
      ],
    );
  }

  Widget _buildTtsSection(VoiceProvider provider) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('文字转语音 (TTS)', style: TextStyle(color: Colors.white70, fontSize: 14)),
        const SizedBox(height: 16),
        TextField(
          controller: _ttsController,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '输入要播报的内容...',
            hintStyle: const TextStyle(color: Colors.white10),
            filled: true,
            fillColor: Colors.white.withOpacity(0.03),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
          ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          height: 48,
          child: ElevatedButton(
            onPressed: provider.isProcessing
                ? null
                : () => provider.processTts(_ttsController.text),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFF875A),
              foregroundColor: const Color(0xFF08161B),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('开始合成并播报', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
        if (provider.lastTtsUrl.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(
              '音频链接已生成 (由于插件限制不自动播放)',
              style: TextStyle(color: Colors.greenAccent.withOpacity(0.5), fontSize: 10),
            ),
          ),
      ],
    );
  }

  Widget _buildDisabledFallback() {
    return Center(
      child: Column(
        children: [
          const SizedBox(height: 40),
          Icon(Icons.voice_over_off, size: 64, color: Colors.white.withOpacity(0.1)),
          const SizedBox(height: 24),
          const Text(
            '语音服务当前不可用',
            style: TextStyle(color: Colors.white70, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          const Text(
            '后端尚未配置专业 ASR/TTS 算力。您可以继续使用实时监测、历史趋势和告警中心等核心功能。',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white24, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
