import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../models/camera_models.dart';
import '../providers/camera_provider.dart';
import '../widgets/local_camera_preview.dart';
import '../widgets/local_camera_preview_controller.dart';

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
          _AiAnalysisPanel(),
          SizedBox(height: 16),
          _DiagnosticsPanel(),
          SizedBox(height: 16),
          _ErrorPanel(),
        ],
      ),
    );
  }
}

class _VideoPanel extends StatefulWidget {
  const _VideoPanel();

  @override
  State<_VideoPanel> createState() => _VideoPanelState();
}

class _VideoPanelState extends State<_VideoPanel> {
  bool _localPreviewReady = false;
  String? _localPreviewError;
  LocalCameraPreviewController? _localPreviewController;
  Timer? _analysisTimer;
  bool _capturingFrame = false;
  bool _didCaptureInitialFrame = false;

  @override
  void dispose() {
    _analysisTimer?.cancel();
    super.dispose();
  }

  void _syncAnalysisTimer({
    required bool autoRefresh,
    required bool useLocalPreview,
    required bool showingProcessedVideo,
  }) {
    final shouldRun = useLocalPreview &&
        showingProcessedVideo &&
        autoRefresh &&
        _localPreviewReady;
    if (!shouldRun) {
      _analysisTimer?.cancel();
      _analysisTimer = null;
      _didCaptureInitialFrame = false;
      return;
    }
    if (!_didCaptureInitialFrame) {
      _didCaptureInitialFrame = true;
      _captureFrameForAnalysis();
    }
    if (_analysisTimer != null) return;
    _analysisTimer = Timer.periodic(
      const Duration(milliseconds: 900),
      (_) => _captureFrameForAnalysis(),
    );
  }

