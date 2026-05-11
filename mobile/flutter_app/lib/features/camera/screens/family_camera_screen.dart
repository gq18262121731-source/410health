import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../models/camera_models.dart';
import '../providers/camera_provider.dart';

class FamilyCameraScreen extends StatelessWidget {
  const FamilyCameraScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          '家庭摄像头',
          style: TextStyle(
            color: AppColors.textMain,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.refresh, color: AppColors.textSub),
            onPressed: () {
              context.read<CameraProvider>().refreshDiagnostics();
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
        children: const <Widget>[
          _VideoPanel(),
          SizedBox(height: 16),
          _CameraSetupPanel(),
          SizedBox(height: 16),
          _ActionStrip(),
          SizedBox(height: 16),
          _PtzPanel(),
          SizedBox(height: 16),
          _DiagnosticsPanel(),
          SizedBox(height: 16),
          _ErrorPanel(),
        ],
      ),
    );
  }
}

class _VideoPanel extends StatelessWidget {
  const _VideoPanel();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();
    final frame = provider.frameBytes;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppColors.border),
        boxShadow: const [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 12,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                fit: StackFit.expand,
                children: <Widget>[
                  ColoredBox(
                    color: const Color(0xFF0F172A),
                    child: frame == null
                        ? _VideoPlaceholder(isConnecting: provider.isConnecting)
                        : Image.memory(
                            frame,
                            gaplessPlayback: true,
                            fit: BoxFit.contain,
                          ),
                  ),
                  Positioned(
                    left: 12,
                    top: 12,
                    child: _StatusPill(
                      label: provider.streamLabel,
                      isOnline: provider.hasFrame && provider.autoRefresh,
                    ),
                  ),
                  Positioned(
                    right: 12,
                    top: 12,
                    child: _StatusPill(
                      label: provider.status?.label ?? '检查中',
                      isOnline: provider.status?.online == true,
                    ),
                  ),
                  if (provider.audioListening)
                    Positioned(
                      left: 12,
                      bottom: 12,
                      child: _StatusPill(
                        label: provider.audioLabel,
                        isOnline: true,
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: <Widget>[
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(
                      Icons.videocam_outlined,
                      color: AppColors.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        const Text(
                          '家庭实时画面',
                          style: TextStyle(
                            color: AppColors.textMain,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          provider.endpointLabel,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.textSub,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VideoPlaceholder extends StatelessWidget {
  final bool isConnecting;

  const _VideoPlaceholder({required this.isConnecting});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (isConnecting)
            const SizedBox(
              width: 30,
              height: 30,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                color: Colors.white,
              ),
            )
          else
            const Icon(Icons.videocam_off_outlined,
                color: Colors.white70, size: 34),
          const SizedBox(height: 12),
          Text(
            isConnecting ? '正在连接摄像头...' : '暂无视频画面',
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _CameraSetupPanel extends StatefulWidget {
  const _CameraSetupPanel();

  @override
  State<_CameraSetupPanel> createState() => _CameraSetupPanelState();
}

class _CameraSetupPanelState extends State<_CameraSetupPanel> {
  late final TextEditingController _localIndexController;
  late final TextEditingController _ipController;
  late final TextEditingController _userController;
  late final TextEditingController _passwordController;
  late final TextEditingController _rtspPortController;
  late final TextEditingController _rtspPathController;
  late final TextEditingController _streamPathController;
  late final TextEditingController _audioPathController;
  late final TextEditingController _onvifPortController;
  CameraSetupConfig? _lastSyncedConfig;

  @override
  void initState() {
    super.initState();
    _localIndexController = TextEditingController();
    _ipController = TextEditingController();
    _userController = TextEditingController();
    _passwordController = TextEditingController();
    _rtspPortController = TextEditingController();
    _rtspPathController = TextEditingController();
    _streamPathController = TextEditingController();
    _audioPathController = TextEditingController();
    _onvifPortController = TextEditingController();
  }

  @override
  void dispose() {
    _localIndexController.dispose();
    _ipController.dispose();
    _userController.dispose();
    _passwordController.dispose();
    _rtspPortController.dispose();
    _rtspPathController.dispose();
    _streamPathController.dispose();
    _audioPathController.dispose();
    _onvifPortController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();
    _syncControllers(provider.setupConfig);
    final config = provider.setupConfig;
    final isLocal = config.sourceMode == 'local';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.add_a_photo_outlined,
                    color: AppColors.primary),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  '摄像头接入',
                  style: TextStyle(
                    color: AppColors.textMain,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SegmentedButton<String>(
            segments: const <ButtonSegment<String>>[
              ButtonSegment<String>(
                value: 'local',
                icon: Icon(Icons.laptop_mac_outlined),
                label: Text('本地摄像头'),
              ),
              ButtonSegment<String>(
                value: 'rtsp',
                icon: Icon(Icons.router_outlined),
                label: Text('外部 RTSP'),
              ),
            ],
            selected: <String>{isLocal ? 'local' : 'rtsp'},
            onSelectionChanged: (Set<String> selected) {
              _updateProvider(
                provider,
                config.copyWith(sourceMode: selected.first),
              );
            },
          ),
          const SizedBox(height: 14),
          if (isLocal)
            Row(
              children: <Widget>[
                Expanded(
                  child: _SetupTextField(
                    controller: _localIndexController,
                    label: '摄像头索引',
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _pushForm(provider),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: config.localBackend,
                    decoration: _fieldDecoration('后端模式'),
                    items: const <DropdownMenuItem<String>>[
                      DropdownMenuItem<String>(
                          value: 'dshow', child: Text('dshow')),
                      DropdownMenuItem<String>(
                          value: 'msmf', child: Text('msmf')),
                      DropdownMenuItem<String>(
                          value: 'auto', child: Text('auto')),
                      DropdownMenuItem<String>(
                          value: 'any', child: Text('any')),
                    ],
                    onChanged: (value) {
                      if (value == null) return;
                      _updateProvider(
                        provider,
                        config.copyWith(localBackend: value),
                      );
                    },
                  ),
                ),
              ],
            )
          else ...<Widget>[
            _SetupTextField(
              controller: _ipController,
              label: '摄像头 IP',
              onChanged: (_) => _pushForm(provider),
            ),
            const SizedBox(height: 10),
            Row(
              children: <Widget>[
                Expanded(
                  child: _SetupTextField(
                    controller: _userController,
                    label: '用户名',
                    onChanged: (_) => _pushForm(provider),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _SetupTextField(
                    controller: _passwordController,
                    label: '密码',
                    obscureText: true,
                    onChanged: (_) => _pushForm(provider),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: <Widget>[
                Expanded(
                  child: _SetupTextField(
                    controller: _rtspPortController,
                    label: 'RTSP 端口',
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _pushForm(provider),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _SetupTextField(
                    controller: _onvifPortController,
                    label: 'ONVIF 端口',
                    keyboardType: TextInputType.number,
                    onChanged: (_) => _pushForm(provider),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            _SetupTextField(
              controller: _rtspPathController,
              label: '主码流路径',
              onChanged: (_) => _pushForm(provider),
            ),
            const SizedBox(height: 10),
            _SetupTextField(
              controller: _streamPathController,
              label: '预览流路径',
              onChanged: (_) => _pushForm(provider),
            ),
            const SizedBox(height: 10),
            _SetupTextField(
              controller: _audioPathController,
              label: '音频流路径',
              onChanged: (_) => _pushForm(provider),
            ),
          ],
          if (provider.setupMessage != null) ...<Widget>[
            const SizedBox(height: 12),
            _InlineNotice(
              icon: Icons.info_outline,
              color: provider.setupMessage!.contains('成功') ||
                      provider.setupMessage!.contains('已保存')
                  ? AppColors.success
                  : AppColors.warning,
              text: provider.setupMessage!,
            ),
          ],
          if (provider.setupSnapshotBytes != null) ...<Widget>[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: Image.memory(
                  provider.setupSnapshotBytes!,
                  fit: BoxFit.cover,
                  gaplessPlayback: true,
                ),
              ),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: <Widget>[
              Expanded(
                child: _ActionButton(
                  icon: Icons.photo_camera_outlined,
                  label: provider.setupTesting ? '测试中...' : '测试快照',
                  color: AppColors.secondary,
                  onTap: provider.setupTesting
                      ? () {}
                      : () => provider.testSetupSnapshot(),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ActionButton(
                  icon: Icons.save_outlined,
                  label: provider.setupSaving ? '保存中...' : '保存配置',
                  color: AppColors.primary,
                  onTap: provider.setupSaving
                      ? () {}
                      : () => provider.saveSetupConfig(),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _syncControllers(CameraSetupConfig config) {
    if (_lastSyncedConfig == config) return;
    _lastSyncedConfig = config;
    _localIndexController.text = config.localIndex.toString();
    _ipController.text = config.ip;
    _userController.text = config.user;
    _passwordController.text = config.password;
    _rtspPortController.text = config.rtspPort.toString();
    _rtspPathController.text = config.rtspPath;
    _streamPathController.text = config.streamRtspPath;
    _audioPathController.text = config.audioRtspPath;
    _onvifPortController.text = config.onvifPort.toString();
  }

  void _pushForm(CameraProvider provider) {
    final current = provider.setupConfig;
    _updateProvider(
      provider,
      current.copyWith(
        localIndex: int.tryParse(_localIndexController.text.trim()) ?? 0,
        ip: _ipController.text.trim(),
        user: _userController.text.trim(),
        password: _passwordController.text,
        rtspPort: int.tryParse(_rtspPortController.text.trim()) ?? 10554,
        rtspPath: _rtspPathController.text.trim(),
        streamRtspPath: _streamPathController.text.trim(),
        audioRtspPath: _audioPathController.text.trim(),
        onvifPort: int.tryParse(_onvifPortController.text.trim()) ?? 10080,
      ),
    );
  }

  void _updateProvider(CameraProvider provider, CameraSetupConfig config) {
    _lastSyncedConfig = config;
    provider.updateSetupConfig(config);
  }

  InputDecoration _fieldDecoration(String label) {
    return InputDecoration(
      labelText: label,
      filled: true,
      fillColor: AppColors.background,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.4),
      ),
    );
  }
}

class _SetupTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final bool obscureText;
  final TextInputType? keyboardType;
  final ValueChanged<String> onChanged;

  const _SetupTextField({
    required this.controller,
    required this.label,
    required this.onChanged,
    this.obscureText = false,
    this.keyboardType,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        filled: true,
        fillColor: AppColors.background,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.primary, width: 1.4),
        ),
      ),
    );
  }
}

class _ActionStrip extends StatelessWidget {
  const _ActionStrip();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();

    return Column(
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: _ActionButton(
                icon: provider.autoRefresh ? Icons.pause : Icons.play_arrow,
                label: provider.autoRefresh ? '暂停画面' : '开始视频',
                color: AppColors.primary,
                onTap: provider.toggleFrameRefresh,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _ActionButton(
                icon: provider.audioListening
                    ? Icons.volume_up
                    : Icons.hearing_outlined,
                label: provider.audioListening
                    ? 'Listening ${provider.audioLevel}%'
                    : provider.audioConnecting
                        ? '音频连接中'
                        : '监听音频',
                color: provider.audioListening
                    ? AppColors.success
                    : AppColors.secondary,
                onTap: provider.toggleAudioListen,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        _ActionButton(
          icon: Icons.call_outlined,
          label: '语音对讲预留',
          color: AppColors.textSub,
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('双向对讲需要摄像头厂商 SDK 支持，当前暂未启用。'),
              ),
            );
          },
        ),
        if (provider.audioNotice != null) ...<Widget>[
          const SizedBox(height: 10),
          _InlineNotice(
            icon: provider.audioListening
                ? Icons.volume_up_outlined
                : Icons.info_outline,
            color:
                provider.audioListening ? AppColors.success : AppColors.primary,
            text: provider.audioNotice!,
          ),
        ],
      ],
    );
  }
}

class _PtzPanel extends StatelessWidget {
  const _PtzPanel();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            '云台控制',
            style: TextStyle(
              color: AppColors.textMain,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 18),
          Center(
            child: SizedBox(
              width: 190,
              height: 190,
              child: Stack(
                alignment: Alignment.center,
                children: <Widget>[
                  Container(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: <Color>[
                          AppColors.primary.withValues(alpha: 0.08),
                          AppColors.primary.withValues(alpha: 0.16),
                          AppColors.textMain.withValues(alpha: 0.08),
                        ],
                      ),
                    ),
                  ),
                  _PtzButton(
                    direction: 'up',
                    icon: Icons.keyboard_arrow_up,
                    alignment: Alignment.topCenter,
                    activeDirection: provider.activeDirection,
                    onStart: provider.startPtz,
                    onStop: provider.stopPtz,
                  ),
                  _PtzButton(
                    direction: 'down',
                    icon: Icons.keyboard_arrow_down,
                    alignment: Alignment.bottomCenter,
                    activeDirection: provider.activeDirection,
                    onStart: provider.startPtz,
                    onStop: provider.stopPtz,
                  ),
                  _PtzButton(
                    direction: 'left',
                    icon: Icons.keyboard_arrow_left,
                    alignment: Alignment.centerLeft,
                    activeDirection: provider.activeDirection,
                    onStart: provider.startPtz,
                    onStop: provider.stopPtz,
                  ),
                  _PtzButton(
                    direction: 'right',
                    icon: Icons.keyboard_arrow_right,
                    alignment: Alignment.centerRight,
                    activeDirection: provider.activeDirection,
                    onStart: provider.startPtz,
                    onStop: provider.stopPtz,
                  ),
                  Container(
                    width: 66,
                    height: 66,
                    decoration: const BoxDecoration(
                      color: AppColors.surface,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black12,
                          blurRadius: 12,
                          offset: Offset(0, 4),
                        ),
                      ],
                    ),
                    child:
                        const Icon(Icons.open_with, color: AppColors.primary),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticsPanel extends StatelessWidget {
  const _DiagnosticsPanel();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();
    final sourceFps = provider.streamStatus?.displayFps ?? 0;
    final latency = provider.status?.latencyMs;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.elderBlueBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.12)),
      ),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: <Widget>[
          _MetricChip(
              label: '客户端 ${provider.clientFps.toStringAsFixed(1)} fps'),
          if (sourceFps > 0)
            _MetricChip(label: '源帧率 ${sourceFps.toStringAsFixed(1)} fps'),
          if (latency != null)
            _MetricChip(label: '延迟 ${latency.toStringAsFixed(1)} ms'),
          _MetricChip(label: provider.audioStatus?.listenLabel ?? '音频检测中'),
          _MetricChip(label: '观看端 ${provider.streamStatus?.clients ?? 0}'),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel();

  @override
  Widget build(BuildContext context) {
    return Consumer<CameraProvider>(
      builder: (context, provider, child) {
        final error = provider.errorMessage;
        if (error == null || error.isEmpty) {
          return const SizedBox.shrink();
        }
        return _InlineNotice(
          icon: Icons.error_outline,
          color: AppColors.error,
          text: error,
        );
      },
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InlineNotice extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;

  const _InlineNotice({
    required this.icon,
    required this.color,
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.18)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w600,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String label;

  const _MetricChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.textSub,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  final String label;
  final bool isOnline;

  const _StatusPill({
    required this.label,
    required this.isOnline,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: isOnline
              ? AppColors.success.withValues(alpha: 0.5)
              : Colors.white24,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: isOnline ? AppColors.success : AppColors.warning,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _PtzButton extends StatelessWidget {
  final String direction;
  final IconData icon;
  final Alignment alignment;
  final String? activeDirection;
  final Future<void> Function(String direction) onStart;
  final Future<void> Function() onStop;

  const _PtzButton({
    required this.direction,
    required this.icon,
    required this.alignment,
    required this.activeDirection,
    required this.onStart,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    final active = activeDirection == direction;

    return Align(
      alignment: alignment,
      child: GestureDetector(
        onTapDown: (_) => onStart(direction),
        onTapUp: (_) => onStop(),
        onTapCancel: onStop,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          width: 58,
          height: 58,
          decoration: BoxDecoration(
            color: active ? AppColors.primary : AppColors.surface,
            shape: BoxShape.circle,
            boxShadow: const [
              BoxShadow(
                color: Colors.black12,
                blurRadius: 8,
                offset: Offset(0, 3),
              ),
            ],
          ),
          child: Icon(
            icon,
            color: active ? Colors.white : AppColors.textMain,
          ),
        ),
      ),
    );
  }
}
