import 'package:flutter/material.dart';
import '../../session/models/user_model.dart';
import '../../session/services/session_manager.dart';
import '../repositories/auth_repository.dart';

enum AuthStatus { initial, authenticating, authenticated, unauthenticated, error }

class AuthProvider extends ChangeNotifier {
  final AuthRepository _repository;
  final SessionManager _sessionManager;

  AuthStatus _status = AuthStatus.initial;
  SessionUser? _user;
  String? _errorMessage;

  AuthProvider(this._repository, this._sessionManager);

  AuthStatus get status => _status;
  SessionUser? get user => _user;
  String? get errorMessage => _errorMessage;

  Future<void> checkSession() async {
    if (!_sessionManager.isAuthenticated) {
      _status = AuthStatus.unauthenticated;
      notifyListeners();
      return;
    }

    try {
      _user = await _repository.getMe();
      _status = AuthStatus.authenticated;
    } catch (e) {
      _status = AuthStatus.unauthenticated;
      await _sessionManager.clearSession();
    }
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    _status = AuthStatus.authenticating;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _repository.login(username, password);
      await _sessionManager.saveSession(response.token, response.user);
      _user = response.user;
      _status = AuthStatus.authenticated;
    } catch (e) {
      _status = AuthStatus.error;
      _errorMessage = '登录失败，请检查账号密码';
    }
    notifyListeners();
  }

  Future<void> logout() async {
    await _sessionManager.clearSession();
    _user = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  void handleUnauthorized() {
    _user = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }
}