  Future<void> _captureFrameForAnalysis() async {
    if (_capturingFrame || !mounted) return;
    _capturingFrame = true;
    try {
      final bytes = await _localPreviewController?.captureFrame();
      if (bytes == null || !mounted) return;
      await context.read<CameraProvider>().analyzeBrowserFrame(bytes);
    } finally {
      _capturingFrame = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.read<CameraProvider>();
    final useLocalPreview = context.select<CameraProvider, bool>(
      (provider) => provider.usesLocalPreview,
    );
    final autoRefresh = context.select<CameraProvider, bool>(
      (provider) => provider.autoRefresh,
    );
    final videoMode = context.select<CameraProvider, CameraVideoMode>(
      (provider) => provider.videoMode,
    );
    final frame = context.select<CameraProvider, Uint8List?>(
      (provider) => provider.frameBytes,
    );
    final showingProcessedVideo = videoMode == CameraVideoMode.processed;
    final useBridgeSource = context.select<CameraProvider, bool>(
      (provider) => provider.usesVideoBridgeSource,
    );
    _syncAnalysisTimer(
      autoRefresh: autoRefresh,
      useLocalPreview: useLocalPreview,
      showingProcessedVideo: showingProcessedVideo,
    );

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
                    child: useLocalPreview
                        ? LocalCameraPreview(
                            active: provider.autoRefresh,
                            onReadyChanged: (ready) {
                              if (!mounted) return;
                              setState(() => _localPreviewReady = ready);
                            },
                            onErrorChanged: (error) {
                              if (!mounted) return;
                              setState(() => _localPreviewError = error);
                            },
                            onControllerChanged: (controller) {
                              _localPreviewController = controller;
                            },
                          )
                        : frame == null
                            ? _VideoPlaceholder(
                                isConnecting: provider.isConnecting)
                            : Image.memory(
                                frame,
                                gaplessPlayback: true,
                                fit: BoxFit.contain,
                              ),
                  ),
                  Positioned(
                    left: 12,
                    top: 12,
                    child: useLocalPreview
                        ? LocalPreviewBadge(
                            active: provider.autoRefresh,
                            ready: _localPreviewReady,
                            error: _localPreviewError,
                          )
                        : _StatusPill(
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
                  if (showingProcessedVideo && !useBridgeSource)
                    const _PoseSkeletonOverlay(),
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
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
                              useLocalPreview
                                  ? (showingProcessedVideo
                                      ? '本地预览叠加后端姿态检测骨架'
                                      : '本地摄像头原始预览')
                                  : provider.endpointLabel,
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
                  const SizedBox(height: 14),
                  _VideoModeSwitch(
                    selected: videoMode,
                    onChanged: (mode) => unawaited(provider.setVideoMode(mode)),
                  ),
                  if (showingProcessedVideo) ...<Widget>[
                    const SizedBox(height: 10),
                    _InlineNotice(
                      icon: Icons.auto_awesome_motion_outlined,
                      color: AppColors.primary,
                      text: provider.processedOverlayNotice,
                    ),
                    const SizedBox(height: 8),
                    _InlineNotice(
                      icon: Icons.warning_amber_rounded,
                      color: AppColors.warning,
                      text: provider.fallDecisionNotice,
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VideoModeSwitch extends StatelessWidget {
  final CameraVideoMode selected;
  final ValueChanged<CameraVideoMode> onChanged;

  const _VideoModeSwitch({
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<CameraVideoMode>(
      segments: const <ButtonSegment<CameraVideoMode>>[
        ButtonSegment<CameraVideoMode>(
          value: CameraVideoMode.processed,
          icon: Icon(Icons.person_search_outlined),
          label: Text('处理后视频'),
        ),
        ButtonSegment<CameraVideoMode>(
          value: CameraVideoMode.raw,
          icon: Icon(Icons.videocam_outlined),
          label: Text('原视频'),
        ),
      ],
      selected: <CameraVideoMode>{selected},
      onSelectionChanged: (Set<CameraVideoMode> value) {
        if (value.isEmpty) return;
        onChanged(value.first);
      },
      style: ButtonStyle(
        visualDensity: VisualDensity.compact,
        textStyle: WidgetStateProperty.all(
          const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w800,
          ),
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
            const SizedBox(width: 10),
            Expanded(
              child: _ActionButton(
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
            ),
          ],
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
    final processedOverlay = provider.streamStatus?.processedOverlay;

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
          if (provider.usesVideoBridgeSource)
            _MetricChip(
              label: '视频服务 ${provider.videoBridgeStatus?.stateLabel ?? '检查中'}',
            ),
          _MetricChip(
              label: '客户端 ${provider.clientFps.toStringAsFixed(1)} fps'),
          if (sourceFps > 0)
            _MetricChip(label: '源帧率 ${sourceFps.toStringAsFixed(1)} fps'),
          if (provider.videoBridgeStatus?.latest?.overlayFps != null)
            _MetricChip(
              label:
                  '合成 ${provider.videoBridgeStatus!.latest!.overlayFps!.toStringAsFixed(1)} fps',
            ),
          if (provider.videoBridgeStatus?.latest?.frameAgeMs != null)
            _MetricChip(
              label: '帧龄 ${provider.videoBridgeStatus!.latest!.frameAgeMs} ms',
            ),
          if (latency != null)
            _MetricChip(label: '延迟 ${latency.toStringAsFixed(1)} ms'),
          if (!provider.usesVideoBridgeSource && processedOverlay != null)
            _MetricChip(label: '处理流 ${processedOverlay.label}'),
          _MetricChip(label: provider.audioStatus?.listenLabel ?? '音频检测中'),
          _MetricChip(label: '观看端 ${provider.streamStatus?.clients ?? 0}'),
        ],
      ),
    );
  }
}

class _AiAnalysisPanel extends StatelessWidget {
  const _AiAnalysisPanel();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();
    if (provider.usesVideoBridgeSource) {
      return const _BridgeAnalysisPanel();
    }
    final poseStatus = provider.poseDetectionStatus;
    final fallStatus = provider.fallDetectionStatus;
    final poseLatest = provider.poseLatest;
    final primaryTrack = poseLatest?.primaryTrack;
    final multimodal = fallStatus?.multimodalReview;
    final reviewProvider =
        multimodal?['resolved_provider']?.toString() ?? 'none';
    final reviewEnabled = multimodal?['enabled'] == true;
    final fallEvent = fallStatus?.lastEvent;
    final fallDetected = fallEvent?['fall_detected'] == true;
    final fallStatusText = fallEvent?['status']?.toString();
    final fallScore = _toPercent(fallEvent?['fall_score']);
    final analysisAt = provider.lastAiAnalysisAt;
    final analysisState = provider.aiAnalysisRunning
        ? '正在分析'
        : analysisAt == null
            ? '等待首帧'
            : '最近 ${_formatTime(analysisAt)}';

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
            'AI 姿态与跌倒分析',
            style: TextStyle(
              color: AppColors.textMain,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _MetricChip(label: '单帧分析 $analysisState'),
              _MetricChip(label: '姿态 ${poseStatus?.stateLabel ?? '检查中'}'),
              _MetricChip(label: '跌倒 ${fallStatus?.stateLabel ?? '检查中'}'),
              _MetricChip(label: '目标数 ${poseLatest?.tracks.length ?? 0}'),
              _MetricChip(
                label: '多模态复核 ${reviewEnabled ? reviewProvider : '未启用'}',
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _ModelToggleButton(
                label: '姿态检测模型',
                enabled: poseStatus?.enabled == true,
                updating: provider.poseDetectionUpdating,
                onPressed: () {
                  provider
                      .setPoseDetectionEnabled(!(poseStatus?.enabled == true));
                },
              ),
              _ModelToggleButton(
                label: '跌倒检测模型',
                enabled: fallStatus?.enabled == true,
                updating: provider.fallDetectionUpdating,
                onPressed: () {
                  provider
                      .setFallDetectionEnabled(!(fallStatus?.enabled == true));
                },
              ),
            ],
          ),
          const SizedBox(height: 14),
          _AnalysisRow(
            label: 'posture',
            value: poseLatest?.postureLabel ?? '暂无结果',
            color: primaryTrack?.isRisk == true
                ? AppColors.error
                : AppColors.primary,
          ),
          _AnalysisRow(
            label: 'posture event',
            value: primaryTrack == null ? '暂无人体目标' : primaryTrack.eventLabel,
            color: primaryTrack?.isRisk == true
                ? AppColors.error
                : primaryTrack?.isWarning == true
                    ? AppColors.warning
                    : AppColors.success,
          ),
          _AnalysisRow(
            label: 'quality / confidence',
            value: primaryTrack == null
                ? '等待关键点'
                : '关键点 ${primaryTrack.keypoints.length} 个 / pose ${(primaryTrack.poseScore * 100).toStringAsFixed(0)}% / state ${(primaryTrack.stateScore * 100).toStringAsFixed(0)}%',
            color: AppColors.textSub,
          ),
          _AnalysisRow(
            label: 'fall risk',
            value: fallEvent == null
                ? '等待跌倒分析'
                : fallDetected
                    ? '疑似跌倒，风险 ${fallScore ?? '--'}'
                    : '未见明确跌倒线索${fallStatusText == null ? '' : '（$fallStatusText）'}',
            color: fallDetected ? AppColors.error : AppColors.success,
          ),
          _AnalysisRow(
            label: 'multimodal review',
            value: reviewEnabled ? '已启用，当前通道：$reviewProvider' : '未启用或未配置复核通道',
            color: reviewEnabled ? AppColors.primary : AppColors.textSub,
          ),
          if (fallStatus?.lastError != null)
            _AnalysisRow(
              label: 'fall error',
              value: fallStatus!.lastError!,
              color: AppColors.warning,
            ),
          if (poseStatus?.lastError != null)
            _AnalysisRow(
              label: 'pose error',
              value: poseStatus!.lastError!,
              color: AppColors.warning,
            ),
          if (provider.lastAiAnalysisError != null)
            _AnalysisRow(
              label: 'worker error',
              value: provider.lastAiAnalysisError!,
              color: AppColors.warning,
            ),
        ],
      ),
    );
  }

  static String? _toPercent(Object? value) {
    final number = value is num ? value.toDouble() : double.tryParse('$value');
    if (number == null) return null;
    return '${(number * 100).clamp(0, 100).toStringAsFixed(0)}%';
  }

  static String _formatTime(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    final second = time.second.toString().padLeft(2, '0');
    return '$hour:$minute:$second';
  }
}

class _BridgeAnalysisPanel extends StatefulWidget {
  const _BridgeAnalysisPanel();

  @override
  State<_BridgeAnalysisPanel> createState() => _BridgeAnalysisPanelState();
}

class _BridgeAnalysisPanelState extends State<_BridgeAnalysisPanel> {
  late final TextEditingController _hostController;

  @override
  void initState() {
    super.initState();
    _hostController = TextEditingController(text: '192.168.8.253');
  }

  @override
  void dispose() {
    _hostController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CameraProvider>();
    final bridge = provider.videoBridgeStatus;
    final latest = bridge?.latest;
    final vision = bridge?.visionService;
    final riskColor = latest?.hasRisk == true
        ? AppColors.error
        : latest?.risk == 'medium'
            ? AppColors.warning
            : AppColors.success;
    final fallProb = latest?.fallProb == null
        ? '--'
        : '${(latest!.fallProb! * 100).clamp(0, 100).toStringAsFixed(0)}%';
    final displaySource = latest?.displaySource ??
        vision?.sourceValue('display_source_current') ??
        '--';
    final analysisSource = latest?.analysisSource ?? 'analysis';

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
            '视频服务风险状态',
            style: TextStyle(
              color: AppColors.textMain,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _MetricChip(label: 'bridge ${bridge?.stateLabel ?? '检查中'}'),
              _MetricChip(label: 'adapter ${bridge?.adapterVersion ?? '--'}'),
              _MetricChip(label: '摄像头 ${latest?.cameraId ?? '--'}'),
              _MetricChip(label: '流 ${latest?.streamName ?? '--'}'),
            ],
          ),
          const SizedBox(height: 14),
          _AnalysisRow(
            label: 'vision url',
            value: vision?.baseUrl.isNotEmpty == true
                ? vision!.baseUrl
                : '等待主系统视觉服务配置',
            color: AppColors.textSub,
          ),
          _AnalysisRow(
            label: 'source',
            value: 'display $displaySource / analysis $analysisSource',
            color: AppColors.textSub,
          ),
          _AnalysisRow(
            label: 'service',
            value: latest?.serviceStateLabel ?? '等待视频服务',
            color: latest?.isOnline == true
                ? AppColors.success
                : AppColors.warning,
          ),
          _AnalysisRow(
            label: 'target',
            value: latest?.targetLabel ?? '等待目标识别',
            color: AppColors.primary,
          ),
          _AnalysisRow(
            label: 'fall risk',
            value: latest == null
                ? '等待视频服务风险数据'
                : '${latest.riskLabel} · ${latest.fallStateLabel} · $fallProb',
            color: riskColor,
          ),
          _AnalysisRow(
            label: 'track',
            value: latest?.trackId ?? '暂无 track_id',
            color: AppColors.textSub,
          ),
          _AnalysisRow(
            label: 'vision action',
            value: provider.visionActionMessage ?? '可手动拉取、探测或切换视觉服务拉流',
            color: provider.visionActionMessage == null
                ? AppColors.textSub
                : AppColors.success,
          ),
          if (vision?.lastError != null && vision!.lastError!.isNotEmpty)
            _AnalysisRow(
              label: 'vision error',
              value: vision.lastError!,
              color: AppColors.warning,
            ),
          const SizedBox(height: 14),
          TextField(
            controller: _hostController,
            decoration: InputDecoration(
              labelText: '摄像头 IP',
              hintText: '192.168.8.253',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
              ),
              isDense: true,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _VisionActionButton(
                icon: Icons.refresh,
                label: '拉取结果',
                busy: provider.visionActionRunning,
                onPressed: provider.pollVisionServiceOnce,
              ),
              _VisionActionButton(
                icon: Icons.radar_outlined,
                label: '探测',
                busy: provider.visionActionRunning,
                onPressed: () => provider.probeVisionHost(_hostController.text),
              ),
              _VisionActionButton(
                icon: Icons.swap_horiz,
                label: '切换拉流',
                busy: provider.visionActionRunning,
                onPressed: () => provider.switchVisionHost(_hostController.text),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _AnalysisRow(
            label: 'snapshot',
            value: latest?.snapshotUrl ?? '等待视频服务快照 URL',
            color: AppColors.textSub,
          ),
        ],
      ),
    );
  }
}

