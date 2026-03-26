import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/alarm_model.dart';
import '../repositories/alarm_repository.dart';

enum AlarmLoadStatus { initial, loading, loaded, error }

class AlarmProvider extends ChangeNotifier {
  final AlarmRepository _repository;

  AlarmLoadStatus _status = AlarmLoadStatus.initial;
  List<AlarmRecord> _alarms = [];
  List<AlarmQueueItem> _queue = [];
  List<MobilePushRecord> _pushes = [];
  String? _errorMessage;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;

  AlarmProvider(this._repository);

  AlarmLoadStatus get status => _status;
  List<AlarmRecord> get alarms => _alarms;
  List<AlarmQueueItem> get queue => _queue;
  List<MobilePushRecord> get pushes => _pushes;
  String? get errorMessage => _errorMessage;

  Future<void> init() async {
    _status = AlarmLoadStatus.loading;
    notifyListeners();

    try {
      final results = await Future.wait([
        _repository.getAlarms(),
        _repository.getAlarmQueue(),
        _repository.getMobilePushes(),
      ]);

      _alarms = results[0] as List<AlarmRecord>;
      _queue = results[1] as List<AlarmQueueItem>;
      _pushes = results[2] as List<MobilePushRecord>;
      
      _status = AlarmLoadStatus.loaded;
      notifyListeners();

      _connectWebSocket();
    } catch (e) {
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
        (message) {
          _handleWsMessage(message);
        },
        onError: (_) => _handleWsDisconnect(),
        onDone: () => _handleWsDisconnect(),
      );
      _reconnectAttempts = 0;
    } catch (_) {
      _handleWsDisconnect();
    }
  }

  void _handleWsMessage(dynamic message) {
    try {
      final data = jsonDecode(message as String);
      if (data is! Map<String, dynamic>) return;

      // 后端可能发两种格式：
      // 1. 单条 AlarmRecord（broadcast_alarm）
      // 2. {type: "alarm_queue", queue: [...]}（broadcast_alarm_queue）
      final msgType = data['type'] as String?;

      if (msgType == 'alarm_queue') {
        // 全量刷新队列
        final rawQueue = data['queue'] as List<dynamic>?;
        if (rawQueue != null) {
          _queue = rawQueue
              .map((e) => AlarmQueueItem.fromJson(e as Map<String, dynamic>))
              .toList();
        }
        // 同步更新 alarms 列表（从 queue 中提取）
        for (final item in _queue) {
          final newAlarm = item.alarm;
          final index = _alarms.indexWhere((a) => a.id == newAlarm.id);
          if (index != -1) {
            _alarms[index] = newAlarm;
          } else {
            _alarms.insert(0, newAlarm);
          }
        }
        notifyListeners();
        return;
      }

      // 单条报警推送
      if (data.containsKey('id') && data.containsKey('alarm_type')) {
        final newAlarm = AlarmRecord.fromJson(data);
        final index = _alarms.indexWhere((a) => a.id == newAlarm.id);
        if (index != -1) {
          _alarms[index] = newAlarm;
        } else {
          _alarms.insert(0, newAlarm);
        }
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> acknowledge(String alarmId) async {
    try {
      await _repository.acknowledgeAlarm(alarmId);
      final index = _alarms.indexWhere((a) => a.id == alarmId);
      if (index != -1) {
        _alarms[index].acknowledged = true;
        notifyListeners();
      }
    } catch (_) {}
  }

  void reloadFromEndpointChange() {
    if (_status == AlarmLoadStatus.initial) {
      return;
    }
    init();
  }

  void _handleWsDisconnect() {
    _reconnectTimer?.cancel();
    final delay = Duration(seconds: (1 << _reconnectAttempts).clamp(1, 30));
    _reconnectTimer = Timer(delay, () {
      _reconnectAttempts++;
      _connectWebSocket();
    });
  }

  void _closeWebSocket() {
    _subscription?.cancel();
    _channel?.sink.close();
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _closeWebSocket();
    super.dispose();
  }
}
