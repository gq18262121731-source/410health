import 'package:flutter/material.dart';

class RemoteMjpegStreamWeb extends StatelessWidget {
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
  Widget build(BuildContext context) {
    return const SizedBox.shrink();
  }
}
