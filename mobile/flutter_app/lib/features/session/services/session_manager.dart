import 'dart:convert';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user_model.dart';

class SessionManager {
  static const _keyToken = 'auth_token';
  static const _keyUser = 'session_user';
  static const _keyInstallationId = 'app_installation_id';

  final SharedPreferences _prefs;

  SessionManager(this._prefs);

  String? get token => _prefs.getString(_keyToken);
  
  SessionUser? get user {
    final userStr = _prefs.getString(_keyUser);
    if (userStr == null) return null;
    try {
      return SessionUser.fromJson(jsonDecode(userStr));
    } catch (_) {
      return null;
    }
  }

  Future<void> saveSession(String token, SessionUser user) async {
    await _prefs.setString(_keyToken, token);
    await _prefs.setString(_keyUser, jsonEncode(user.toJson()));
  }

  Future<void> clearSession() async {
    await _prefs.remove(_keyToken);
    await _prefs.remove(_keyUser);
  }

  bool get isAuthenticated => token != null && user != null;

  String getOrCreateInstallationId() {
    final existing = _prefs.getString(_keyInstallationId);
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    final installationId = bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
    _prefs.setString(_keyInstallationId, installationId);
    return installationId;
  }
}
