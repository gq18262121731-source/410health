import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/history_provider.dart';
import '../repositories/health_repository.dart';
import 'history_screen.dart';

class HistoryRoute extends StatelessWidget {
  final String deviceMac;

  const HistoryRoute({super.key, required this.deviceMac});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<HistoryProvider>(
      create: (context) {
        final provider = HistoryProvider(
          context.read<HealthRepository>(),
          deviceMac,
        );
        unawaited(provider.fetchHistory());
        return provider;
      },
      child: HistoryScreen(deviceMac: deviceMac),
    );
  }
}
