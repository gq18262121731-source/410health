import 'package:flutter/material.dart';

import '../../../core/services/mobile_device_registration_service.dart';
import '../../session/models/user_model.dart';
import '../../session/services/session_manager.dart';
import '../models/register_models.dart';
import '../repositories/auth_repository.dart';

export '../models/register_models.dart';

enum AuthStatus { initial, authenticating, authenticated, unauthenticated, error }
enum RegisterStatus { idle, submitting, success, error }

class AuthProvider extends ChangeNotifier {
  AuthRepository _repository;
  SessionManager _sessionManager;
  MobileDeviceRegistrationService _mobileDeviceRegistrationService;

  AuthStatus _status = AuthStatus.initial;
  RegisterStatus _registerStatus = RegisterStatus.idle;
  SessionUser? _user;
  String? _errorMessage;
  String? _registerError;
  RegisterResponse? _lastRegistered;
  bool _disposed = false;

  AuthProvider(this._repository, this._sessionManager, this._mobileDeviceRegistrationService);

  AuthStatus get status => _status;
  RegisterStatus get registerStatus => _registerStatus;
  SessionUser? get user => _user;
  String? get errorMessage => _errorMessage;
  String? get registerError => _registerError;
  RegisterResponse? get lastRegistered => _lastRegistered;

  void updateDependencies(
    AuthRepository repository,
    SessionManager sessionManager,
    MobileDeviceRegistrationService mobileDeviceRegistrationService,
  ) {
    _repository = repository;
    _sessionManager = sessionManager;
    _mobileDeviceRegistrationService = mobileDeviceRegistrationService;
  }

  void _notifyIfAlive() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  Future<void> checkSession() async {
    if (!_sessionManager.isAuthenticated) {
      _status = AuthStatus.unauthenticated;
      _notifyIfAlive();
      return;
    }

    try {
      _user = await _repository.getMe();
      _status = AuthStatus.authenticated;
    } catch (e) {
      _status = AuthStatus.unauthenticated;
      await _sessionManager.clearSession();
    }
    _notifyIfAlive();
  }

  Future<void> login(String username, String password) async {
    _status = AuthStatus.authenticating;
    _errorMessage = null;
    _notifyIfAlive();

    try {
      final response = await _repository.login(username, password);
      await _sessionManager.saveSession(response.token, response.user);
      _user = response.user;
      _status = AuthStatus.authenticated;
    } catch (e) {
      _status = AuthStatus.error;
      _errorMessage = _humanizeLoginError(e.toString());
    }
    _notifyIfAlive();
  }

  Future<void> logout() async {
    await _mobileDeviceRegistrationService.revokeCurrentInstallation();
    await _sessionManager.clearSession();
    _user = null;
    _status = AuthStatus.unauthenticated;
    _notifyIfAlive();
  }

  void handleUnauthorized() {
    _user = null;
    _status = AuthStatus.unauthenticated;
    _notifyIfAlive();
  }

  void resetRegisterState() {
    _registerStatus = RegisterStatus.idle;
    _registerError = null;
    _lastRegistered = null;
    _notifyIfAlive();
  }

  Future<bool> registerElder(ElderRegisterRequest request) async {
    return _doRegister(() => _repository.registerElder(request));
  }

  Future<bool> registerFamily(FamilyRegisterRequest request) async {
    return _doRegister(() => _repository.registerFamily(request));
  }

  Future<bool> registerCommunity(CommunityRegisterRequest request) async {
    return _doRegister(() => _repository.registerCommunity(request));
  }

  Future<bool> _doRegister(Future<RegisterResponse> Function() call) async {
    _registerStatus = RegisterStatus.submitting;
    _registerError = null;
    _notifyIfAlive();
    try {
      _lastRegistered = await call();
      _registerStatus = RegisterStatus.success;
      _notifyIfAlive();
      return true;
    } catch (e) {
      _registerStatus = RegisterStatus.error;
      _registerError = _humanizeRegisterError(e.toString());
      _notifyIfAlive();
      return false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  static String _humanizeLoginError(String raw) {
    if (raw.contains('SocketException') ||
        raw.contains('Connection refused') ||
        raw.contains('Connection error') ||
        raw.contains('No route to host')) {
      return '无法连接到后端服务，请在服务器设置中填写局域网 IP 和 8000 端口。';
    }
    if (raw.contains('401') || raw.contains('403')) {
      return '登录失败，请检查账号和密码。';
    }
    return '登录失败，请稍后重试。';
  }

  static String _humanizeRegisterError(String raw) {
    if (raw.contains('PHONE_ALREADY_EXISTS')) return '该手机号已被注册，请更换手机号。';
    if (raw.contains('LOGIN_USERNAME_ALREADY_EXISTS')) return '该账号名已被占用，请更换账号名。';
    if (raw.contains('409')) return '该账号信息已存在，请检查手机号或账号名。';
    if (raw.contains('SocketException') || raw.contains('Connection')) {
      return '无法连接到服务器，请检查网络后重试。';
    }
    return '注册失败，请稍后重试。';
  }
}
