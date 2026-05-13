import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../core/services/app_notification_service.dart';
import '../../../core/services/audio_service.dart';
import '../../auth/providers/auth_provider.dart';
import '../../camera/providers/camera_provider.dart';
import '../../camera/repositories/camera_repository.dart';
import '../../camera/screens/family_camera_screen.dart';
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

class _GlobalAlarmListenerState extends State<GlobalAlarmListener>
    with WidgetsBindingObserver {
  static const Duration _fallbackToneInterval =
      Duration(milliseconds: 1200);
  static const Duration _freshAlarmWindow = Duration(minutes: 2);

  final Set<String> _shownAlarmIds = <String>{};
  final Set<String> _shownFallIncidentIds = <String>{};
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
      _shownFallIncidentIds.clear();
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
          _markAlarmPresented(alarm);
          _enqueueAlarm(alarm);
          continue;
        }
        _markAlarmSeen(alarm);
      }
      _initializedSnapshot = true;
      return;
    }

    for (final alarm in provider.alarms) {
      if (_shouldPresentRealtimeAlarm(alarm)) {
        _markAlarmPresented(alarm);
        _enqueueAlarm(alarm);
      }
    }
  }

  bool _shouldPresentInitialAlarm(AlarmRecord alarm) {
    if (alarm.acknowledged) {
      return false;
    }
    if (alarm.isSos) {
      return !_shownAlarmIds.contains(alarm.id) && _isFreshAlarm(alarm);
    }
    if (alarm.isFall) {
      final incidentId = alarm.incidentId;
      return incidentId != null &&
          incidentId.isNotEmpty &&
          !_shownFallIncidentIds.contains(incidentId) &&
          alarm.showImmediatePopup;
    }
    return false;
  }

  bool _shouldPresentRealtimeAlarm(AlarmRecord alarm) {
    if (alarm.acknowledged) {
      return false;
    }
    if (alarm.isSos) {
      return !_shownAlarmIds.contains(alarm.id);
    }
    if (alarm.isFall) {
      final incidentId = alarm.incidentId;
      return incidentId != null &&
          incidentId.isNotEmpty &&
          !_shownFallIncidentIds.contains(incidentId) &&
          alarm.showImmediatePopup;
    }
    return false;
  }

  void _markAlarmPresented(AlarmRecord alarm) {
    _shownAlarmIds.add(alarm.id);
    final incidentId = alarm.incidentId;
    if (alarm.isFall && incidentId != null && incidentId.isNotEmpty) {
      _shownFallIncidentIds.add(incidentId);
    }
  }

  void _markAlarmSeen(AlarmRecord alarm) {
    _shownAlarmIds.add(alarm.id);
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
    final hasAudibleAlarm = provider.alarms.any(
      (alarm) =>
          !alarm.acknowledged &&
          (alarm.isSos ||
              (alarm.isFall &&
                  alarm.showImmediatePopup &&
                  (alarm.alarmLevel == 'critical' ||
                      alarm.alarmLevel == 'warning'))),
    );
    if (hasAudibleAlarm) {
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
    final started =
        await (_audioService?.startAlarmLoop() ?? Future.value(false));
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
    return alarm.isFall ? '跌倒风险提醒' : 'SOS 紧急求助';
  }

  String _resolveAlarmBody(AlarmRecord alarm) {
    if (alarm.isFall) {
      final lead = alarm.fallLead;
      if (lead != null && lead.isNotEmpty) {
        return lead;
      }
      return alarm.message;
    }
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFF7F1D1D),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: const Color(0xFFFCA5A5),
                    width: 1.2,
                  ),
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
                    const Icon(
                      Icons.warning_amber_rounded,
                      color: Color(0xFFFECACA),
                      size: 22,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            alarm.isFall
                                ? alarm.fallSeverityLabel
                                : 'SOS 紧急告警',
                            style: const TextStyle(
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
    _floatingWarningTimer =
        Timer(const Duration(seconds: 4), _hideFloatingWarning);
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
      final alreadyQueued = _pendingAlarms.any(
        (item) =>
            item.id == alarm.id ||
            (item.isFall &&
                alarm.isFall &&
                item.incidentId != null &&
                item.incidentId == alarm.incidentId),
      );
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

  Future<void> _showAlarmDialog(AlarmRecord initialAlarm) async {
    if (!mounted) {
      _dialogVisible = false;
      return;
    }

    _startAlarmToneLoop();
    await showDialog<void>(
      context: context,
      useRootNavigator: true,
      barrierDismissible: false,
      builder: (dialogContext) => Consumer<AlarmProvider>(
        builder: (context, provider, _) {
          final alarm = _resolveDialogAlarm(provider, initialAlarm);
          final isFall = alarm.isFall;
          final recommendedActions =
              isFall ? alarm.recommendedActions : const <String>[];
          final contraindications =
              isFall ? alarm.contraindications : const <String>[];
          final pendingReview = isFall && alarm.incidentId != null
              ? provider.pendingFallReviews[alarm.incidentId!]
              : null;
          final headline = isFall ? alarm.fallTitle : 'SOS 紧急求助告警';
          final description = pendingReview != null
              ? pendingReview.lead
              : _resolveAlarmBody(alarm);

          return AlertDialog(
            backgroundColor: const Color(0xFF1A0A0A),
            shape: RoundedRectangleBorder(
              side: const BorderSide(color: Colors.redAccent, width: 2),
              borderRadius: BorderRadius.circular(16),
            ),
            title: Row(
              children: [
                const Icon(Icons.warning, color: Colors.redAccent, size: 28),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    headline,
                    style: const TextStyle(
                      color: Colors.redAccent,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            content: SingleChildScrollView(
              child: Column(
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
                  if (isFall)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7F1D1D),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: const Color(0xFFFCA5A5)),
                      ),
                      child: Text(
                        alarm.fallSeverityLabel,
                        style: const TextStyle(
                          color: Color(0xFFFFE4E6),
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  if (!isFall && alarm.deviceName != null) ...[
                    Text(
                      '设备: ${alarm.deviceName}',
                      style: const TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 6),
                  ],
                  if (alarm.deviceMac.isNotEmpty) ...[
                    Text(
                      '设备 MAC: ${alarm.deviceMac}',
                      style: const TextStyle(
                        color: Color(0xFFF8FAFC),
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  Text(
                    '时间: ${alarm.createdAtDisplay}',
                    style: const TextStyle(color: Color(0xFFCBD5E1)),
                  ),
                  if (!isFall) ...[
                    const SizedBox(height: 8),
                    Text(
                      '触发方式: ${alarm.sosTriggerLabel}',
                      style: const TextStyle(color: Color(0xFFCBD5E1)),
                    ),
                  ],
                  if (pendingReview != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF3F1D1D),
                        borderRadius: BorderRadius.circular(12),
                        border:
                            Border.all(color: const Color(0xFFFCA5A5), width: 1),
                      ),
                      child: Text(
                        pendingReview.expectedSeconds != null
                            ? '系统复核中，预计 ${pendingReview.expectedSeconds} 秒内返回结果。'
                            : '系统正在复核当前跌倒事件，请先按风险处理并人工确认现场。',
                        style: const TextStyle(
                          color: Color(0xFFFEE2E2),
                          height: 1.35,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  Text(
                    description,
                    style: const TextStyle(
                      color: Color(0xFFE2E8F0),
                      height: 1.4,
                    ),
                  ),
                  if (isFall && recommendedActions.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    const Text(
                      '应对措施',
                      style: TextStyle(
                        color: Color(0xFFFFF1F2),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    for (final item in recommendedActions)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(
                          '• $item',
                          style: const TextStyle(
                            color: Color(0xFFE2E8F0),
                            height: 1.35,
                          ),
                        ),
                      ),
                  ],
                  if (isFall && contraindications.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    const Text(
                      '注意事项',
                      style: TextStyle(
                        color: Color(0xFFFFF1F2),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    for (final item in contraindications)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(
                          '• $item',
                          style: const TextStyle(
                            color: Color(0xFFFECACA),
                            height: 1.35,
                          ),
                        ),
                      ),
                  ],
                  if (isFall && alarm.familyMessage != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      alarm.familyMessage!,
                      style: const TextStyle(
                        color: Color(0xFFE2E8F0),
                        height: 1.4,
                      ),
                    ),
                  ],
                  if (isFall && alarm.shouldCallEmergency) ...[
                    const SizedBox(height: 12),
                    const Text(
                      '建议立即准备急救或医疗支援',
                      style: TextStyle(
                        color: Color(0xFFFCA5A5),
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              if (isFall)
                TextButton(
                  onPressed: () {
                    Navigator.pop(dialogContext);
                    _stopAlarmToneLoop();
                    _hideFloatingWarning();
                    _openCameraScreen();
                  },
                  child: const Text(
                    '查看监控',
                    style: TextStyle(
                      color: Color(0xFFFECACA),
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                ),
              TextButton(
                onPressed: () {
                  _stopAlarmToneLoop();
                  _hideFloatingWarning();
                  _alarmProvider?.acknowledge(alarm.id);
                  Navigator.pop(dialogContext);
                },
                child: const Text(
                  '我已知晓',
                  style: TextStyle(
                    color: Colors.redAccent,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
            ],
          );
        },
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

  AlarmRecord _resolveDialogAlarm(
    AlarmProvider provider,
    AlarmRecord initialAlarm,
  ) {
    final incidentId = initialAlarm.incidentId;
    if (incidentId == null || incidentId.isEmpty) {
      return initialAlarm;
    }
    for (final alarm in provider.alarms) {
      if (alarm.isFall && alarm.incidentId == incidentId) {
        return alarm;
      }
    }
    return initialAlarm;
  }

  void _openCameraScreen() {
    if (!mounted) return;
    Navigator.of(context, rootNavigator: true).push(
      MaterialPageRoute<void>(
        builder: (BuildContext context) => ChangeNotifierProvider(
          create: (BuildContext context) => CameraProvider(
            context.read<CameraRepository>(),
          )..start(),
          child: const FamilyCameraScreen(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}
