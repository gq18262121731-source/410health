import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../../features/alarm/models/alarm_model.dart';

class AppNotificationService {
  static const String _sosChannelId = 'sos_alerts';
  static const String _sosChannelName = 'SOS Emergency Alerts';
  static const String _sosChannelDescription = 'Emergency SOS alerts from family wearable devices';

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();

  bool _initialized = false;
  bool _requestedPermissionsThisLaunch = false;
  Set<String> _activeSosAlarmIds = <String>{};

  Future<NotificationRegistrationSnapshot> registrationSnapshot() async {
    await initialize();
    bool enabled = true;
    final androidPlugin = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    if (androidPlugin != null) {
      enabled = await androidPlugin.areNotificationsEnabled() ?? true;
    }
    return NotificationRegistrationSnapshot(
      platform: _platformName(),
      notificationsEnabled: enabled,
      remotePushReady: false,
    );
  }

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwinSettings = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _plugin.initialize(
      settings: const InitializationSettings(
        android: androidSettings,
        iOS: darwinSettings,
        macOS: darwinSettings,
      ),
    );

    const sosChannel = AndroidNotificationChannel(
      _sosChannelId,
      _sosChannelName,
      description: _sosChannelDescription,
      importance: Importance.max,
      playSound: true,
      enableVibration: true,
      enableLights: true,
      showBadge: true,
    );

    final androidPlugin = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    await androidPlugin?.createNotificationChannel(sosChannel);
    _initialized = true;
  }

  Future<void> requestPermissionsIfNeeded() async {
    if (_requestedPermissionsThisLaunch) {
      return;
    }
    _requestedPermissionsThisLaunch = true;
    await initialize();

    final androidPlugin = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    final androidEnabled = await androidPlugin?.areNotificationsEnabled();
    if (androidEnabled == false) {
      await androidPlugin?.requestNotificationsPermission();
    }

    final iosPlugin = _plugin.resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>();
    await iosPlugin?.requestPermissions(
      alert: true,
      badge: true,
      sound: true,
    );
    final macosPlugin = _plugin.resolvePlatformSpecificImplementation<MacOSFlutterLocalNotificationsPlugin>();
    await macosPlugin?.requestPermissions(
      alert: true,
      badge: true,
      sound: true,
    );
  }

  Future<void> syncActiveSosNotifications(
    Iterable<AlarmRecord> alarms, {
    required bool appInForeground,
  }) async {
    await initialize();

    final activeSosAlarms = alarms.where((alarm) => alarm.isSos && !alarm.acknowledged).toList();
    final nextIds = activeSosAlarms.map((alarm) => alarm.id).toSet();

    for (final staleId in _activeSosAlarmIds.difference(nextIds)) {
      await _plugin.cancel(id: _notificationIdFor(staleId));
    }

    _activeSosAlarmIds = nextIds;

    if (appInForeground) {
      for (final alarmId in nextIds) {
        await _plugin.cancel(id: _notificationIdFor(alarmId));
      }
      return;
    }

    for (final alarm in activeSosAlarms) {
      await _plugin.show(
        id: _notificationIdFor(alarm.id),
        title: _buildTitle(alarm),
        body: _buildBody(alarm),
        notificationDetails: NotificationDetails(
          android: AndroidNotificationDetails(
            _sosChannelId,
            _sosChannelName,
            channelDescription: _sosChannelDescription,
            importance: Importance.max,
            priority: Priority.max,
            category: AndroidNotificationCategory.alarm,
            visibility: NotificationVisibility.public,
            styleInformation: BigTextStyleInformation(_buildBody(alarm)),
            ticker: 'SOS',
            ongoing: true,
            autoCancel: false,
            onlyAlertOnce: false,
          ),
          iOS: DarwinNotificationDetails(
            presentAlert: true,
            presentBadge: true,
            presentSound: true,
            interruptionLevel: InterruptionLevel.timeSensitive,
            threadIdentifier: 'sos-alerts',
          ),
          macOS: DarwinNotificationDetails(
            presentAlert: true,
            presentBadge: true,
            presentSound: true,
            interruptionLevel: InterruptionLevel.timeSensitive,
            threadIdentifier: 'sos-alerts',
          ),
        ),
        payload: alarm.id,
      );
    }
  }

  Future<void> clearAllSosNotifications() async {
    for (final alarmId in _activeSosAlarmIds) {
      await _plugin.cancel(id: _notificationIdFor(alarmId));
    }
    _activeSosAlarmIds = <String>{};
  }

  static int _notificationIdFor(String alarmId) {
    return alarmId.hashCode & 0x7fffffff;
  }

  static String _platformName() {
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return 'android';
      case TargetPlatform.iOS:
        return 'ios';
      case TargetPlatform.macOS:
        return 'macos';
      case TargetPlatform.windows:
        return 'windows';
      case TargetPlatform.linux:
        return 'linux';
      case TargetPlatform.fuchsia:
        return 'unknown';
    }
  }

  static String _buildTitle(AlarmRecord alarm) {
    final elderName = alarm.elderName;
    if (elderName != null && elderName.isNotEmpty) {
      return 'SOS 紧急求助 · $elderName';
    }
    return 'SOS 紧急求助';
  }

  static String _buildBody(AlarmRecord alarm) {
    final segments = <String>[];
    if (alarm.apartment != null) {
      segments.add(alarm.apartment!);
    }
    if (alarm.deviceName != null) {
      segments.add('设备 ${alarm.deviceName}');
    }
    segments.add(alarm.sosTriggerLabel);
    final lead = segments.join(' · ');
    if (alarm.message.isEmpty) {
      return lead;
    }
    if (lead.isEmpty) {
      return alarm.message;
    }
    return '$lead\n${alarm.message}';
  }
}

class NotificationRegistrationSnapshot {
  final String platform;
  final bool notificationsEnabled;
  final bool remotePushReady;

  const NotificationRegistrationSnapshot({
    required this.platform,
    required this.notificationsEnabled,
    required this.remotePushReady,
  });
}
