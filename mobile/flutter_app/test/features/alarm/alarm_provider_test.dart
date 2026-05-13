import 'dart:async';
import 'dart:convert';

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

AlarmRecord _buildFallAlarm({
  required String id,
  required String incidentId,
  String title = '检测到老人跌倒，请立即处理',
  String lead = '系统已识别到高风险跌倒事件，请立刻查看现场。',
  List<String> actions = const <String>['立即查看现场', '联系护理人员'],
}) {
  return AlarmRecord(
    id: id,
    deviceMac: 'CAMERA-192.168.8.253',
    alarmType: 'fall_injury_risk',
    alarmLevel: 'critical',
    alarmPriority: 2,
    message: '$title: $lead',
    createdAt: '2026-05-13T03:12:30Z',
    acknowledged: false,
    anomalyProbability: 0.91,
    metadata: <String, dynamic>{
      'incident_id': incidentId,
      'elder_name': '王阿姨',
      'apartment': '2-302',
      'presentation': <String, dynamic>{
        'title': title,
        'lead': lead,
        'show_immediate_popup': true,
        'recommended_actions': actions,
        'review_status': 'pending',
      },
      'family_guidance': const <String, dynamic>{
        'severity_label': '高危跌倒',
        'immediate_actions': <String>['先确认意识和呼吸', '不要强行扶起'],
        'contraindications': <String>['不要拖拽老人'],
        'call_emergency': true,
        'family_message': '如老人无反应或呼吸异常，请立刻呼叫急救。',
      },
      'event': <String, dynamic>{
        'incident_id': incidentId,
        'state': 'confirmed_fall',
      },
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

  test('fall alarm websocket refresh replaces previous alarm by incident id', () async {
    final channel = _FakeWebSocketChannel();
    final repository = await _buildRepository(
      alarmsResult: () async => <AlarmRecord>[
        _buildFallAlarm(id: 'fall-1', incidentId: 'incident-1'),
      ],
      queueResult: () async => <AlarmQueueItem>[],
      pushesResult: () async => <MobilePushRecord>[],
      channel: channel,
    );
    final provider = AlarmProvider(repository);

    await provider.init();
    expect(provider.alarms, hasLength(1));
    expect(provider.alarms.first.id, 'fall-1');

    channel._controller.add(
      jsonEncode(
        _buildFallAlarm(
          id: 'fall-2',
          incidentId: 'incident-1',
          lead: '系统复核后确认风险上升，请立即联系护理人员。',
        ).toJson(),
      ),
    );
    await Future<void>.delayed(const Duration(milliseconds: 30));

    expect(provider.alarms, hasLength(1));
    expect(provider.alarms.first.id, 'fall-2');
    expect(provider.alarms.first.incidentId, 'incident-1');
  });

  test('fall review finalized merges presentation and guidance into existing incident', () async {
    final channel = _FakeWebSocketChannel();
    final repository = await _buildRepository(
      alarmsResult: () async => <AlarmRecord>[
        _buildFallAlarm(id: 'fall-3', incidentId: 'incident-2'),
      ],
      queueResult: () async => <AlarmQueueItem>[],
      pushesResult: () async => <MobilePushRecord>[],
      channel: channel,
    );
    final provider = AlarmProvider(repository);

    await provider.init();

    channel._controller.add(
      jsonEncode(<String, dynamic>{
        'type': 'fall_alarm_pending_review',
        'incident_id': 'incident-2',
        'title': '系统正在复核现场，请稍等',
        'lead': '已检测到异常姿态，系统正在进一步复核。',
      }),
    );
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(provider.pendingFallReviews.containsKey('incident-2'), isTrue);

    channel._controller.add(
      jsonEncode(<String, dynamic>{
        'type': 'fall_alarm_finalized',
        'incident_id': 'incident-2',
        'presentation': <String, dynamic>{
          'title': '系统复核后倾向于误报',
          'lead': '系统已完成二次复核，当前更像误报，但仍建议人工确认。',
          'show_immediate_popup': true,
          'recommended_actions': <String>['继续观察现场'],
          'review_status': 'completed',
        },
        'family_guidance': <String, dynamic>{
          'severity_label': '疑似误报待确认',
          'immediate_actions': <String>['继续观察现场'],
          'contraindications': <String>[],
          'call_emergency': false,
          'family_message': '当前更像误报，但仍建议人工确认。',
        },
        'event': <String, dynamic>{
          'incident_id': 'incident-2',
          'state': 'suspected_fall',
        },
        'review': <String, dynamic>{
          'judgement': 'false_positive',
        },
      }),
    );
    await Future<void>.delayed(const Duration(milliseconds: 30));

    expect(provider.pendingFallReviews.containsKey('incident-2'), isFalse);
    expect(provider.alarms.first.fallTitle, '系统复核后倾向于误报');
    expect(provider.alarms.first.fallSeverityLabel, '疑似误报待确认');
    expect(provider.alarms.first.recommendedActions, contains('继续观察现场'));
  });
}
