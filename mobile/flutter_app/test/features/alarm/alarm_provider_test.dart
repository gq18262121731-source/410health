import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'package:ai_health_iot_flutter/core/network/api_client.dart';
import 'package:ai_health_iot_flutter/core/network/server_endpoint_config.dart';
import 'package:ai_health_iot_flutter/features/alarm/models/alarm_model.dart';
import 'package:ai_health_iot_flutter/features/alarm/providers/alarm_provider.dart';
import 'package:ai_health_iot_flutter/features/alarm/repositories/alarm_repository.dart';
import 'package:ai_health_iot_flutter/features/session/services/session_manager.dart';

class _TestAlarmRepository extends AlarmRepository {
  _TestAlarmRepository({
    required ServerEndpointConfig endpointConfig,
    required ApiClient apiClient,
    required SessionManager sessionManager,
    required this.alarmsResult,
    required this.queueResult,
    required this.pushesResult,
    required this.channel,
  }) : super(
          apiClient,
          endpointConfig: endpointConfig,
          sessionManager: sessionManager,
        );

  final Future<List<AlarmRecord>> Function() alarmsResult;
  final Future<List<AlarmQueueItem>> Function() queueResult;
  final Future<List<MobilePushRecord>> Function() pushesResult;
  final WebSocketChannel channel;

  @override
  Future<List<AlarmRecord>> getAlarms({bool activeOnly = false}) => alarmsResult();

  @override
  Future<List<AlarmQueueItem>> getAlarmQueue() => queueResult();

  @override
  Future<List<MobilePushRecord>> getMobilePushes() => pushesResult();

  @override
  WebSocketChannel connectToAlarms() => channel;
}

class _FakeWebSocketChannel implements WebSocketChannel {
  _FakeWebSocketChannel() : _controller = StreamController<dynamic>.broadcast();

  final StreamController<dynamic> _controller;
  bool closed = false;

  @override
  Stream get stream => _controller.stream;

  @override
  WebSocketSink get sink => _FakeWebSocketSink(
        onClose: () {
          closed = true;
          _controller.close();
        },
      );

  @override
  String? get protocol => null;

  @override
  int? get closeCode => null;

  @override
  String? get closeReason => null;

  @override
  Future<void> get ready => Future.value();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeWebSocketSink implements WebSocketSink {
  _FakeWebSocketSink({required this.onClose});

  final VoidCallback onClose;

  @override
  void add(event) {}

  @override
  void addError(error, [StackTrace? stackTrace]) {}

  @override
  Future addStream(Stream stream) => Future.value();

  @override
  Future close([int? closeCode, String? closeReason]) async {
    onClose();
  }

  @override
  Future get done => Future.value();
}

AlarmRecord _buildAlarm({required String id}) {
  return AlarmRecord(
    id: id,
    deviceMac: '54:10:26:01:00:DF',
    alarmType: 'sos',
    alarmLevel: 'sos',
    alarmPriority: 1,
    message: 'SOS',
    createdAt: '2026-05-01T03:12:30Z',
    acknowledged: false,
    anomalyProbability: 1.0,
    metadata: const {
      'elder_name': '张三',
      'device_name': 'T10-WATCH-A',
      'apartment': '1-101',
      'sos_trigger': 'long_press',
    },
  );
}

AlarmQueueItem _buildQueueItem({required String id}) {
  return AlarmQueueItem(
    score: 1.0,
    alarm: _buildAlarm(id: id),
  );
}

Future<_TestAlarmRepository> _buildRepository({
  required Future<List<AlarmRecord>> Function() alarmsResult,
  required Future<List<AlarmQueueItem>> Function() queueResult,
  required Future<List<MobilePushRecord>> Function() pushesResult,
  required _FakeWebSocketChannel channel,
}) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final endpointConfig = ServerEndpointConfig(prefs);
  final sessionManager = SessionManager(prefs);
  final apiClient = ApiClient(
    endpointConfig: endpointConfig,
    sessionManager: sessionManager,
    onUnauthorized: () {},
  );
  return _TestAlarmRepository(
    endpointConfig: endpointConfig,
    apiClient: apiClient,
    sessionManager: sessionManager,
    alarmsResult: alarmsResult,
    queueResult: queueResult,
    pushesResult: pushesResult,
    channel: channel,
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('init hydrates visible alarms from queue before websocket replay', () async {
    final channel = _FakeWebSocketChannel();
    final repository = await _buildRepository(
      alarmsResult: () async => <AlarmRecord>[],
      queueResult: () async => <AlarmQueueItem>[_buildQueueItem(id: 'alarm-1')],
      pushesResult: () async => <MobilePushRecord>[],
      channel: channel,
    );
    final provider = AlarmProvider(repository);

    await provider.init();

    expect(provider.status, AlarmLoadStatus.loaded);
    expect(provider.queue, hasLength(1));
    expect(provider.alarms, hasLength(1));
    expect(provider.alarms.first.id, 'alarm-1');
    expect(provider.alarms.first.elderName, '张三');
    expect(provider.alarms.first.apartment, '1-101');
  });

  test('init keeps realtime alarm startup alive when mobile pushes fail', () async {
    final channel = _FakeWebSocketChannel();
    final repository = await _buildRepository(
      alarmsResult: () async => <AlarmRecord>[],
      queueResult: () async => <AlarmQueueItem>[_buildQueueItem(id: 'alarm-2')],
      pushesResult: () async => throw Exception('push endpoint unavailable'),
      channel: channel,
    );
    final provider = AlarmProvider(repository);

    await provider.init();

    expect(provider.status, AlarmLoadStatus.loaded);
    expect(provider.alarms, hasLength(1));
    expect(provider.pushes, isEmpty);
  });
}
