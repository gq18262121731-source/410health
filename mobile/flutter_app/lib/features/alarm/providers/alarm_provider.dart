import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/alarm_model.dart';
import '../repositories/alarm_repository.dart';

enum AlarmLoadStatus { initial, loading, loaded, error }

class FallReviewPendingMessage {
  final String incidentId;
  final String? trackId;
  final String title;
  final String lead;
  final int? expectedSeconds;
  final String? catalogCode;
  final Map<String, dynamic>? event;
  final Map<String, dynamic>? presentation;
  final Map<String, dynamic>? familyGuidance;

  const FallReviewPendingMessage({
    required this.incidentId,
    this.trackId,
    required this.title,
    required this.lead,
    this.expectedSeconds,
    this.catalogCode,
    this.event,
    this.presentation,
    this.familyGuidance,
  });

  factory FallReviewPendingMessage.fromJson(Map<String, dynamic> json) {
    return FallReviewPendingMessage(
      incidentId: json['incident_id']?.toString() ?? '',
      trackId: json['track_id']?.toString(),
      title: json['title']?.toString() ?? '',
      lead: json['lead']?.toString() ?? '',
      expectedSeconds: json['expected_seconds'] is num
          ? (json['expected_seconds'] as num).toInt()
          : int.tryParse(json['expected_seconds']?.toString() ?? ''),
      catalogCode: json['catalog_code']?.toString(),
      event: _asMap(json['event']),
      presentation: _asMap(json['presentation']),
      familyGuidance: _asMap(json['family_guidance']),
    );
  }
}

class FallReviewFinalizedMessage {
  final String incidentId;
  final String? trackId;
  final String? catalogCode;
  final Map<String, dynamic>? presentation;
  final Map<String, dynamic>? familyGuidance;
  final Map<String, dynamic>? event;
  final Map<String, dynamic>? review;

  const FallReviewFinalizedMessage({
    required this.incidentId,
    this.trackId,
    this.catalogCode,
    this.presentation,
    this.familyGuidance,
    this.event,
    this.review,
  });

  factory FallReviewFinalizedMessage.fromJson(Map<String, dynamic> json) {
    return FallReviewFinalizedMessage(
      incidentId: json['incident_id']?.toString() ?? '',
      trackId: json['track_id']?.toString(),
      catalogCode: json['catalog_code']?.toString(),
      presentation: _asMap(json['presentation']),
      familyGuidance: _asMap(json['family_guidance']),
      event: _asMap(json['event']),
      review: _asMap(json['review']),
    );
  }
}

Map<String, dynamic>? _asMap(dynamic raw) {
  if (raw is Map) {
    return Map<String, dynamic>.from(raw);
  }
  return null;
}

class AlarmProvider extends ChangeNotifier {
  static const Duration _fallbackRefreshInterval = Duration(seconds: 12);

  AlarmRepository _repository;

  AlarmLoadStatus _status = AlarmLoadStatus.initial;
  List<AlarmRecord> _alarms = [];
  List<AlarmQueueItem> _queue = [];
  List<MobilePushRecord> _pushes = [];
  Map<String, FallReviewPendingMessage> _pendingFallReviews =
      <String, FallReviewPendingMessage>{};
  String? _errorMessage;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  Timer? _fallbackRefreshTimer;
  int _reconnectAttempts = 0;
  bool _started = false;
  bool _refreshInFlight = false;
  bool _disposed = false;

  AlarmProvider(this._repository);

  void updateRepository(AlarmRepository repository) {
    if (identical(_repository, repository)) {
      return;
    }
    _repository = repository;
    if (_started) {
      unawaited(reloadFromEndpointChange());
    }
  }

  void _notifyIfAlive() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  AlarmLoadStatus get status => _status;
  List<AlarmRecord> get alarms => _alarms;
  List<AlarmQueueItem> get queue => _queue;
  List<MobilePushRecord> get pushes => _pushes;
  Map<String, FallReviewPendingMessage> get pendingFallReviews =>
      Map<String, FallReviewPendingMessage>.unmodifiable(_pendingFallReviews);
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
    _pendingFallReviews = <String, FallReviewPendingMessage>{};
    _notifyIfAlive();

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
      _notifyIfAlive();

