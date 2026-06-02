import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../../../widgets/logout_action.dart';
import '../../agent/widgets/ai_chat_dialog.dart';
import '../../auth/providers/auth_provider.dart';
import '../../camera/repositories/camera_repository.dart';
import '../../voice/screens/voice_screen.dart';
import '../models/care_profile_model.dart';
import '../providers/care_provider.dart';

class ElderHomeScreen extends StatefulWidget {
  const ElderHomeScreen({super.key});

  @override
  State<ElderHomeScreen> createState() => _ElderHomeScreenState();
}

class _ElderHomeScreenState extends State<ElderHomeScreen> {
  CareProvider? _careProvider;
  bool _isBindingDevice = false;
  bool _isUnbindingDevice = false;
  bool _isBindingCamera = false;
  bool _isUnbindingCamera = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _careProvider?.startAutoRefresh();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _careProvider = context.read<CareProvider>();
  }

  @override
  void dispose() {
    _careProvider?.stopAutoRefresh();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final careProvider = context.watch<CareProvider>();
    final authUser = context.watch<AuthProvider>().user;
    final profile = careProvider.profile;
    final metric = profile != null && profile.deviceMetrics.isNotEmpty
        ? profile.deviceMetrics.first
        : null;
    final elderName = metric?.subjectName ?? authUser?.name ?? '长者';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          '$elderName的健康守护',
          style: const TextStyle(
            color: AppColors.textMain,
            fontSize: 28,
            fontWeight: FontWeight.w900,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        iconTheme: const IconThemeData(color: AppColors.textMain),
        actions: const [LogoutAction()],
      ),
      body: _buildBody(careProvider, elderName, metric),
    );
  }

  Widget _buildBody(
    CareProvider provider,
    String elderName,
    CareAccessDeviceMetric? metric,
  ) {
    if (provider.status == CareLoadStatus.loading && provider.profile == null) {
      return const Center(
        child: CircularProgressIndicator(color: Color(0xFF2563EB)),
      );
    }

    if (provider.status == CareLoadStatus.error && provider.profile == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              provider.errorMessage ?? '加载失败',
              style: const TextStyle(
                color: AppColors.textSub,
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => provider.fetchProfile(),
              child: const Text(
                '重试',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Colors.white),
              ),
            ),
          ],
        ),
      );
    }

    final profile = provider.profile;
    if (profile == null) return const SizedBox.shrink();

    final hasDevice =
        profile.boundDeviceMacs.isNotEmpty || profile.deviceMetrics.isNotEmpty;
    final hasRealtimeSample = metric?.hasRealtimeSample ?? false;
    final deviceStatus = metric?.deviceStatus ?? 'unknown';
    final batteryLabel = metric?.battery != null ? '${metric!.battery}%' : '--';
    final currentCameraId = profile.relatedCameraIds.isNotEmpty
        ? profile.relatedCameraIds.first
        : null;

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildHeaderCard(elderName),
            const SizedBox(height: 20),
            _buildDeviceStatusCard(
              metric,
              hasDevice,
              hasRealtimeSample,
              deviceStatus,
              batteryLabel,
            ),
            const SizedBox(height: 20),
            _buildRealtimeMetrics(metric),
            const SizedBox(height: 20),
            _buildCameraBindingCard(provider, currentCameraId),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: _buildBigButton(
                    Icons.phone,
                    '联系家属',
                    Colors.blue,
                  ),
                ),
                const SizedBox(width: 24),
                Expanded(
                  child: _buildBigButton(
                    Icons.warning,
                    '一键求助',
                    Colors.red,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            _buildBigButton(
              Icons.mic,
              '语音对话',
              Colors.purple,
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const VoiceScreen(),
                ),
              ),
            ),
            const SizedBox(height: 20),
            _buildBigButton(
              Icons.auto_awesome,
              '助手帮我看看',
              AppColors.primary,
              onTap: () => showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (context) => AiChatDialog(
                  isElder: true,
                  deviceMac: metric?.deviceMac,
                  availableDevices: profile.deviceMetrics,
                ),
              ),
            ),
            const SizedBox(height: 20),
            hasDevice
                ? _buildUnbindDeviceButton(provider)
                : _buildBindDeviceButton(provider),
            const SizedBox(height: 24),
            _buildInfoCard(
              profile.basicAdvice.isNotEmpty
                  ? profile.basicAdvice
                  : hasDevice
                      ? '当前账号已绑定到有效设备链路，可以查看设备指标、评估结果和健康报告摘要。'
                      : '请先登记并绑定手环，绑定成功后就能在这里看到实时指标和提醒。',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderCard(String elderName) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        elderName,
        textAlign: TextAlign.center,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 48,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }

  Widget _buildDeviceStatusCard(
    CareAccessDeviceMetric? metric,
    bool hasDevice,
    bool hasRealtimeSample,
    String status,
    String battery,
  ) {
    final normalizedStatus = status.toLowerCase();
    final isOnline =
        normalizedStatus == 'online' || normalizedStatus == 'normal';

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          width: 3,
          color: hasDevice
              ? (isOnline && hasRealtimeSample
                  ? AppColors.success
                  : AppColors.warning)
              : AppColors.error,
        ),
      ),
      child: Column(
        children: [
          Icon(
            hasDevice ? Icons.watch : Icons.watch_off,
            size: 64,
            color: hasDevice
                ? (isOnline && hasRealtimeSample ? Colors.green : Colors.orange)
                : Colors.red,
          ),
          const SizedBox(height: 16),
          Text(
            hasDevice ? '手环已连接' : '手环未连接',
            style: const TextStyle(
              color: AppColors.textMain,
              fontSize: 32,
              fontWeight: FontWeight.w900,
            ),
          ),
          if (metric != null) ...[
            const SizedBox(height: 8),
            Text(
              '${metric.deviceName} · ${metric.deviceMac}',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.textSub,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
          const SizedBox(height: 12),
          if (hasDevice)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.battery_full, color: AppColors.success, size: 28),
                const SizedBox(width: 8),
                Text(
                  '电量: $battery',
                  style: const TextStyle(color: AppColors.textMain, fontSize: 24, fontWeight: FontWeight.w800),
                ),
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
        _buildMetricCard('心率', _formatDouble(metric?.heartRate), 'bpm', Icons.favorite),
        _buildMetricCard('血压', metric?.bloodPressure ?? '--', 'mmHg', Icons.bloodtype),
        _buildMetricCard('血氧', _formatDouble(metric?.bloodOxygen), '%', Icons.water_drop),
        _buildMetricCard('体温', _formatDouble(metric?.temperature, fractionDigits: 1), '°C', Icons.thermostat),
        _buildMetricCard('步数', metric?.steps?.toString() ?? '--', '步', Icons.directions_walk),
        _buildMetricCard('健康度', metric?.healthScore?.toString() ?? '--', '分', Icons.monitor_heart),
      ],
    );
  }

  Widget _buildMetricCard(
    String label,
    String value,
    String unit,
    IconData icon,
  ) {
    return Container(
      width: (MediaQuery.of(context).size.width - 60) / 2,
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border, width: 2),
      ),
      child: Column(
        children: [
          Icon(icon, color: const Color(0xFF2563EB), size: 42),
          const SizedBox(height: 12),
          Text(
            label,
            style: const TextStyle(color: AppColors.textSub, fontSize: 24, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          RichText(
            textAlign: TextAlign.center,
            text: TextSpan(
              children: [
                TextSpan(
                  text: value,
                  style: const TextStyle(
                    color: AppColors.textMain,
                    fontSize: 56,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                TextSpan(
                  text: ' $unit',
                  style: const TextStyle(color: AppColors.textSub, fontSize: 24, fontWeight: FontWeight.w900),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraBindingCard(CareProvider provider, String? currentCameraId) {
    final busy = _isBindingCamera || _isUnbindingCamera || provider.isMutating;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.videocam_outlined, color: AppColors.primary, size: 30),
              SizedBox(width: 10),
              Text(
                '摄像头绑定',
                style: TextStyle(
                  color: AppColors.textMain,
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            currentCameraId == null || currentCameraId.isEmpty
                ? '当前未绑定摄像头'
                : '当前摄像头：$currentCameraId',
            style: const TextStyle(
              color: AppColors.textMain,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: busy ? null : () => _showBindCameraDialog(provider),
                  icon: const Icon(Icons.link, color: Colors.white),
                  label: Text(
                    busy ? '处理中...' : (currentCameraId == null || currentCameraId.isEmpty ? '绑定摄像头' : '更换摄像头'),
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Colors.white),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  ),
                ),
              ),
              if (currentCameraId != null && currentCameraId.isNotEmpty) ...[
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: busy ? null : () => _unbindCamera(provider),
                    icon: const Icon(Icons.link_off, color: AppColors.warning),
                    label: const Text(
                      '解绑摄像头',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.warning),
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      side: const BorderSide(color: AppColors.warning, width: 2),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _showBindCameraDialog(CareProvider provider) async {
    final elderId = provider.profile?.userId;
    if (elderId == null || elderId.isEmpty) return;
    final cameraRepository = context.read<CameraRepository>();
    final sources = await cameraRepository.listCameraSources();
    if (!mounted) return;
    final enabledSources = sources.where((item) => item.enabled).toList(growable: false);
    if (enabledSources.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('当前没有可用摄像头源')),
      );
      return;
    }
    String selectedCameraId =
        provider.profile?.relatedCameraIds.isNotEmpty == true
            ? provider.profile!.relatedCameraIds.first
            : enabledSources.first.cameraId;
    final picked = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('选择摄像头'),
        content: StatefulBuilder(
          builder: (context, setState) => SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: enabledSources
                  .map(
                    (source) => RadioListTile<String>(
                      value: source.cameraId,
                      groupValue: selectedCameraId,
                      title: Text(source.label),
                      subtitle: Text('${source.cameraId} · ${source.sourceMode}'),
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => selectedCameraId = value);
                      },
                    ),
                  )
                  .toList(growable: false),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, selectedCameraId),
            child: const Text('确认绑定'),
          ),
        ],
      ),
    );
    if (picked == null || picked.isEmpty) return;
    setState(() => _isBindingCamera = true);
    try {
      final success = await provider.bindElderCamera(elderId: elderId, cameraId: picked);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? '摄像头绑定成功' : (provider.errorMessage ?? '摄像头绑定失败')),
          backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isBindingCamera = false);
        _resumeAutoRefreshAfterBuild(provider);
      }
    }
  }

  Future<void> _unbindCamera(CareProvider provider) async {
    final elderId = provider.profile?.userId;
    if (elderId == null || elderId.isEmpty) return;
    setState(() => _isUnbindingCamera = true);
    try {
      final success = await provider.unbindElderCamera(elderId: elderId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? '摄像头已解绑' : (provider.errorMessage ?? '解绑摄像头失败')),
          backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isUnbindingCamera = false);
        _resumeAutoRefreshAfterBuild(provider);
      }
    }
  }

  Widget _buildBindDeviceButton(CareProvider provider) {
    final isBusy = _isBindingDevice || provider.isMutating;
    return ElevatedButton.icon(
      onPressed: isBusy ? null : () => _showBindDeviceDialog(provider),
      icon: isBusy
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
            )
          : const Icon(Icons.add_link, size: 32, color: Colors.white),
      label: Text(
        isBusy ? '处理中...' : '绑定新手环',
        style: const TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.w900),
      ),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 24),
        backgroundColor: AppColors.primary,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
    );
  }

  Widget _buildUnbindDeviceButton(CareProvider provider) {
    final isBusy = _isUnbindingDevice || provider.isMutating;
    return OutlinedButton.icon(
      onPressed: isBusy ? null : () => _performUnbindDevice(provider),
      icon: isBusy
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.warning),
            )
          : const Icon(Icons.link_off, size: 28, color: AppColors.warning),
      label: Text(
        isBusy ? '处理中...' : '解绑手环设备',
        style: const TextStyle(fontSize: 22, color: AppColors.warning, fontWeight: FontWeight.w900),
      ),
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 20),
        side: const BorderSide(color: AppColors.warning, width: 2),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
    );
  }

  Widget _buildBigButton(
    IconData icon,
    String label,
    Color color, {
    VoidCallback? onTap,
  }) {
    return ElevatedButton(
      onPressed: onTap ??
          () {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('正在尝试$label...')),
            );
          },
      style: ElevatedButton.styleFrom(
        backgroundColor: color.withValues(alpha: 0.08),
        foregroundColor: color,
        padding: const EdgeInsets.symmetric(vertical: 48),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: color, width: 3),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 64, color: color),
          const SizedBox(height: 16),
          Text(
            label,
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: color),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCard(String basicAdvice) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.elderBlueBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFBFDBFE), width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const Text(
            '今日健康建议',
            style: TextStyle(color: AppColors.elderBlueText, fontSize: 32, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 16),
          Text(
            basicAdvice,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.textMain,
              fontSize: 34,
              fontWeight: FontWeight.w900,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _showBindDeviceDialog(CareProvider provider) async {
    provider.stopAutoRefresh();
    final macController = TextEditingController();
    final nameController = TextEditingController(text: 'T10-WATCH');
    final result = await showDialog<_BindDeviceResult>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('登记并绑定手环'),
        content: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDialogField(controller: macController, label: '手环 MAC 地址', hintText: '例如 54:10:26:01:00:DF'),
              const SizedBox(height: 12),
              _buildDialogField(controller: nameController, label: '设备名称', hintText: '默认 T10-WATCH'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(
              dialogContext,
              _BindDeviceResult(
                macAddress: _normalizeMacInput(macController.text),
                deviceName: nameController.text.trim(),
              ),
            ),
            child: const Text('确认绑定'),
          ),
        ],
      ),
    );
    macController.dispose();
    nameController.dispose();
    if (result == null) {
      _resumeAutoRefreshAfterBuild(provider);
      return;
    }
    await _performBindDevice(provider, result);
  }

  Future<void> _performBindDevice(
    CareProvider provider,
    _BindDeviceResult result,
  ) async {
    if (_isBindingDevice) {
      _resumeAutoRefreshAfterBuild(provider);
      return;
    }
    setState(() => _isBindingDevice = true);
    try {
      final success = await provider.bindSelfDevice(
        result.macAddress,
        deviceName: result.deviceName,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? '手环已成功绑定' : (provider.errorMessage ?? '绑定手环失败')),
          backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isBindingDevice = false);
        _resumeAutoRefreshAfterBuild(provider);
      }
    }
  }

  Future<void> _performUnbindDevice(CareProvider provider) async {
    if (_isUnbindingDevice) return;
    setState(() => _isUnbindingDevice = true);
    try {
      final success = await provider.unbindSelfDevice();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(success ? '手环已解绑' : (provider.errorMessage ?? '解绑手环失败')),
          backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isUnbindingDevice = false);
        _resumeAutoRefreshAfterBuild(provider);
      }
    }
  }

  void _resumeAutoRefreshAfterBuild(CareProvider provider) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Future<void>.delayed(const Duration(milliseconds: 80), () {
        if (mounted) {
          provider.startAutoRefresh();
        }
      });
    });
  }

  Widget _buildDialogField({
    required TextEditingController controller,
    required String label,
    required String hintText,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: AppColors.textMain, fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: controller,
          decoration: InputDecoration(
            hintText: hintText,
            filled: true,
            fillColor: Colors.white,
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: AppColors.border, width: 1.5),
            ),
            focusedBorder: const OutlineInputBorder(
              borderRadius: BorderRadius.all(Radius.circular(12)),
              borderSide: BorderSide(color: AppColors.primary, width: 2),
            ),
          ),
        ),
      ],
    );
  }

  String _formatDouble(double? value, {int fractionDigits = 0}) {
    if (value == null) return '--';
    return value.toStringAsFixed(fractionDigits);
  }

  String _normalizeMacInput(String rawValue) {
    final compact =
        rawValue.replaceAll(RegExp(r'[^0-9A-Fa-f]'), '').toUpperCase();
    if (compact.length != 12) {
      return rawValue.trim().toUpperCase();
    }
    final parts = <String>[];
    for (var index = 0; index < compact.length; index += 2) {
      parts.add(compact.substring(index, index + 2));
    }
    return parts.join(':');
  }
}

class _BindDeviceResult {
  final String macAddress;
  final String? deviceName;

  const _BindDeviceResult({
    required this.macAddress,
    required this.deviceName,
  });
}
