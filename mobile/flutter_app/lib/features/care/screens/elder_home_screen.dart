import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../widgets/logout_action.dart';
import '../../agent/widgets/ai_chat_dialog.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/theme/app_colors.dart';
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
              style: const TextStyle(color: AppColors.textSub, fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => provider.fetchProfile(),
              child: const Text('重试', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Colors.white)),
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
            _buildRealtimeMetrics(
              metric,
              hasDevice: hasDevice,
              hasRealtimeSample: hasRealtimeSample,
            ),
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
                      ? '当前账号已绑定到有效设备链路，可查看设备指标、评估结果和健康报告摘要。'
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
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.2),
            blurRadius: 15,
            offset: const Offset(0, 8),
          )
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            elderName,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 48,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
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
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          )
        ],
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
              style: const TextStyle(color: AppColors.textSub, fontSize: 20, fontWeight: FontWeight.bold),
            ),
            if (!hasRealtimeSample) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: AppColors.warning.withValues(alpha: 0.35),
                    width: 1.5,
                  ),
                ),
                child: const Text(
                  '手环已绑定，正在等待第一批健康数据。请保持佩戴并等待 10-30 秒。',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: AppColors.warning,
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    height: 1.35,
                  ),
                ),
              ),
            ],
          ] else ...[
            const SizedBox(height: 8),
            const Text(
              '请戴好手环，数据会自动同步。',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSub, fontSize: 20, fontWeight: FontWeight.bold),
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

  Widget _buildRealtimeMetrics(
    CareAccessDeviceMetric? metric, {
    required bool hasDevice,
    required bool hasRealtimeSample,
  }) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        if (hasDevice && !hasRealtimeSample)
          Container(
            width: MediaQuery.of(context).size.width - 48,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFBEB),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFF59E0B), width: 1.5),
            ),
            child: const Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.sync, color: Color(0xFFF59E0B), size: 28),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '已连接手环，但暂未收到有效健康数据包。页面会自动刷新，收到后会立即显示心率、血氧、血压等指标。',
                    style: TextStyle(
                      color: Color(0xFF92400E),
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
        _buildMetricCard(
          '心率',
          _formatDouble(metric?.heartRate),
          'bpm',
          Icons.favorite,
        ),
        _buildMetricCard(
          '血压',
          metric?.bloodPressure ?? '--',
          'mmHg',
          Icons.bloodtype,
        ),
        _buildMetricCard(
          '血氧',
          _formatDouble(metric?.bloodOxygen),
          '%',
          Icons.water_drop,
        ),
        _buildMetricCard(
          '体温',
          _formatDouble(metric?.temperature, fractionDigits: 1),
          '°C',
          Icons.thermostat,
        ),
        _buildMetricCard(
          '步数',
          metric?.steps?.toString() ?? '--',
          '步',
          Icons.directions_walk,
        ),
        _buildMetricCard(
          '健康度',
          metric?.healthScore?.toString() ?? '--',
          '分',
          Icons.monitor_heart,
        ),
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
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 8,
            offset: const Offset(0, 4),
          )
        ],
        border: Border.all(color: AppColors.border, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
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
                    fontSize: 56, // Enormous font for elders
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
        style: const TextStyle(
          fontSize: 26,
          color: Colors.white,
          fontWeight: FontWeight.w900,
        ),
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
      onPressed: isBusy
          ? null
          : () async {
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (dialogContext) => AlertDialog(
                  backgroundColor: AppColors.surface,
                  shape: RoundedRectangleBorder(
                    side: const BorderSide(color: AppColors.warning, width: 2),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  title: const Text(
                    '解绑手环设备',
                    style: TextStyle(
                      color: AppColors.warning,
                      fontWeight: FontWeight.w900,
                      fontSize: 24,
                    ),
                  ),
                  content: const Text(
                    '确认解绑后，这只手环会与当前账号解除绑定，实时健康数据将停止同步。',
                    style: TextStyle(
                      color: AppColors.textMain,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      height: 1.5,
                    ),
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(dialogContext, false),
                      child: const Text(
                        '取消',
                        style: TextStyle(color: AppColors.textSub, fontSize: 20, fontWeight: FontWeight.bold),
                      ),
                    ),
                    TextButton(
                      onPressed: () => Navigator.pop(dialogContext, true),
                      child: const Text(
                        '确认解绑',
                        style: TextStyle(
                          color: AppColors.error,
                          fontWeight: FontWeight.w900,
                          fontSize: 20,
                        ),
                      ),
                    ),
                  ],
                ),
              );
              if (confirmed != true) return;

              await _performUnbindDevice(provider);
            },
      icon: isBusy
          ? const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.warning),
            )
          : const Icon(Icons.link_off, size: 28, color: AppColors.warning),
      label: Text(
        isBusy ? '处理中...' : '解绑手环设备',
        style: const TextStyle(
          fontSize: 22,
          color: AppColors.warning,
          fontWeight: FontWeight.w900,
        ),
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
            style: TextStyle(fontSize: 32, fontWeight: FontWeight.w900, color: color, letterSpacing: 2),
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
        color: AppColors.elderBlueBg, // Light blue background
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
      builder: (dialogContext) {
        String? localError;
        return StatefulBuilder(
          builder: (dialogContext, setState) => AlertDialog(
            backgroundColor: AppColors.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: const BorderSide(color: AppColors.primary, width: 2),
            ),
            title: const Text(
              '登记并绑定手环',
              style: TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w900,
                fontSize: 26,
              ),
            ),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildDialogField(
                    controller: macController,
                    label: '手环 MAC 地址',
                    hintText: '例如 54:10:26:01:00:DF',
                  ),
                  const SizedBox(height: 12),
                  _buildDialogField(
                    controller: nameController,
                    label: '设备名称',
                    hintText: '默认 T10-WATCH',
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '支持输入 12 位十六进制 MAC，系统会自动格式化。',
                    style: TextStyle(color: AppColors.textSub, fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  if (localError != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      localError!,
                      style: const TextStyle(
                          color: Colors.redAccent, fontSize: 16),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text(
                  '取消',
                  style: TextStyle(color: AppColors.textSub, fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              TextButton(
                onPressed: () {
                  final normalizedMac = _normalizeMacInput(macController.text);
                  if (!_isValidMac(normalizedMac)) {
                    setState(() {
                      localError = '请输入正确的手环 MAC 地址';
                    });
                    return;
                  }

                  Navigator.pop(
                    dialogContext,
                    _BindDeviceResult(
                      macAddress: normalizedMac,
                      deviceName: nameController.text.trim(),
                    ),
                  );
                },
                child: const Text(
                  '确认绑定',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w900,
                    fontSize: 20,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );

    macController.dispose();
    nameController.dispose();

    if (result == null) {
      if (mounted) {
        _resumeAutoRefreshAfterBuild(provider);
      }
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
    provider.stopAutoRefresh();
    setState(() => _isBindingDevice = true);
    try {
      // Let the dialog route and its inherited-provider dependents fully unmount
      // before the bind call refreshes CareProvider.
      await WidgetsBinding.instance.endOfFrame;
      await Future<void>.delayed(const Duration(milliseconds: 180));
      if (!mounted) return;

      final success = await provider.bindSelfDevice(
        result.macAddress,
        deviceName: result.deviceName,
      );
      if (!mounted) return;

      _showOperationSnackBarAfterBuild(
        success: success,
        successMessage: '手环已成功登记并绑定',
        fallbackError: '绑定手环失败，请稍后重试',
        provider: provider,
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
    provider.stopAutoRefresh();
    setState(() => _isUnbindingDevice = true);
    try {
      await WidgetsBinding.instance.endOfFrame;
      await Future<void>.delayed(const Duration(milliseconds: 140));
      if (!mounted) return;

      final success = await provider.unbindSelfDevice();
      if (!mounted) return;

      _showOperationSnackBarAfterBuild(
        success: success,
        successMessage: '手环已成功解绑',
        fallbackError: '解绑失败，请稍后重试',
        provider: provider,
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

  void _showOperationSnackBarAfterBuild({
    required bool success,
    required String successMessage,
    required String fallbackError,
    required CareProvider provider,
  }) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _showOperationSnackBar(
        success: success,
        successMessage: successMessage,
        fallbackError: fallbackError,
        provider: provider,
      );
    });
  }

  void _showOperationSnackBar({
    required bool success,
    required String successMessage,
    required String fallbackError,
    required CareProvider provider,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          success ? successMessage : (provider.errorMessage ?? fallbackError),
          style: const TextStyle(fontSize: 18),
        ),
        backgroundColor: success ? Colors.green.shade700 : Colors.red.shade700,
      ),
    );
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
          style: const TextStyle(color: AppColors.textMain, fontSize: 18, fontWeight: FontWeight.bold),
          decoration: InputDecoration(
            hintText: hintText,
            hintStyle: const TextStyle(color: AppColors.textMuted),
            filled: true,
            fillColor: Colors.white,
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide:
                  const BorderSide(color: AppColors.border, width: 1.5),
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

  bool _isValidMac(String value) {
    final compact = value.replaceAll(':', '');
    return RegExp(r'^[0-9A-F]{12}$').hasMatch(compact);
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