      _connectWebSocket();
    } catch (_) {
      _status = AlarmLoadStatus.error;
      _errorMessage = '获取告警信息失败';
      _notifyIfAlive();
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
        _notifyIfAlive();
        return;
      }

      if (msgType == 'fall_alarm_pending_review') {
        final review = FallReviewPendingMessage.fromJson(data);
        if (review.incidentId.isNotEmpty) {
          _pendingFallReviews[review.incidentId] = review;
          _notifyIfAlive();
        }
        return;
      }

      if (msgType == 'fall_alarm_finalized') {
        final review = FallReviewFinalizedMessage.fromJson(data);
        if (review.incidentId.isNotEmpty) {
          _pendingFallReviews.remove(review.incidentId);
          _mergeFallReviewFinalized(review);
          _notifyIfAlive();
        }
        return;
      }

      if (data.containsKey('id') && data.containsKey('alarm_type')) {
        final newAlarm = AlarmRecord.fromJson(data);
        if (newAlarm.isFall && newAlarm.incidentId != null) {
          _replaceExistingIncidentAlarm(newAlarm);
          _notifyIfAlive();
          return;
        }
        final index = _alarms.indexWhere((a) => a.id == newAlarm.id);
        if (index != -1) {
          _alarms[index] = newAlarm;
        } else {
          _alarms.insert(0, newAlarm);
        }
        _sortAlarms();
        _notifyIfAlive();
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
      if (queued.isFall && queued.incidentId != null) {
        _replaceExistingIncidentAlarm(queued);
        continue;
      }
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

  void _replaceExistingIncidentAlarm(AlarmRecord incoming) {
    final incidentId = incoming.incidentId;
    if (incidentId == null || incidentId.isEmpty) {
      final index = _alarms.indexWhere((alarm) => alarm.id == incoming.id);
      if (index != -1) {
        _alarms[index] = incoming;
      } else {
        _alarms.insert(0, incoming);
      }
      _sortAlarms();
      return;
    }

    final existingIndex = _alarms.indexWhere(
      (alarm) => alarm.isFall && alarm.incidentId == incidentId,
    );
    if (existingIndex != -1) {
      _alarms[existingIndex] = incoming;
    } else {
      _alarms.insert(0, incoming);
    }
    _sortAlarms();
  }

  void _mergeFallReviewFinalized(FallReviewFinalizedMessage message) {
    if (message.incidentId.isEmpty) return;
    for (var index = 0; index < _alarms.length; index += 1) {
      final alarm = _alarms[index];
      if (!alarm.isFall || alarm.incidentId != message.incidentId) {
        continue;
      }
      final nextMetadata = Map<String, dynamic>.from(alarm.metadata);
      if (message.presentation != null) {
        nextMetadata['presentation'] = message.presentation;
      }
      if (message.familyGuidance != null) {
        nextMetadata['family_guidance'] = message.familyGuidance;
      }
      if (message.event != null) {
        final existingEvent =
            _asMap(nextMetadata['event']) ?? <String, dynamic>{};
        final mergedEvent = Map<String, dynamic>.from(existingEvent)
          ..addAll(message.event!);
        if (message.review != null) {
          mergedEvent['multimodal_review'] = message.review;
        }
        nextMetadata['event'] = mergedEvent;
      }
      _alarms[index] = AlarmRecord(
        id: alarm.id,
        deviceMac: alarm.deviceMac,
        alarmType: alarm.alarmType,
        alarmLevel: alarm.alarmLevel,
        alarmPriority: alarm.alarmPriority,
        message: alarm.message,
        createdAt: alarm.createdAt,
        acknowledged: alarm.acknowledged,
        anomalyProbability: alarm.anomalyProbability,
        metadata: nextMetadata,
      );
      break;
    }
    _sortAlarms();
  }

  Future<void> acknowledge(String alarmId) async {
    final index = _alarms.indexWhere((a) => a.id == alarmId);
    bool previousAcknowledged = false;
    if (index != -1) {
      previousAcknowledged = _alarms[index].acknowledged;
      _alarms[index].acknowledged = true;
      _notifyIfAlive();
    }
    try {
      await _repository.acknowledgeAlarm(alarmId);
    } catch (_) {
      if (index != -1) {
        _alarms[index].acknowledged = previousAcknowledged;
        _notifyIfAlive();
      }
    }
  }

  void reset() {
    _started = false;
    _status = AlarmLoadStatus.initial;
    _alarms = [];
    _queue = [];
    _pushes = [];
    _pendingFallReviews = <String, FallReviewPendingMessage>{};
    _errorMessage = null;
    _reconnectTimer?.cancel();
    _stopFallbackRefresh();
    _closeWebSocket();
    _notifyIfAlive();
  }

  Future<void> reloadFromEndpointChange() async {
    if (!_started) {
      return;
    }
    await init();
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
      _notifyIfAlive();
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
    _disposed = true;
    _reconnectTimer?.cancel();
    _stopFallbackRefresh();
    _closeWebSocket();
    super.dispose();
  }
}
