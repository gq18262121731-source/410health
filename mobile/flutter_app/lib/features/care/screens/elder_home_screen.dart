import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../widgets/logout_action.dart';
import '../../auth/providers/auth_provider.dart';
import '../models/care_profile_model.dart';
import '../providers/care_provider.dart';
import '../../agent/screens/elder_agent_screen.dart';

class ElderHomeScreen extends StatefulWidget {
  const ElderHomeScreen({super.key});

  @override
  State<ElderHomeScreen> createState() => _ElderHomeScreenState();
}

class _ElderHomeScreenState extends State<ElderHomeScreen> {
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
    final authUser = context.watch<AuthProvider>().user;
    final profile = careProvider.profile;
    final metric = profile != null && profile.deviceMetrics.isNotEmpty ? profile.deviceMetrics.first : null;
    final elderName = metric?.subjectName ?? authUser?.name ?? '长者';

    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        title: Text(
          '$elderName 的健康守护',
          style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        actions: const [LogoutAction()],
      ),
      body: _buildBody(careProvider, elderName, metric),
    );
  }

  Widget _buildBody(CareProvider provider, String elderName, CareAccessDeviceMetric? metric) {
    if (provider.status == CareLoadStatus.loading && provider.profile == null) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFFFF875A)));
    }

    if (provider.status == CareLoadStatus.error && provider.profile == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(provider.errorMessage ?? '加载失败', style: const TextStyle(color: Colors.white70, fontSize: 18)),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => provider.fetchProfile(),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16),
              ),
              child: const Text('重试', style: TextStyle(fontSize: 18)),
            ),
          ],
        ),
      );
    }

    final profile = provider.profile;
    if (profile == null) return const SizedBox.shrink();

    final hasDevice = profile.boundDeviceMacs.isNotEmpty || profile.deviceMetrics.isNotEmpty;
    final deviceStatus = metric?.deviceStatus ?? 'unknown';
    final batteryLabel = metric?.battery != null ? '${metric!.battery}%' : '--';

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildHeaderCard(elderName),
            const SizedBox(height: 20),
            _buildDeviceStatusCard(metric, hasDevice, deviceStatus, batteryLabel),
            const SizedBox(height: 20),
            _buildRealtimeMetrics(metric),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(child: _buildBigButton(Icons.phone, '联系家属', Colors.blue)),
                const SizedBox(width: 24),
                Expanded(child: _buildBigButton(Icons.warning, '一键求助', Colors.red)),
              ],
            ),
            const SizedBox(height: 20),
            _buildBigButton(
              Icons.auto_awesome,
              '智能健康助手',
              const Color(0xFFFF875A),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => ElderAgentScreen(deviceMac: metric?.deviceMac)),
              ),
            ),
            const SizedBox(height: 24),
            _buildInfoCard(profile.basicAdvice),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderCard(String elderName) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            elderName,
            style: const TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  Widget _buildDeviceStatusCard(
    CareAccessDeviceMetric? metric,
    bool hasDevice,
    String status,
    String battery,
  ) {
    final isOnline = status.toLowerCase() == 'online' || status.toLowerCase() == 'normal';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: hasDevice
              ? (isOnline ? Colors.green.withOpacity(0.5) : Colors.orange.withOpacity(0.5))
              : Colors.red.withOpacity(0.3),
        ),
      ),
      child: Column(
        children: [
          Icon(hasDevice ? Icons.watch : Icons.watch_off, size: 64, color: Colors.white54),
          const SizedBox(height: 16),
          Text(
            hasDevice ? '设备已连接' : '设备未连接',
            style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.bold),
          ),
          if (metric != null) ...[
            const SizedBox(height: 8),
            Text(
              '${metric.deviceName} · ${metric.deviceMac}',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white70, fontSize: 18),
            ),
          ],
          const SizedBox(height: 12),
          if (hasDevice)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.battery_full, color: Colors.greenAccent, size: 24),
                const SizedBox(width: 8),
                Text('电量: $battery', style: const TextStyle(color: Colors.white70, fontSize: 22)),
              ],
            ),
        ],
      ),
    );
  }

  Widget _buildRealtimeMetrics(CareAccessDeviceMetric? metric) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        _buildMetricCard('心率', '${metric?.heartRate?.toInt() ?? '--'}', 'bpm', Icons.favorite),
        _buildMetricCard('血氧', '${metric?.bloodOxygen?.toInt() ?? '--'}', '%', Icons.water_drop),
        _buildMetricCard('体温', '${metric?.temperature ?? '--'}', '℃', Icons.thermostat),
        _buildMetricCard('健康度', '${metric?.healthScore ?? '--'}', '分', Icons.monitor_heart),
      ],
    );
  }

  Widget _buildMetricCard(String label, String value, String unit, IconData icon) {
    return Container(
      width: (MediaQuery.of(context).size.width - 60) / 2,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(icon, color: const Color(0xFFFF875A), size: 36),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 22)),
          const SizedBox(height: 6),
          RichText(
            textAlign: TextAlign.center,
            text: TextSpan(
              children: [
                TextSpan(
                  text: value,
                  style: const TextStyle(color: Colors.white, fontSize: 48, fontWeight: FontWeight.bold),
                ),
                TextSpan(
                  text: ' $unit',
                  style: const TextStyle(color: Colors.white38, fontSize: 20),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBigButton(IconData icon, String label, Color color, {VoidCallback? onTap}) {
    return ElevatedButton(
      onPressed: onTap ?? () {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('正在尝试$label...')));
      },
      style: ElevatedButton.styleFrom(
        backgroundColor: color.withOpacity(0.2),
        foregroundColor: color,
        padding: const EdgeInsets.symmetric(vertical: 40),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: color.withOpacity(0.5)),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 56),
          const SizedBox(height: 16),
          Text(label, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildInfoCard(String basicAdvice) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Text('今日提示', style: TextStyle(color: Colors.white54, fontSize: 28)),
          const SizedBox(height: 12),
          Text(
            basicAdvice.isNotEmpty ? basicAdvice : '保持规律作息，继续关注设备同步的实时指标。',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white, fontSize: 30, height: 1.5),
          ),
        ],
      ),
    );
  }
}
