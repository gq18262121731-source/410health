import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/alarm_provider.dart';
import '../models/alarm_model.dart';
import '../../../widgets/logout_action.dart';

class AlarmCenterScreen extends StatefulWidget {
  const AlarmCenterScreen({super.key});

  @override
  State<AlarmCenterScreen> createState() => _AlarmCenterScreenState();
}

class _AlarmCenterScreenState extends State<AlarmCenterScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AlarmProvider>().init();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final alarmProvider = context.watch<AlarmProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        title: const Text('告警中心', style: TextStyle(color: Colors.white, fontSize: 18)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: const [LogoutAction()],
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFFFF875A),
          unselectedLabelColor: Colors.white30,
          indicatorColor: const Color(0xFFFF875A),
          tabs: const [
            Tab(text: '活动告警'),
            Tab(text: '调度队列'),
            Tab(text: '推送记录'),
          ],
        ),
      ),
      body: _buildBody(alarmProvider),
    );
  }

  Widget _buildBody(AlarmProvider provider) {
    if (provider.status == AlarmLoadStatus.loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFFFF875A)));
    }

    if (provider.status == AlarmLoadStatus.error) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(provider.errorMessage ?? '加载失败', style: const TextStyle(color: Colors.white70)),
            TextButton(onPressed: () => provider.init(), child: const Text('重试')),
          ],
        ),
      );
    }

    return TabBarView(
      controller: _tabController,
      children: [
        _buildAlarmList(provider.alarms, provider),
        _buildQueueList(provider.queue),
        _buildPushList(provider.pushes),
      ],
    );
  }

  Widget _buildAlarmList(List<AlarmRecord> alarms, AlarmProvider provider) {
    if (alarms.isEmpty) {
      return const Center(child: Text('暂无未确认告警', style: TextStyle(color: Colors.white24)));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: alarms.length,
      itemBuilder: (context, index) => _buildAlarmCard(alarms[index], provider),
    );
  }

  Widget _buildAlarmCard(AlarmRecord alarm, AlarmProvider provider) {
    final isSOS = alarm.alarmType.toLowerCase().contains('sos');
    final isCritical = alarm.alarmLevel.toLowerCase() == 'critical';

    return Card(
      color: (isSOS || isCritical) ? Colors.redAccent.withOpacity(0.1) : Colors.white.withOpacity(0.05),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: (isSOS || isCritical) ? const BorderSide(color: Colors.redAccent, width: 0.5) : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  isSOS ? Icons.sos : Icons.warning_amber_rounded,
                  color: (isSOS || isCritical) ? Colors.redAccent : Colors.orangeAccent,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    alarm.alarmType.toUpperCase(),
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  alarm.createdAt.split('T').first,
                  style: const TextStyle(color: Colors.white24, fontSize: 10),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              alarm.message,
              style: const TextStyle(color: Colors.white70, fontSize: 14),
            ),
            const SizedBox(height: 8),
            Text(
              '设备: ${alarm.deviceMac}',
              style: const TextStyle(color: Colors.white24, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                if (alarm.acknowledged)
                  const Row(
                    children: [
                      Icon(Icons.check_circle, color: Colors.greenAccent, size: 16),
                      SizedBox(width: 4),
                      Text('已确认', style: TextStyle(color: Colors.greenAccent, fontSize: 12)),
                    ],
                  )
                else
                  ElevatedButton(
                    onPressed: () => provider.acknowledge(alarm.id),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFF875A),
                      foregroundColor: const Color(0xFF08161B),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 0),
                      minimumSize: const Size(80, 32),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    child: const Text('确认告警', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQueueList(List<AlarmQueueItem> queue) {
    if (queue.isEmpty) {
      return const Center(child: Text('调度队列为空', style: TextStyle(color: Colors.white24)));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: queue.length,
      itemBuilder: (context, index) {
        final item = queue[index];
        return ListTile(
          leading: CircleAvatar(
            backgroundColor: Color.lerp(Colors.orange, Colors.red, item.priority / 10),
            radius: 4,
          ),
          title: Text('MAC: ${item.deviceMac}', style: const TextStyle(color: Colors.white, fontSize: 14)),
          subtitle: Text('优先级: ${item.priority} | 状态: ${item.status}', style: const TextStyle(color: Colors.white30, fontSize: 12)),
          trailing: const Icon(Icons.low_priority, color: Colors.white10),
        );
      },
    );
  }

  Widget _buildPushList(List<MobilePushRecord> pushes) {
    if (pushes.isEmpty) {
      return const Center(child: Text('暂无历史推送', style: TextStyle(color: Colors.white24)));
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: pushes.length,
      itemBuilder: (context, index) {
        final push = pushes[index];
        return Card(
          color: Colors.white.withOpacity(0.02),
          child: ListTile(
            title: Text(push.title, style: const TextStyle(color: Colors.white, fontSize: 14)),
            subtitle: Text(push.body, style: const TextStyle(color: Colors.white30, fontSize: 12)),
            trailing: Text(push.createdAt.split('T').first, style: const TextStyle(color: Colors.white10, fontSize: 10)),
          ),
        );
      },
    );
  }
}
