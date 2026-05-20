import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/health_provider.dart';
import '../repositories/health_repository.dart';
import 'device_detail_screen.dart';

class DeviceDetailRoute extends StatelessWidget {
  final String deviceMac;

  const DeviceDetailRoute({super.key, required this.deviceMac});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<HealthProvider>(
      create: (context) {
        final provider = HealthProvider(
          context.read<HealthRepository>(),
          deviceMac,
        );
        unawaited(provider.init());
        return provider;
      },
      child: DeviceDetailScreen(deviceMac: deviceMac),
    );
  }
}