class _ModelToggleButton extends StatelessWidget {
  final String label;
  final bool enabled;
  final bool updating;
  final VoidCallback onPressed;

  const _ModelToggleButton({
    required this.label,
    required this.enabled,
    required this.updating,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final color = enabled ? AppColors.success : AppColors.primary;
    final text = updating
        ? '处理中...'
        : enabled
            ? '关闭$label'
            : '开启$label';
    return OutlinedButton.icon(
      onPressed: updating ? null : onPressed,
      icon: updating
          ? SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: color,
              ),
            )
          : Icon(enabled ? Icons.power_settings_new : Icons.play_arrow),
      label: Text(text),
      style: OutlinedButton.styleFrom(
        foregroundColor: color,
        side: BorderSide(color: color.withValues(alpha: 0.38)),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        textStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _VisionActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool busy;
  final VoidCallback onPressed;

  const _VisionActionButton({
    required this.icon,
    required this.label,
    required this.busy,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: busy ? null : onPressed,
      icon: busy
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Icon(icon),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.primary,
        side: BorderSide(color: AppColors.primary.withValues(alpha: 0.32)),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        textStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _AnalysisRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _AnalysisRow({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 118,
            child: Text(
              label,
              style: const TextStyle(
                color: AppColors.textSub,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: color,
                fontSize: 15,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PoseSkeletonPainter extends CustomPainter {
  final PoseTrack track;
  final int frameWidth;
  final int frameHeight;

  const _PoseSkeletonPainter({
    required this.track,
    required this.frameWidth,
    required this.frameHeight,
  });

  static const List<(int, int)> _bones = <(int, int)>[
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (0, 5),
    (0, 6),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    if (frameWidth <= 0 || frameHeight <= 0 || track.keypoints.isEmpty) {
      return;
    }

    final scale =
        (size.width / frameWidth).clamp(0.0, size.height / frameHeight);
    final drawWidth = frameWidth * scale;
    final drawHeight = frameHeight * scale;
    final dx = (size.width - drawWidth) / 2;
    final dy = (size.height - drawHeight) / 2;
    Offset point(PoseKeypoint kp) =>
        Offset(dx + kp.x * scale, dy + kp.y * scale);

    final bonePaint = Paint()
      ..color = track.isRisk
          ? AppColors.error.withValues(alpha: 0.92)
          : AppColors.success.withValues(alpha: 0.92)
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final pointPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
    final haloPaint = Paint()
      ..color = AppColors.primary.withValues(alpha: 0.52)
      ..style = PaintingStyle.fill;

    for (final bone in _bones) {
      final a = bone.$1;
      final b = bone.$2;
      if (a >= track.keypoints.length || b >= track.keypoints.length) continue;
      final pa = track.keypoints[a];
      final pb = track.keypoints[b];
      if (pa.confidence < 0.2 || pb.confidence < 0.2) continue;
      canvas.drawLine(point(pa), point(pb), bonePaint);
    }

    for (final kp in track.keypoints) {
      if (kp.confidence < 0.2) continue;
      final p = point(kp);
      canvas.drawCircle(p, 5, haloPaint);
      canvas.drawCircle(p, 2.5, pointPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _PoseSkeletonPainter oldDelegate) {
    return oldDelegate.track != track ||
        oldDelegate.frameWidth != frameWidth ||
        oldDelegate.frameHeight != frameHeight;
  }
}

class _PoseSkeletonOverlay extends StatelessWidget {
  const _PoseSkeletonOverlay();

  @override
  Widget build(BuildContext context) {
    final poseLatest = context.select<CameraProvider, PoseDetectionLatest?>(
      (provider) => provider.poseLatest,
    );
    final primaryTrack = poseLatest?.primaryTrack;
    if (poseLatest == null || primaryTrack == null) {
      return const SizedBox.shrink();
    }
    return Positioned.fill(
      child: IgnorePointer(
        child: RepaintBoundary(
          child: CustomPaint(
            painter: _PoseSkeletonPainter(
              track: primaryTrack,
              frameWidth: poseLatest.frameWidth,
              frameHeight: poseLatest.frameHeight,
            ),
          ),
        ),
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
