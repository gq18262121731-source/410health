import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../core/services/app_notification_service.dart';
import '../../../core/services/audio_service.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/alarm_model.dart';
import '../providers/alarm_provider.dart';

class GlobalAlarmListener extends StatefulWidget {
  final Widget child;

  const GlobalAlarmListener({
    super.key,
    required this.child,
  });

  @override
  State<GlobalAlarmListener> createState() => _GlobalAlarmListenerState();
}

class _GlobalAlarmListenerState extends State<GlobalAlarmListener> with WidgetsBindingObserver {
  static const Duration _freshAlarmWindow = Duration(minutes: 2);
  static const Duration _fallbackToneInterval = Duration(milliseconds: 1200);

  final Set<String> _shownAlarmIds = <String>{};
  final List<AlarmRecord> _pendingAlarms = <AlarmRecord>[];

  AlarmProvider? _alarmProvider;
  AudioService? _audioService;
  AppNotificationService? _notificationService;
  bool _initializedSnapshot = false;
  bool _dialogVisible = false;
  bool _appInForeground = true;
  OverlayEntry? _floatingWarningEntry;
  Timer? _floatingWarningTimer;
  Timer? _fallbackToneTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final provider = context.read<AlarmProvider>();
    if (!identical(_alarmProvider, provider)) {
      _alarmProvider?.removeListener(_onAlarmChanged);
      _alarmProvider = provider;
      _alarmProvider?.addListener(_onAlarmChanged);
    }
    _audioService ??= context.read<AudioService>();
    _notificationService ??= context.read<AppNotificationService>();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _alarmProvider?.removeListener(_onAlarmChanged);
    _stopAlarmToneLoop();
    _hideFloatingWarning();
    unawaited(_notificationService?.clearAllSosNotifications());
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _appInForeground = state == AppLifecycleState.resumed;
    if (state != AppLifecycleState.resumed) {
      return;
    }
    final provider = _alarmProvider;
    if (provider == null) {
      return;
    }
    unawaited(provider.resyncAfterForegroundResume());
  }

  void _onAlarmChanged() {
    if (!mounted) {
      return;
    }

    final provider = _alarmProvider;
    if (provider == null) {
      return;
    }

    if (provider.status == AlarmLoadStatus.initial) {
      _shownAlarmIds.clear();
      _pendingAlarms.clear();
      _initializedSnapshot = false;
      _dialogVisible = false;
      _stopAlarmToneLoop();
      _hideFloatingWarning();
      unawaited(_notificationService?.clearAllSosNotifications());
      return;
    }

    if (provider.status != AlarmLoadStatus.loaded) {
      _stopAlarmToneLoop();
      return;
    }

    _syncAlarmToneState(provider);
    _syncSystemNotificationState(provider);

    if (!_initializedSnapshot) {
      for (final alarm in provider.alarms) {
        if (_shouldPresentInitialAlarm(alarm)) {
          _shownAlarmIds.add(alarm.id);
          _enqueueAlarm(alarm);
          continue;
        }
        _shownAlarmIds.add(alarm.id);
      }
      _initializedSnapshot = true;
      return;
    }

    for (final alarm in provider.alarms) {
      if (_shouldPresentRealtimeAlarm(alarm)) {
        _shownAlarmIds.add(alarm.id);
        _enqueueAlarm(alarm);
      }
    }
  }

  bool _shouldPresentInitialAlarm(AlarmRecord alarm) {
    return !_shownAlarmIds.contains(alarm.id) &&
        !alarm.acknowledged &&
        alarm.isSos &&
        _isFreshAlarm(alarm);
  }

  bool _shouldPresentRealtimeAlarm(AlarmRecord alarm) {
    return !_shownAlarmIds.contains(alarm.id) &&
        !alarm.acknowledged &&
        alarm.isSos;
  }

  bool _isFreshAlarm(AlarmRecord alarm) {
    final createdAt = alarm.createdAtDateTime;
    if (createdAt == null) {
      return false;
    }
    final age = DateTime.now().difference(createdAt).abs();
    return age <= _freshAlarmWindow;
  }

  void _syncAlarmToneState(AlarmProvider provider) {
    final hasActiveSos = provider.alarms.any((alarm) => alarm.isSos && !alarm.acknowledged);
    if (hasActiveSos) {
      _startAlarmToneLoop();
      return;
    }
    _stopAlarmToneLoop();
  }

  void _syncSystemNotificationState(AlarmProvider provider) {
    final notificationService = _notificationService;
    if (notificationService == null) {
      return;
    }
    unawaited(
      notificationService.syncActiveSosNotifications(
        provider.alarms.where((alarm) => alarm.isSos && !alarm.acknowledged),
        appInForeground: _appInForeground,
      ),
    );
  }

  void _startAlarmToneLoop() {
    unawaited(_startAlarmToneLoopAsync());
  }

  void _stopAlarmToneLoop() {
    _stopFallbackToneLoop();
    _audioService?.stopAlarmLoop();
  }

  Future<void> _startAlarmToneLoopAsync() async {
    final started = await (_audioService?.startAlarmLoop() ?? Future.value(false));
    if (started) {
      _stopFallbackToneLoop();
      return;
    }
    _startFallbackToneLoop();
  }

  void _startFallbackToneLoop() {
    if (_fallbackToneTimer != null) {
      return;
    }
    unawaited(SystemSound.play(SystemSoundType.alert));
    _fallbackToneTimer = Timer.periodic(_fallbackToneInterval, (_) {
      unawaited(SystemSound.play(SystemSoundType.alert));
    });
  }

  void _stopFallbackToneLoop() {
    _fallbackToneTimer?.cancel();
    _fallbackToneTimer = null;
  }

  bool _isFamilyUser() {
    final role = context.read<AuthProvider>().user?.role.toLowerCase();
    return role == 'family';
  }

  String _resolveAlarmLead(AlarmRecord alarm) {
    final elderName = alarm.elderName;
    final apartment = alarm.apartment;
    if (elderName != null && apartment != null) {
      return '$elderName / $apartment';
    }
    if (elderName != null) {
      return elderName;
    }
    return 'SOS 紧急求助';
  }

  String _resolveAlarmBody(AlarmRecord alarm) {
    final parts = <String>[];
    if (alarm.deviceName != null) {
      parts.add('设备 ${alarm.deviceName}');
    }
    parts.add(alarm.sosTriggerLabel);
    return parts.join(' · ');
  }

  void _showFloatingWarning(AlarmRecord alarm) {
    if (!mounted || !_isFamilyUser()) {
      return;
    }
    final overlay = Overlay.of(context, rootOverlay: true);

    _floatingWarningTimer?.cancel();
    _floatingWarningEntry?.remove();

    _floatingWarningEntry = OverlayEntry(
      builder: (_) => SafeArea(
        child: Align(
          alignment: Alignment.topCenter,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
            child: Material(
              color: Colors.transparent,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFF7F1D1D),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFFCA5A5), width: 1.2),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x33000000),
                      blurRadius: 12,
                      offset: Offset(0, 6),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Color(0xFFFECACA), size: 22),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text(
                            'SOS 紧急告警',
                            style: TextStyle(
                              color: Color(0xFFFFF1F2),
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                            ),
                          ),
                          Text(
                            _resolveAlarmLead(alarm),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFFFEE2E2),
                              fontSize: 12,
                              height: 1.3,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _resolveAlarmBody(alarm),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Color(0xFFFECACA),
                              fontSize: 11,
                              height: 1.3,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );

    overlay.insert(_floatingWarningEntry!);
    _floatingWarningTimer = Timer(const Duration(seconds: 4), _hideFloatingWarning);
  }

  void _hideFloatingWarning() {
    _floatingWarningTimer?.cancel();
    _floatingWarningTimer = null;
    _floatingWarningEntry?.remove();
    _floatingWarningEntry = null;
  }

  void _enqueueAlarm(AlarmRecord alarm) {
    _showFloatingWarning(alarm);
    if (_dialogVisible) {
      final alreadyQueued = _pendingAlarms.any((item) => item.id == alarm.id);
      if (!alreadyQueued) {
        _pendingAlarms.add(alarm);
      }
      return;
    }

    _dialogVisible = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        _dialogVisible = false;
        return;
      }
      unawaited(_showAlarmDialog(alarm));
    });
  }

  Future<void> _showAlarmDialog(AlarmRecord alarm) async {
    if (!mounted) {
      _dialogVisible = false;
      return;
    }

    _startAlarmToneLoop();
    await showDialog<void>(
      context: context,
      useRootNavigator: true,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF1A0A0A),
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: Colors.redAccent, width: 2),
          borderRadius: BorderRadius.circular(16),
        ),
        title: const Row(
          children: [
            Icon(Icons.warning, color: Colors.redAccent, size: 28),
            SizedBox(width: 12),
            Text(
              '紧急求助报警',
              style: TextStyle(
                color: Colors.redAccent,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _resolveAlarmLead(alarm),
              style: const TextStyle(
                color: Color(0xFFF8FAFC),
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            if (alarm.deviceName != null) ...[
              Text(
                '设备: ${alarm.deviceName}',
                style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 15),
              ),
              const SizedBox(height: 6),
            ],
            if (alarm.deviceMac.isNotEmpty) ...[
              Text(
                '设备 MAC: ${alarm.deviceMac}',
                style: const TextStyle(color: Color(0xFFF8FAFC), fontSize: 16),
              ),
              const SizedBox(height: 8),
            ],
            Text(
              '时间: ${alarm.createdAtDisplay}',
              style: const TextStyle(color: Color(0xFFCBD5E1)),
            ),
            const SizedBox(height: 8),
            Text(
              '触发方式: ${alarm.sosTriggerLabel}',
              style: const TextStyle(color: Color(0xFFCBD5E1)),
            ),
            const SizedBox(height: 12),
            Text(
              alarm.message.isNotEmpty
                  ? alarm.message
                  : '已检测到紧急求助，请立即联系老人或通知社区值守人员。',
              style: const TextStyle(color: Color(0xFFE2E8F0)),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              _stopAlarmToneLoop();
              _hideFloatingWarning();
              _alarmProvider?.acknowledge(alarm.id);
              Navigator.pop(dialogContext);
            },
            child: const Text(
              '我知道了',
              style: TextStyle(
                color: Colors.redAccent,
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ),
        ],
      ),
    );

    _dialogVisible = false;
    if (!mounted || _pendingAlarms.isEmpty) {
      return;
    }

    final nextAlarm = _pendingAlarms.removeAt(0);
    _showFloatingWarning(nextAlarm);
    unawaited(_showAlarmDialog(nextAlarm));
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}
