import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import 'local_camera_preview_controller.dart';
import 'local_camera_preview_stub.dart'
    if (dart.library.html) 'local_camera_preview_web.dart';

class LocalCameraPreview extends StatefulWidget {
  final bool active;
  final ValueChanged<bool>? onReadyChanged;
  final ValueChanged<String?>? onErrorChanged;
  final ValueChanged<LocalCameraPreviewController?>? onControllerChanged;

  const LocalCameraPreview({
    super.key,
    required this.active,
    this.onReadyChanged,
    this.onErrorChanged,
    this.onControllerChanged,
  });

  @override
  State<LocalCameraPreview> createState() => _LocalCameraPreviewState();
}

class _LocalCameraPreviewState extends State<LocalCameraPreview> {
  late final LocalCameraPreviewController _controller;
  bool _controllerStarted = false;

  @override
  void initState() {
    super.initState();
    _controller = createLocalCameraPreviewController(
      onReadyChanged: widget.onReadyChanged,
      onErrorChanged: widget.onErrorChanged,
    );
    widget.onControllerChanged?.call(_controller);
  }

  @override
  void didUpdateWidget(covariant LocalCameraPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active == widget.active) return;
    if (widget.active) {
      _controllerStarted = false;
      _ensureStartedIfNeeded();
    } else {
      _controllerStarted = false;
      _controller.stop();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _ensureStartedIfNeeded();
  }

  @override
  void dispose() {
    widget.onControllerChanged?.call(null);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.active) {
      return const SizedBox.shrink();
    }
    if (!_controller.isSupported) {
      return const _UnsupportedPreview();
    }
    _ensureStartedIfNeeded();
    return _controller.build(context);
  }

  void _ensureStartedIfNeeded() {
    if (!widget.active || _controllerStarted) {
      return;
    }
    _controllerStarted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !widget.active) {
        _controllerStarted = false;
        return;
      }
      _controller.start();
    });
  }
}

class _UnsupportedPreview extends StatelessWidget {
  const _UnsupportedPreview();

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Color(0xFF0F172A),
      child: Center(
        child: Text(
          '本地摄像头流畅预览仅支持浏览器演示',
          style: TextStyle(
            color: Colors.white70,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

class LocalPreviewBadge extends StatelessWidget {
  final bool active;
  final bool ready;
  final String? error;

  const LocalPreviewBadge({
    super.key,
    required this.active,
    required this.ready,
    this.error,
  });

  @override
  Widget build(BuildContext context) {
    final label = !active
        ? '本地预览关闭'
        : error != null
            ? '本地预览异常'
            : ready
                ? '浏览器直连摄像头'
                : '请求摄像头权限';
    final color = error != null
        ? AppColors.error
        : ready
            ? AppColors.success
            : AppColors.primary;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.32)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
