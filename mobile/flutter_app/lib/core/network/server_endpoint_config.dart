import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ServerEndpointConfig extends ChangeNotifier {
  static const _keyHost = 'server_host';
  static const _keyPort = 'server_port';
  static const _keyScheme = 'server_scheme';

  final SharedPreferences _prefs;

  late String _host;
  late int _port;
  late String _scheme;
  int _revision = 0;

  ServerEndpointConfig(this._prefs) {
    _host = _prefs.getString(_keyHost) ?? _defaultHost();
    _port = _prefs.getInt(_keyPort) ?? 8000;
    _scheme = _normalizeScheme(_prefs.getString(_keyScheme) ?? 'http');
  }

  String get host => _host;
  int get port => _port;
  String get scheme => _scheme;
  int get revision => _revision;

  String get origin => '$_scheme://$_host:$_port';
  String get apiBaseUrl => '$origin/api/v1/';
  String get wsBaseUrl => '${_scheme == 'https' ? 'wss' : 'ws'}://$_host:$_port';

  bool get isEmulatorDefaultHost => _host == '10.0.2.2';
  bool get isLoopbackHost => _host == '127.0.0.1' || _host == 'localhost';
  bool get looksLikeFrontendPort => _port == 5173 || _port == 5182 || _port == 7860 || _port == 7861 || _port == 8090;

  static String _normalizeScheme(String value) {
    return value.toLowerCase() == 'https' ? 'https' : 'http';
  }

  static String _defaultHost() {
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return '10.0.2.2';
    }
    return '127.0.0.1';
  }

  static bool isLikelyIpv4(String value) {
    final parts = value.trim().split('.');
    if (parts.length != 4) return false;
    return parts.every((part) {
      final parsed = int.tryParse(part);
      return parsed != null && parsed >= 0 && parsed <= 255;
    });
  }

  static bool isReservedFrontendPort(int port) {
    return {5173, 5182, 7860, 7861, 8090}.contains(port);
  }

  static String? validateEndpoint({
    required String host,
    required int port,
    required bool isAndroidRealDeviceMode,
  }) {
    final normalizedHost = host.trim();
    if (normalizedHost.isEmpty) {
      return '请输入服务器地址。';
    }
    if (port < 1 || port > 65535) {
      return '请输入 1 到 65535 之间的端口。';
    }
    if (isReservedFrontendPort(port)) {
      return '当前移动端只能连接后端 8000 端口，不能填写 5173/5182/7860/8090 这类前端或工具端口。';
    }
    if (isAndroidRealDeviceMode && normalizedHost == '10.0.2.2') {
      return '10.0.2.2 仅适用于 Android 模拟器，不适用于真机。请填写运行后端服务那台电脑的局域网 IP。';
    }
    return null;
  }

  String? getCurrentEndpointWarning({bool isAndroidRealDeviceMode = true}) {
    return validateEndpoint(
      host: _host,
      port: _port,
      isAndroidRealDeviceMode: isAndroidRealDeviceMode,
    );
  }

  String suggestRealDeviceOrigin({String? preferredHost}) {
    final candidate = (preferredHost?.trim().isNotEmpty ?? false) ? preferredHost!.trim() : '192.168.8.252';
    return 'http://$candidate:8000';
  }

  Future<void> save({
    required String host,
    required int port,
    required String scheme,
  }) async {
    final normalizedHost = host.trim();
    final normalizedScheme = _normalizeScheme(scheme);

    await _prefs.setString(_keyHost, normalizedHost);
    await _prefs.setInt(_keyPort, port);
    await _prefs.setString(_keyScheme, normalizedScheme);

    _host = normalizedHost;
    _port = port;
    _scheme = normalizedScheme;
    _revision += 1;
    notifyListeners();
  }

  Future<String?> testConnection({
    required String host,
    required int port,
    required String scheme,
    bool isAndroidRealDeviceMode = true,
  }) async {
    final normalizedHost = host.trim();
    final normalizedScheme = _normalizeScheme(scheme);

    final validationMessage = validateEndpoint(
      host: normalizedHost,
      port: port,
      isAndroidRealDeviceMode: isAndroidRealDeviceMode,
    );
    if (validationMessage != null) {
      return validationMessage;
    }

    try {
      final dio = Dio(
        BaseOptions(
          baseUrl: '$normalizedScheme://$normalizedHost:$port',
          connectTimeout: const Duration(seconds: 3),
          receiveTimeout: const Duration(seconds: 3),
        ),
      );
      final response = await dio.get('/healthz');
      final data = response.data;
      if (response.statusCode == 200 && data is Map && data['status'] == 'ok') {
        return null;
      }
      return '服务器有响应，但这不是可用的后端健康检查接口。请确认填写的是后端服务地址，例如 http://<局域网IP>:8000。';
    } on DioException catch (error) {
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout) {
        return '连接超时。请确认手机和平板与运行后端的电脑在同一局域网，并检查地址是否应为类似 192.168.8.xxx:8000。';
      }
      if (error.type == DioExceptionType.connectionError) {
        final message = (error.message ?? '').toLowerCase();
        if (message.contains('connection refused')) {
          return '后端地址可达，但 8000 端口未响应。请确认后端服务已经启动。';
        }
        return '无法连接到后端服务。请检查局域网 IP、端口和 Windows 防火墙设置。';
      }
      final message = error.message?.trim();
      if (message != null && message.isNotEmpty) {
        return '连接失败：$message';
      }
      return '连接失败，请检查手机与服务器是否在同一局域网。';
    } catch (_) {
      return '连接失败，请检查后端服务是否已经启动。';
    }
  }
}
