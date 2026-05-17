import 'dart:async';
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

class RemoteMjpegStreamWeb extends StatefulWidget {
  final String streamUrl;
  final bool active;
  final ValueChanged<double>? onReceiveFpsChanged;
  final ValueChanged<double>? onClientFpsChanged;
  final ValueChanged<bool>? onReadyChanged;
  final ValueChanged<String?>? onErrorChanged;

  const RemoteMjpegStreamWeb({
    super.key,
    required this.streamUrl,
    required this.active,
    this.onReceiveFpsChanged,
    this.onClientFpsChanged,
    this.onReadyChanged,
    this.onErrorChanged,
  });

  @override
  State<RemoteMjpegStreamWeb> createState() => _RemoteMjpegStreamWebState();
}

class _RemoteMjpegStreamWebState extends State<RemoteMjpegStreamWeb> {
  late final html.ImageElement _image;
  late final String _viewType;
  Timer? _fpsTimer;
  Timer? _pollTimer;
  int _loadEvents = 0;
  DateTime _fpsWindowStartedAt = DateTime.now();
  bool _registered = false;
  bool _requestInFlight = false;

  @override
  void initState() {
    super.initState();
    _viewType =
        'remote-mjpeg-stream-${DateTime.now().microsecondsSinceEpoch}';
    _image = html.ImageElement()
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.objectFit = 'contain'
      ..style.backgroundColor = '#0F172A';
    _image.onLoad.listen((_) => _handleFrameLoaded());
    _image.onError.listen((_) {
      _requestInFlight = false;
      widget.onErrorChanged?.call('MJPEG stream load failed');
      widget.onReadyChanged?.call(false);
    });
    _registerViewFactory();
    _applyActiveState();
  }

  @override
  void didUpdateWidget(covariant RemoteMjpegStreamWeb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.streamUrl != widget.streamUrl ||
        oldWidget.active != widget.active) {
      _applyActiveState();
    }
  }

  @override
  void dispose() {
    _fpsTimer?.cancel();
    _pollTimer?.cancel();
    _image.src = '';
    super.dispose();
  }

  void _registerViewFactory() {
    if (_registered) return;
    ui_web.platformViewRegistry.registerViewFactory(
      _viewType,
      (int viewId) => _image,
    );
    _registered = true;
  }

  void _applyActiveState() {
    _fpsTimer?.cancel();
    _pollTimer?.cancel();
    _loadEvents = 0;
    _fpsWindowStartedAt = DateTime.now();
    _requestInFlight = false;
    _emitAfterFrame(() => widget.onReceiveFpsChanged?.call(0));
    _emitAfterFrame(() => widget.onClientFpsChanged?.call(0));
    _emitAfterFrame(() => widget.onReadyChanged?.call(false));
    _emitAfterFrame(() => widget.onErrorChanged?.call(null));
    if (!widget.active) {
      _image.src = '';
      return;
    }
    _requestLatestFrame();
    _pollTimer = Timer.periodic(
      const Duration(milliseconds: 110),
      (_) => _requestLatestFrame(),
    );
    _fpsTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      final elapsed =
          DateTime.now().difference(_fpsWindowStartedAt).inMilliseconds / 1000;
      if (elapsed <= 0) {
        return;
      }
      final fps = _loadEvents / elapsed;
      _emitAfterFrame(() => widget.onReceiveFpsChanged?.call(fps));
      _emitAfterFrame(() => widget.onClientFpsChanged?.call(fps));
      _loadEvents = 0;
      _fpsWindowStartedAt = DateTime.now();
    });
  }

  void _requestLatestFrame() {
    if (!widget.active || _requestInFlight) {
      return;
    }
    _requestInFlight = true;
    final ts = DateTime.now().microsecondsSinceEpoch;
    final separator = widget.streamUrl.contains('?') ? '&' : '?';
    _image.src = '${widget.streamUrl}${separator}ts=$ts';
  }

  void _handleFrameLoaded() {
    _requestInFlight = false;
    _loadEvents += 1;
    _emitAfterFrame(() => widget.onReadyChanged?.call(true));
    _emitAfterFrame(() => widget.onErrorChanged?.call(null));
  }

  void _emitAfterFrame(VoidCallback callback) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      callback();
    });
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }
}
