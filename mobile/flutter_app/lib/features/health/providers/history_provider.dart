import 'package:flutter/material.dart';

import '../models/history_model.dart';
import '../repositories/health_repository.dart';

enum HistoryLoadStatus { initial, loading, loaded, error }

class HistoryProvider extends ChangeNotifier {
  final HealthRepository _repository;
  final String _deviceMac;

  HistoryLoadStatus _status = HistoryLoadStatus.initial;
  List<TrendPoint> _trends = [];
  DeviceHistoryResponse? _history;
  String? _errorMessage;
  String _currentWindow = 'day';
  bool _disposed = false;

  HistoryProvider(this._repository, this._deviceMac);

  HistoryLoadStatus get status => _status;
  List<TrendPoint> get trends => _trends;
  DeviceHistoryResponse? get history => _history;
  String? get errorMessage => _errorMessage;
  String get currentWindow => _currentWindow;

  void _notifyIfAlive() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  Future<void> fetchHistory({String? window}) async {
    if (_disposed) return;
    if (window != null) _currentWindow = window;

    _status = HistoryLoadStatus.loading;
    _notifyIfAlive();

    try {
      final results = await Future.wait<Object>([
        _repository.getTrend(_deviceMac),
        _repository.getHistory(_deviceMac, window: _currentWindow),
      ]);
      if (_disposed) return;

      _trends = results[0] as List<TrendPoint>;
      _history = results[1] as DeviceHistoryResponse;
      _errorMessage = null;
      _status = HistoryLoadStatus.loaded;
    } catch (_) {
      if (_disposed) return;
      _status = HistoryLoadStatus.error;
      _errorMessage = '获取历史数据失败';
    }

    _notifyIfAlive();
  }

  void setWindow(String window) {
    if (_currentWindow == window) return;
    fetchHistory(window: window);
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
