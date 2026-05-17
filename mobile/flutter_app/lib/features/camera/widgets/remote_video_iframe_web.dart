import 'dart:ui_web' as ui_web;
import 'dart:html' as html;

import 'package:flutter/material.dart';

class RemoteVideoIframeWeb extends StatefulWidget {
  final String previewUrl;

  const RemoteVideoIframeWeb({
    super.key,
    required this.previewUrl,
  });

  @override
  State<RemoteVideoIframeWeb> createState() => _RemoteVideoIframeWebState();
}

class _RemoteVideoIframeWebState extends State<RemoteVideoIframeWeb> {
  late final String _viewType;
  late final html.IFrameElement _iframe;
  bool _registered = false;

  @override
  void initState() {
    super.initState();
    _viewType = 'remote-video-iframe-${DateTime.now().microsecondsSinceEpoch}';
    _iframe = html.IFrameElement()
      ..src = widget.previewUrl
      ..style.border = '0'
      ..style.width = '100%'
      ..style.height = '100%'
      ..allow = 'autoplay; fullscreen';
    _register();
  }

  @override
  void didUpdateWidget(covariant RemoteVideoIframeWeb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.previewUrl != widget.previewUrl) {
      _iframe.src = widget.previewUrl;
    }
  }

  void _register() {
    if (_registered) return;
    ui_web.platformViewRegistry.registerViewFactory(
      _viewType,
      (int viewId) => _iframe,
    );
    _registered = true;
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }
}
