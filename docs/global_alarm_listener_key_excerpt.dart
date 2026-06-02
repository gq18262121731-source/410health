import 'dart:async';
import 'dart:collection';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/alarm_model.dart';
import '../providers/alarm_provider.dart';

/// 仅保留全局告警监听器最关键的展示逻辑：
/// 1. Provider 监听告警流；
/// 2. 首次加载只展示 2 分钟内的 SOS；
/// 3. 去重 + 队列，保证告警按顺序弹出。
class GlobalAlarmListenerKeyExcerpt extends StatefulWidget {
  final Widget child;

  const GlobalAlarmListenerKeyExcerpt({
    super.key,
    required this.child,
  });

  @override
  State<GlobalAlarmListenerKeyExcerpt> createState() =>
      _GlobalAlarmListenerKeyExcerptState();
}

class _GlobalAlarmListenerKeyExcerptState
    extends State<GlobalAlarmListenerKeyExcerpt> {
  // 核心状态定义。
  static const Duration _initialAlarmWindow = Duration(minutes: 2);
  final Set<String> _handledAlarmIds = <String>{};
  final Set<String> _queuedAlarmIds = <String>{};
  final Queue<AlarmRecord> _pendingSosQueue = ListQueue<AlarmRecord>();

  AlarmProvider? _alarmProvider;
  bool _initialSnapshotLoaded = false;
  bool _dialogVisible = false;
  String? _activeAlarmId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final provider = context.read<AlarmProvider>();
    if (!identical(_alarmProvider, provider)) {
      _alarmProvider?.removeListener(_onAlarmProviderChanged);
      _alarmProvider = provider;
      _alarmProvider?.addListener(_onAlarmProviderChanged);
    }
  }

  @override
  void dispose() {
    _alarmProvider?.removeListener(_onAlarmProviderChanged);
    super.dispose();
  }

  // Provider 变化后的总入口。
  void _onAlarmProviderChanged() {
    if (!mounted) {
      return;
    }

    final provider = _alarmProvider;
    if (provider == null || provider.status != AlarmLoadStatus.loaded) {
      return;
    }

    if (!_initialSnapshotLoaded) {
      _consumeInitialSnapshot(provider.alarms);
      return;
    }

    _consumeRealtimeSosAlarms(provider.alarms);
  }

  // 首次快照只消费 2 分钟内的未确认 SOS。
  void _consumeInitialSnapshot(List<AlarmRecord> alarms) {
    final initialSosAlarms = alarms
        .where(_shouldPresentOnInitialLoad)
        .toList()
      ..sort(_compareByCreatedAt);

    for (final alarm in initialSosAlarms) {
      _trackAndEnqueueAlarm(alarm);
    }

    for (final alarm in alarms) {
      _handledAlarmIds.add(alarm.id);
    }

    _initialSnapshotLoaded = true;
  }

  // 后续把实时新增的 SOS 继续送入弹窗流程。
  void _consumeRealtimeSosAlarms(List<AlarmRecord> alarms) {
    final realtimeSosAlarms = alarms
        .where(_shouldPresentInRealtime)
        .toList()
      ..sort(_compareByCreatedAt);

    for (final alarm in realtimeSosAlarms) {
      _trackAndEnqueueAlarm(alarm);
    }
  }

  void _trackAndEnqueueAlarm(AlarmRecord alarm) {
    _handledAlarmIds.add(alarm.id);
    _enqueueAlarm(alarm);
  }

  // 告警过滤规则。
  bool _shouldPresentOnInitialLoad(AlarmRecord alarm) {
    return !_handledAlarmIds.contains(alarm.id) &&
        _isPendingSosAlarm(alarm) &&
        _isFreshAlarm(alarm);
  }

  bool _shouldPresentInRealtime(AlarmRecord alarm) {
    return !_handledAlarmIds.contains(alarm.id) && _isPendingSosAlarm(alarm);
  }

  bool _isPendingSosAlarm(AlarmRecord alarm) {
    return alarm.isSos && !alarm.acknowledged;
  }

  bool _isFreshAlarm(AlarmRecord alarm) {
    final createdAt = alarm.createdAtDateTime;
    if (createdAt == null) {
      return false;
    }
    final age = DateTime.now().difference(createdAt).abs();
    return age <= _initialAlarmWindow;
  }

  int _compareByCreatedAt(AlarmRecord a, AlarmRecord b) {
    final aTime = a.createdAtDateTime ?? DateTime.fromMillisecondsSinceEpoch(0);
    final bTime = b.createdAtDateTime ?? DateTime.fromMillisecondsSinceEpoch(0);
    return aTime.compareTo(bTime);
  }

  // 去重 + 入队。
  void _enqueueAlarm(AlarmRecord alarm) {
    if (_activeAlarmId == alarm.id || _queuedAlarmIds.contains(alarm.id)) {
      return;
    }

    if (_dialogVisible) {
      _pendingSosQueue.addLast(alarm);
      _queuedAlarmIds.add(alarm.id);
      return;
    }

    _presentAlarmDialog(alarm);
  }

  void _presentAlarmDialog(AlarmRecord alarm) {
    _dialogVisible = true;
    _activeAlarmId = alarm.id;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        _dialogVisible = false;
        _activeAlarmId = null;
        return;
      }
      unawaited(_showAlarmDialog(alarm));
    });
  }

  // 当前处理完后，继续消费队列中的下一条。
  Future<void> _showAlarmDialog(AlarmRecord alarm) async {
    await showDialog<void>(
      context: context,
      useRootNavigator: true,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('SOS 紧急告警'),
        content: Text(alarm.headlineDisplay),
        actions: [
          TextButton(
            onPressed: () {
              _alarmProvider?.acknowledge(alarm.id);
              Navigator.pop(dialogContext);
            },
            child: const Text('我知道了'),
          ),
        ],
      ),
    );

    _dialogVisible = false;
    _activeAlarmId = null;
    _presentNextQueuedAlarm();
  }

  void _presentNextQueuedAlarm() {
    if (!mounted || _pendingSosQueue.isEmpty) {
      return;
    }

    final nextAlarm = _pendingSosQueue.removeFirst();
    _queuedAlarmIds.remove(nextAlarm.id);
    _presentAlarmDialog(nextAlarm);
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}




class GlobalAlarmListenerPptDemo {
  static const Duration freshWindow = Duration(minutes: 2);
  final Set<String> shownIds = <String>{}; // 去重
  final Queue<AlarmRecord> queue = ListQueue<AlarmRecord>(); // 排队
  bool dialogVisible = false;
  void onAlarmsChanged(List<AlarmRecord> alarms, {bool initialLoad = false}) {
    final candidates = alarms.where((alarm) {
      if (shownIds.contains(alarm.id)) return false;
      if (!alarm.isSos || alarm.acknowledged) return false;
      if (!initialLoad) return true;
      return DateTime.now().difference(alarm.createdAt) <= freshWindow;
    });
    for (final alarm in candidates) {
      shownIds.add(alarm.id);
      if (dialogVisible) {
        queue.addLast(alarm);
      } else {
        showDialog(alarm);
      }
    }
  }
}
