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
      if (data is Map<String, dynamic>) {
        final newAlarm = AlarmRecord.fromJson(data);
        
        // 增量刷新：检查是否已存在
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
