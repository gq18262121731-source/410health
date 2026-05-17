import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../../../core/network/server_endpoint_config.dart';
import '../../../core/theme/app_colors.dart';
import '../../../widgets/logout_action.dart';
import '../../alarm/providers/alarm_provider.dart';
import '../../care/providers/care_provider.dart';

class ServerSettingsScreen extends StatefulWidget {
  const ServerSettingsScreen({super.key});

  @override
  State<ServerSettingsScreen> createState() => _ServerSettingsScreenState();
}

class _ServerSettingsScreenState extends State<ServerSettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _hostController;
  late final TextEditingController _portController;

  String _scheme = 'http';
  bool _isTesting = false;
  bool _isSaving = false;
  String? _testResult;
  bool _lastTestPassed = false;

  static const _recommendedLanHost = '192.168.8.252';

  @override
  void initState() {
    super.initState();
    final config = context.read<ServerEndpointConfig>();
    _hostController = TextEditingController(text: config.host);
    _portController = TextEditingController(text: config.port.toString());
    _scheme = config.scheme;
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    super.dispose();
  }

  bool get _isAndroidRealDeviceMode => true;

  String? _validateHost(String? value) {
    final host = value?.trim() ?? '';
    final port = int.tryParse(_portController.text) ?? 0;
    return ServerEndpointConfig.validateEndpoint(
      host: host,
      port: port,
      isAndroidRealDeviceMode: _isAndroidRealDeviceMode,
    );
  }

  String? _validatePort(String? value) {
    final host = _hostController.text.trim();
    final port = int.tryParse(value ?? '') ?? -1;
    return ServerEndpointConfig.validateEndpoint(
      host: host,
      port: port,
      isAndroidRealDeviceMode: _isAndroidRealDeviceMode,
    );
  }

  Future<void> _testConnection() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isTesting = true;
      _testResult = null;
      _lastTestPassed = false;
    });

    final config = context.read<ServerEndpointConfig>();
    final error = await config.testConnection(
      host: _hostController.text,
      port: int.parse(_portController.text),
      scheme: _scheme,
      isAndroidRealDeviceMode: _isAndroidRealDeviceMode,
    );

    if (!mounted) {
      return;
    }

    setState(() {
      _isTesting = false;
      _lastTestPassed = error == null;
      _testResult = error ?? '连接成功，后端健康检查通过。';
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isSaving = true;
      _testResult = null;
      _lastTestPassed = false;
    });

    final config = context.read<ServerEndpointConfig>();
    final careProvider = context.read<CareProvider>();
    final alarmProvider = context.read<AlarmProvider>();
    final error = await config.testConnection(
      host: _hostController.text,
      port: int.parse(_portController.text),
      scheme: _scheme,
      isAndroidRealDeviceMode: _isAndroidRealDeviceMode,
    );

    if (error != null) {
      if (!mounted) {
        return;
      }
      setState(() {
        _isSaving = false;
        _testResult = error;
      });
      return;
    }

    careProvider.stopAutoRefresh();

    await config.save(
      host: _hostController.text,
      port: int.parse(_portController.text),
      scheme: _scheme,
    );

    if (!mounted) {
      return;
    }

    setState(() {
      _isSaving = false;
      _lastTestPassed = true;
      _testResult = '连接成功，已切换到 ${config.origin}';
    });

    Navigator.of(context).pop();
    Future<void>.delayed(const Duration(milliseconds: 160), () async {
      careProvider.stopAutoRefresh();
      await careProvider.fetchProfile(silent: true);
      await alarmProvider.reloadFromEndpointChange();
    });
  }

  void _applyRecommendedLanAddress() {
    _hostController.text = _recommendedLanHost;
    _portController.text = '8000';
    setState(() {
      _scheme = 'http';
      _testResult = null;
      _lastTestPassed = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final config = context.watch<ServerEndpointConfig>();
    final warning = config.getCurrentEndpointWarning(
      isAndroidRealDeviceMode: _isAndroidRealDeviceMode,
    );

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text(
          '服务器设置',
          style: TextStyle(color: AppColors.textMain, fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textMain),
        actions: const [LogoutAction()],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildInfoCard(config),
              if (warning != null) ...[
                const SizedBox(height: 12),
                _buildWarningCard(warning),
              ],
              const SizedBox(height: 16),
              _buildRecommendationCard(),
              const SizedBox(height: 16),
              _buildFieldLabel('协议'),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _scheme,
                dropdownColor: AppColors.surface,
                decoration: _inputDecoration(),
                items: const [
                  DropdownMenuItem(value: 'http', child: Text('HTTP')),
                  DropdownMenuItem(value: 'https', child: Text('HTTPS')),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _scheme = value;
                  });
                },
              ),
              const SizedBox(height: 16),
              _buildFieldLabel('服务器 IP / 域名'),
              const SizedBox(height: 8),
              TextFormField(
                controller: _hostController,
                style: const TextStyle(color: AppColors.textMain, fontWeight: FontWeight.bold),
                decoration: _inputDecoration(hintText: '例如 192.168.8.252'),
                validator: _validateHost,
              ),
              const SizedBox(height: 16),
              _buildFieldLabel('端口'),
              const SizedBox(height: 8),
              TextFormField(
                controller: _portController,
                style: const TextStyle(color: AppColors.textMain, fontWeight: FontWeight.bold),
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: _inputDecoration(hintText: '8000'),
                validator: _validatePort,
              ),
              const SizedBox(height: 12),
              const Text(
                '移动端只能连接后端服务。请填写运行后端那台电脑的局域网 IP 和 8000 端口，不要填写 5173、5182、7860 或 8090。',
                style: TextStyle(color: AppColors.textSub, height: 1.5),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _isTesting || _isSaving ? null : _testConnection,
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: AppColors.primary),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: _isTesting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('测试连接'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _isSaving || _isTesting ? null : _save,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2563EB),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: _isSaving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('保存并应用'),
                    ),
                  ),
                ],
              ),
              if (_testResult != null) ...[
                const SizedBox(height: 16),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _lastTestPassed
                        ? Colors.green.withValues(alpha: 0.12)
                        : Colors.orange.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _lastTestPassed ? AppColors.success : AppColors.warning,
                    ),
                  ),
                  child: Text(
                    _testResult!,
                    style: const TextStyle(color: AppColors.textMain),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInfoCard(ServerEndpointConfig config) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
        boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 2))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '当前后端地址',
            style: TextStyle(color: AppColors.textMain, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            config.origin,
            style: const TextStyle(color: AppColors.primary, fontSize: 15, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          const Text(
            'Android 真机接入同一局域网时，这里应填写运行后端服务那台电脑的局域网 IP 和 8000 端口。',
            style: TextStyle(color: AppColors.textSub, height: 1.5),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '推荐真机地址',
            style: TextStyle(color: AppColors.textMain, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            'http://$_recommendedLanHost:8000',
            style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            '如果你当前连接的是这台电脑所在的同一 Wi‑Fi，优先使用上面的地址。',
            style: TextStyle(color: AppColors.textSub, height: 1.5),
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _applyRecommendedLanAddress,
            child: const Text('一键填入推荐地址'),
          ),
        ],
      ),
    );
  }

  Widget _buildWarningCard(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.warning),
      ),
      child: Text(
        message,
        style: const TextStyle(color: AppColors.textMain, height: 1.45),
      ),
    );
  }

  Widget _buildFieldLabel(String label) {
    return Text(
      label,
      style: const TextStyle(color: AppColors.textMain, fontWeight: FontWeight.w600),
    );
  }

  InputDecoration _inputDecoration({String? hintText}) {
    return InputDecoration(
      hintText: hintText,
      hintStyle: const TextStyle(color: AppColors.textMuted),
      filled: true,
      fillColor: AppColors.surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.primary, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.error),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.error, width: 2),
      ),
    );
  }
}
