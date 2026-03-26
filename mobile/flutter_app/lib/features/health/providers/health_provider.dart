import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/health_model.dart';
import '../repositories/health_repository.dart';

enum HealthStatus { initial, loading, loaded, error }

class HealthProvider extends ChangeNotifier {
  final HealthRepository _repository;
  final String _deviceMac;

  HealthStatus _status = HealthStatus.initial;
  HealthData? _data;
  final List<HealthData> _historyBuffer = [];
  String? _errorMessage;
  bool _isWsConnected = false;
  
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;

  HealthProvider(this._repository, this._deviceMac);

  HealthStatus get status => _status;
  HealthData? get data => _data;
  List<HealthData> get historyBuffer => _historyBuffer;
  String? get errorMessage => _errorMessage;
  bool get isWsConnected => _isWsConnected;

  Future<void> init() async {
    _status = HealthStatus.loading;
    notifyListeners();

    try {
      // 1. REST 快照初始化
      _data = await _repository.getRealtimeSnapshot(_deviceMac);
      if (_data != null) {
        _historyBuffer.clear();
        _historyBuffer.add(_data!);
      }
      _status = HealthStatus.loaded;
      notifyListeners();

      // 2. 建立 WebSocket 连接
      _connectWebSocket();
    } catch (e) {
      _status = HealthStatus.error;
      _errorMessage = '无法获取实时数据';
      notifyListeners();
    }
  }

  void _connectWebSocket() {
    _closeWebSocket();
    
    try {
      _channel = _repository.connectToRealtime(_deviceMac);
      _isWsConnected = true;
      _reconnectAttempts = 0;
      
      _subscription = _channel!.stream.listen(
        (message) {
          _handleWsMessage(message);
        },
        onError: (error) {
          _handleWsDisconnect();
        },
        onDone: () {
          _handleWsDisconnect();
        },
      );
    } catch (_) {
      _handleWsDisconnect();
    }
    notifyListeners();
  }

  void _handleWsMessage(dynamic message) {
    try {
      final Map<String, dynamic> json = jsonDecode(message as String);
      if (_data == null) {
        _data = HealthData.fromJson(json);
      } else {
        // 合并增量数据
        final newData = HealthData.fromJson(json);
        _data = _data!.copyWith(
          heartRate: newData.heartRate,
          temperature: newData.temperature,
          bloodOxygen: newData.bloodOxygen,
          bloodPressure: newData.bloodPressure,
          battery: newData.battery,
          sosFlag: newData.sosFlag,
          steps: newData.steps,
          healthScore: newData.healthScore,
        );
      }
      
      if (_data != null) {
        _historyBuffer.add(_data!);
        if (_historyBuffer.length > 60) {
          _historyBuffer.removeAt(0); // 仅保留最近 60 个数据点
        }
      }
      
      notifyListeners();
    } catch (e) {
      // 解析错误忽略
    }
  }

  void _handleWsDisconnect() {
    _isWsConnected = false;
    notifyListeners();
    
    // 指数退避重连
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
    _isWsConnected = false;
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _closeWebSocket();
    super.dispose();
  }
}
