import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../widgets/logout_action.dart';
import '../../agent/widgets/ai_chat_dialog.dart';
import '../../alarm/providers/alarm_provider.dart';
import '../../alarm/screens/alarm_center_screen.dart';
import '../../health/providers/health_provider.dart';
import '../../health/repositories/health_repository.dart';
import '../../health/screens/device_detail_screen.dart';
import '../../settings/screens/server_settings_screen.dart';
import '../../voice/screens/voice_screen.dart';
import '../models/care_profile_model.dart';
import '../providers/care_provider.dart';

class FamilyHomeScreen extends StatefulWidget {
  const FamilyHomeScreen({super.key});

  @override
  State<FamilyHomeScreen> createState() => _FamilyHomeScreenState();
}

class _FamilyHomeScreenState extends State<FamilyHomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CareProvider>().startAutoRefresh();
    });
  }

  @override
  void dispose() {
    context.read<CareProvider>().stopAutoRefresh();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final careProvider = context.watch<CareProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        title: const Text(
          '家人守护',
          style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          _buildAlarmAction(context),
          const LogoutAction(),
          IconButton(
            icon: const Icon(Icons.settings_ethernet, color: Colors.white70),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const ServerSettingsScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white70),
            onPressed: () => careProvider.fetchProfile(),
          ),
        ],
      ),
      body: _buildBody(careProvider),
    );
  }

  Widget _buildAlarmAction(BuildContext context) {
    final hasUnacknowledged = context.watch<AlarmProvider>().alarms.any((alarm) => !alarm.acknowledged);

    return Stack(
      children: [
        IconButton(
          icon: const Icon(Icons.notifications_none, color: Colors.white),
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const AlarmCenterScreen()),
            );
          },
        ),
        if (hasUnacknowledged)
          Positioned(
            right: 12,
            top: 12,
            child: Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                color: Colors.redAccent,
                shape: BoxShape.circle,
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildBody(CareProvider provider) {
    if (provider.status == CareLoadStatus.loading && provider.profile == null) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFFFF875A)));
    }

    if (provider.status == CareLoadStatus.error && provider.profile == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(provider.errorMessage ?? '加载失败', style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => provider.fetchProfile(),
              child: const Text('重试'),
            ),
          ],
        ),
      );
    }

    final profile = provider.profile;
    if (profile == null) return const SizedBox.shrink();

    if (profile.bindingState == 'unbound') {
      return _buildUnboundState();
    }

    return _buildBoundState(profile);
  }

  Widget _buildUnboundState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.device_unknown, size: 80, color: Colors.white24),
            const SizedBox(height: 24),
            const Text(
              '当前还没有绑定老人设备',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            const Text(
              '完成绑定后，家庭端会自动刷新并实时显示对应虚拟设备的 mock 数据。',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white70),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBoundState(CareAccessProfile profile) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildRealtimeBanner(),
        const SizedBox(height: 20),
        _buildSectionTitle('我的关注'),
        ...profile.deviceMetrics.map(_buildDeviceCard),
        const SizedBox(height: 16),
        _buildVoiceEntry(context),
        const SizedBox(height: 24),
        _buildSectionTitle('AI 健康对话'),
        _buildAgentEntry(context, profile),
      ],
    );
  }

  Widget _buildRealtimeBanner() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFFF875A).withOpacity(0.2)),
      ),
      child: const Row(
        children: [
          Icon(Icons.podcasts, color: Color(0xFFFF875A)),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              '已开启自动刷新，登录后会持续显示绑定虚拟设备的实时 mock 数据。',
              style: TextStyle(color: Colors.white70, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(
        title,
        style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildDeviceCard(CareAccessDeviceMetric metric) {
    return Card(
      color: Colors.white.withOpacity(0.05),
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => ChangeNotifierProvider(
                create: (context) => HealthProvider(
                  context.read<HealthRepository>(),
                  metric.deviceMac,
                ),
                child: DeviceDetailScreen(deviceMac: metric.deviceMac),
              ),
            ),
          );
        },
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Row(
                children: [
                  const Icon(Icons.watch, color: Color(0xFFFF875A)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          metric.subjectName,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${metric.deviceName} · ${metric.deviceMac}',
                          style: const TextStyle(color: Colors.white54, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: (metric.healthScore ?? 0) >= 80
                          ? Colors.green.withOpacity(0.2)
                          : Colors.orange.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '健康度 ${metric.healthScore ?? '--'}',
                      style: TextStyle(
                        color: (metric.healthScore ?? 0) >= 80 ? Colors.greenAccent : Colors.orangeAccent,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _buildMetricItem(Icons.favorite, '心率', '${metric.heartRate?.toInt() ?? '--'} bpm'),
                  _buildMetricItem(Icons.thermostat, '体温', '${metric.temperature ?? '--'} ℃'),
                  _buildMetricItem(Icons.water_drop, '血氧', '${metric.bloodOxygen?.toInt() ?? '--'} %'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMetricItem(IconData icon, String label, String value) {
    return Column(
      children: [
        Icon(icon, size: 20, color: Colors.white54),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(color: Colors.white30, fontSize: 10)),
      ],
    );
  }

  Widget _buildVoiceEntry(BuildContext context) {
    return InkWell(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (context) => const VoiceScreen()),
        );
      },
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [const Color(0xFFFF875A).withOpacity(0.1), Colors.transparent],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFFF875A).withOpacity(0.2)),
        ),
        child: const Row(
          children: [
            Icon(Icons.mic_none, color: Color(0xFFFF875A), size: 24),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('智能语音交互', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                  Text('语音转文字与合成播报', style: TextStyle(color: Colors.white30, fontSize: 12)),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.white24),
          ],
        ),
      ),
    );
  }

  Widget _buildAgentEntry(BuildContext context, CareAccessProfile profile) {
    return InkWell(
      onTap: () {
        final mac = profile.deviceMetrics.isNotEmpty ? profile.deviceMetrics.first.deviceMac : null;

        showModalBottomSheet(
          context: context,
          isScrollControlled: true,
          backgroundColor: Colors.transparent,
          barrierColor: Colors.black87,
          builder: (context) => AiChatDialog(deviceMac: mac),
        );
      },
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white10),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFF875A).withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.auto_awesome, color: Color(0xFFFF875A)),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('向守护助手提问', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                  SizedBox(height: 4),
                  Text('支持快捷输入和心率血氧异常解读', style: TextStyle(color: Colors.white54, fontSize: 12)),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white24, size: 16),
          ],
        ),
      ),
    );
  }
}
