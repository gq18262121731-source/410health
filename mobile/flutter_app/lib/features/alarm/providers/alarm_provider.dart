import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/alarm_model.dart';
import '../repositories/alarm_repository.dart';

enum AlarmLoadStatus { initial, loading, loaded, error }

class AlarmProvider extends ChangeNotifier {
  static const Duration _fallbackRefreshInterval = Duration(seconds: 12);

  final AlarmRepository _repository;

  AlarmLoadStatus _status = AlarmLoadStatus.initial;
  List<AlarmRecord> _alarms = [];
  List<AlarmQueueItem> _queue = [];
  List<MobilePushRecord> _pushes = [];
  String? _errorMessage;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  Timer? _fallbackRefreshTimer;
  int _reconnectAttempts = 0;
  bool _started = false;
  bool _refreshInFlight = false;

  AlarmProvider(this._repository);

  AlarmLoadStatus get status => _status;
  List<AlarmRecord> get alarms => _alarms;
  List<AlarmQueueItem> get queue => _queue;
  List<MobilePushRecord> get pushes => _pushes;
  String? get errorMessage => _errorMessage;

  Future<void> ensureStarted() async {
    if (_started && _channel != null) {
      return;
    }
    await init();
  }

  Future<void> init() async {
    _started = true;
    _status = AlarmLoadStatus.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      List<AlarmRecord>? alarms;
      List<AlarmQueueItem>? queue;
      List<MobilePushRecord> pushes = <MobilePushRecord>[];

      try {
        alarms = await _repository.getAlarms();
      } catch (_) {
        alarms = null;
      }

      try {
        queue = await _repository.getAlarmQueue();
      } catch (_) {
        queue = null;
      }

      try {
        pushes = await _repository.getMobilePushes();
      } catch (_) {
        pushes = <MobilePushRecord>[];
      }

      if (alarms == null && queue == null) {
        throw StateError('failed to load core alarm state');
      }

      _alarms = alarms ?? <AlarmRecord>[];
      _queue = queue ?? <AlarmQueueItem>[];
      _pushes = pushes;
      // Fold the current active queue into the visible alarm list before the
      // websocket is connected so SOS popups are not delayed on app startup.
      _reconcileActiveQueue(null);

      _status = AlarmLoadStatus.loaded;
      notifyListeners();

      _connectWebSocket();
    } catch (_) {
      _status = AlarmLoadStatus.error;
      _errorMessage = '获取告警信息失败';
      notifyListeners();
    }
  }

  void _connectWebSocket() {
    _closeWebSocket();
    try {
      _channel = _repository.connectToAlarms();
      _subscription = _channel!.stream.listen(
        _handleWsMessage,
        onError: (_) => _handleWsDisconnect(),
        onDone: () => _handleWsDisconnect(),
      );
      _reconnectAttempts = 0;
      _stopFallbackRefresh();
    } catch (_) {
      _handleWsDisconnect();
    }
  }

  void _handleWsMessage(dynamic message) {
    try {
      final data = jsonDecode(message as String);
      if (data is! Map<String, dynamic>) {
        return;
      }

      final msgType = data['type'] as String?;
      if (msgType == 'alarm_queue') {
        _reconcileActiveQueue(data['queue'] as List<dynamic>?);
        notifyListeners();
        return;
      }

      if (data.containsKey('id') && data.containsKey('alarm_type')) {
        final newAlarm = AlarmRecord.fromJson(data);
        final index = _alarms.indexWhere((a) => a.id == newAlarm.id);
        if (index != -1) {
          _alarms[index] = newAlarm;
        } else {
          _alarms.insert(0, newAlarm);
        }
        _sortAlarms();
        notifyListeners();
      }
    } catch (_) {}
  }

  void _reconcileActiveQueue(List<dynamic>? rawQueue) {
    if (rawQueue != null) {
      _queue = rawQueue
          .map((e) => AlarmQueueItem.fromJson(e as Map<String, dynamic>))
          .toList();
    }

    final queueAlarmById = <String, AlarmRecord>{
      for (final item in _queue) item.alarm.id: item.alarm,
    };

    _alarms = _alarms.map((alarm) {
      final queued = queueAlarmById[alarm.id];
      if (queued != null) {
        return queued;
      }
      if (!alarm.acknowledged) {
        return AlarmRecord(
          id: alarm.id,
          deviceMac: alarm.deviceMac,
          alarmType: alarm.alarmType,
          alarmLevel: alarm.alarmLevel,
          alarmPriority: alarm.alarmPriority,
          message: alarm.message,
          createdAt: alarm.createdAt,
          acknowledged: true,
          anomalyProbability: alarm.anomalyProbability,
          metadata: alarm.metadata,
        );
      }
      return alarm;
    }).toList();

    for (final queued in queueAlarmById.values) {
      final index = _alarms.indexWhere((alarm) => alarm.id == queued.id);
      if (index != -1) {
        _alarms[index] = queued;
      } else {
        _alarms.insert(0, queued);
      }
    }

    _sortAlarms();
  }

  void _sortAlarms() {
    _alarms.sort((a, b) {
      final aTime = a.createdAtDateTime ?? DateTime.fromMillisecondsSinceEpoch(0);
      final bTime = b.createdAtDateTime ?? DateTime.fromMillisecondsSinceEpoch(0);
      return bTime.compareTo(aTime);
    });
  }

  Future<void> acknowledge(String alarmId) async {
    final index = _alarms.indexWhere((a) => a.id == alarmId);
    bool previousAcknowledged = false;
    if (index != -1) {
      previousAcknowledged = _alarms[index].acknowledged;
      _alarms[index].acknowledged = true;
      notifyListeners();
    }
    try {
      await _repository.acknowledgeAlarm(alarmId);
    } catch (_) {
      if (index != -1) {
        _alarms[index].acknowledged = previousAcknowledged;
        notifyListeners();
      }
    }
  }

  void reset() {
    _started = false;
    _status = AlarmLoadStatus.initial;
    _alarms = [];
    _queue = [];
    _pushes = [];
    _errorMessage = null;
    _reconnectTimer?.cancel();
    _stopFallbackRefresh();
    _closeWebSocket();
    notifyListeners();
  }

  void reloadFromEndpointChange() {
    if (!_started) {
      return;
    }
    init();
  }

  Future<void> resyncAfterForegroundResume() async {
    if (!_started) {
      await ensureStarted();
      return;
    }
    await init();
  }

  void _startFallbackRefresh() {
    if (_fallbackRefreshTimer != null) {
      return;
    }
    _fallbackRefreshTimer = Timer.periodic(_fallbackRefreshInterval, (_) {
      unawaited(_refreshFromFallbackPath());
    });
  }

  void _stopFallbackRefresh() {
    _fallbackRefreshTimer?.cancel();
    _fallbackRefreshTimer = null;
  }

  Future<void> _refreshFromFallbackPath() async {
    if (!_started || _refreshInFlight) {
      return;
    }
    _refreshInFlight = true;
    try {
      List<AlarmRecord>? alarms;
      List<AlarmQueueItem>? queue;

      try {
        alarms = await _repository.getAlarms();
      } catch (_) {
        alarms = null;
      }

      try {
        queue = await _repository.getAlarmQueue();
      } catch (_) {
        queue = null;
      }

      if (alarms == null && queue == null) {
        return;
      }

      if (alarms != null) {
        _alarms = alarms;
      }
      if (queue != null) {
        _queue = queue;
      }
      _reconcileActiveQueue(null);
      if (_status != AlarmLoadStatus.loaded) {
        _status = AlarmLoadStatus.loaded;
        _errorMessage = null;
      }
      notifyListeners();
    } finally {
      _refreshInFlight = false;
    }
  }

  void _handleWsDisconnect() {
    _channel = null;
    _subscription = null;
    if (!_started) {
      return;
    }
    _startFallbackRefresh();
    _reconnectTimer?.cancel();
    final delay = Duration(seconds: (1 << _reconnectAttempts).clamp(1, 30));
    _reconnectTimer = Timer(delay, () {
      if (!_started) {
        return;
      }
      _reconnectAttempts++;
      _connectWebSocket();
    });
  }

  void _closeWebSocket() {
    _subscription?.cancel();
    _channel?.sink.close();
    _subscription = null;
    _channel = null;
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _stopFallbackRefresh();
    _closeWebSocket();
    super.dispose();
  }
}
