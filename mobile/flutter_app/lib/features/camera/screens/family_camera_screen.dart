import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../providers/camera_provider.dart';

class FamilyCameraScreen extends StatelessWidget {
  const FamilyCameraScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          '家庭看护',
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
        children: <Widget>[
          const _VideoPanel(),
          const SizedBox(height: 16),
          const _ActionStrip(),
          const SizedBox(height: 16),
          const _PtzPanel(),
          const SizedBox(height: 16),
          const _DiagnosticsPanel(),
          Consumer<CameraProvider>(
            builder: (context, provider, child) {
              final error = provider.errorMessage;
              if (error == null) return const SizedBox.shrink();
              return Column(
                children: <Widget>[
                  const SizedBox(height: 12),
                  _InlineNotice(
                    icon: Icons.error_outline,
                    color: AppColors.error,
                    text: error,
                  ),
                ],
              );
            },
          ),
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
                      label: provider.status?.label ?? '检测中',
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
                          '家中实时画面',
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
            isConnecting ? '正在连接摄像头' : '暂无画面',
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
                label: provider.autoRefresh ? '暂停画面' : '继续查看',
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
                    ? '监听中 ${provider.audioLevel}%'
                    : provider.audioConnecting
                        ? '连接声音'
                        : '开始监听',
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
          label: '远程通话',
          color: AppColors.textSub,
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('移动端远程通话将接入厂商 SDK 后启用。')),
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
          _MetricChip(label: '前端 ${provider.clientFps.toStringAsFixed(1)}fps'),
          if (sourceFps > 0)
            _MetricChip(label: '源流 ${sourceFps.toStringAsFixed(1)}fps'),
          if (latency != null)
            _MetricChip(label: '延迟 ${latency.toStringAsFixed(1)}ms'),
          _MetricChip(label: provider.audioLabel),
          _MetricChip(
              label: provider.status?.online == true ? '摄像头在线' : '等待摄像头'),
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
    final isActive = activeDirection == direction;

    return Align(
      alignment: alignment,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) {
          onStart(direction);
        },
        onTapUp: (_) {
          onStop();
        },
        onTapCancel: () {
          onStop();
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          width: 62,
          height: 62,
          decoration: BoxDecoration(
            color: isActive
                ? AppColors.primary
                : Colors.white.withValues(alpha: 0.74),
            shape: BoxShape.circle,
          ),
          child: Icon(
            icon,
            size: 34,
            color: isActive ? Colors.white : AppColors.primary,
          ),
        ),
      ),
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
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        height: 56,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(icon, color: Colors.white, size: 22),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: isOnline
            ? AppColors.success.withValues(alpha: 0.9)
            : AppColors.textMain.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.12)),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.elderBlueText,
          fontSize: 13,
          fontWeight: FontWeight.w700,
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
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: <Widget>[
          Icon(icon, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: color,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
