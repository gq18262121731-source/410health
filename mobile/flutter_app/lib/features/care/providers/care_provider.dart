import 'dart:async';

import 'package:flutter/material.dart';

import '../models/care_profile_model.dart';
import '../repositories/care_repository.dart';

enum CareLoadStatus { initial, loading, loaded, error }

class CareProvider extends ChangeNotifier {
  final CareRepository _repository;

  CareLoadStatus _status = CareLoadStatus.initial;
  CareAccessProfile? _profile;
  String? _errorMessage;
  Timer? _refreshTimer;
  bool _isFetching = false;

  CareProvider(this._repository);

  CareLoadStatus get status => _status;
  CareAccessProfile? get profile => _profile;
  String? get errorMessage => _errorMessage;

  Future<void> fetchProfile({bool silent = false}) async {
    if (_isFetching) return;
    _isFetching = true;

    final shouldShowLoading = !silent || _profile == null;
    if (shouldShowLoading) {
      _status = CareLoadStatus.loading;
      notifyListeners();
    }

    try {
      _profile = await _repository.getAccessProfile();
      _errorMessage = null;
      _status = CareLoadStatus.loaded;
    } catch (_) {
      _errorMessage = '获取监护数据失败';
      if (_profile == null || !silent) {
        _status = CareLoadStatus.error;
      }
    } finally {
      _isFetching = false;
    }

    notifyListeners();
  }

  void startAutoRefresh({Duration interval = const Duration(seconds: 3)}) {
    stopAutoRefresh();
    Future.microtask(() => fetchProfile(silent: _profile != null));
    _refreshTimer = Timer.periodic(interval, (_) {
      fetchProfile(silent: true);
    });
  }

  void stopAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  @override
  void dispose() {
    stopAutoRefresh();
    super.dispose();
  }
}
