import 'dart:collection';

/// PPT 演示极简版：只保留核心思想，不参与实际业务运行。
class AlarmRecord {
  final String id;
  final bool isSos;
  final bool acknowledged;
  final DateTime createdAt;

  AlarmRecord({
    required this.id,
    required this.isSos,
    required this.acknowledged,
    required this.createdAt,
  });
}

class GlobalAlarmListenerPptDemo {
  static const Duration freshWindow = Duration(minutes: 2);

  final Set<String> shownIds = <String>{}; // 去重
  final Queue<AlarmRecord> queue = ListQueue<AlarmRecord>(); // 排队
  bool dialogVisible = false;

  void onAlarmsChanged(List<AlarmRecord> alarms, {bool initialLoad = false}) {
    final candidates = alarms.where((alarm) {
      if (shownIds.contains(alarm.id)) return false; // 已展示过，直接过滤
      if (!alarm.isSos || alarm.acknowledged) return false; // 只处理未确认 SOS
      if (!initialLoad) return true; // 实时告警直接放行
      return DateTime.now().difference(alarm.createdAt) <= freshWindow;
    });

    for (final alarm in candidates) {
      shownIds.add(alarm.id);
      if (dialogVisible) {
        queue.addLast(alarm); // 当前有弹窗，新告警先入队
      } else {
        showDialog(alarm); // 没有弹窗，立即展示
      }
    }
  }

  void onDialogClosed() {
    dialogVisible = false;
    if (queue.isNotEmpty) {
      showDialog(queue.removeFirst()); // 当前处理完，继续下一条
    }
  }

  void showDialog(AlarmRecord alarm) {
    dialogVisible = true;
    print('show SOS dialog: ${alarm.id}');
  }
}
