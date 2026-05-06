import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/network/server_endpoint_config.dart';
import '../../../core/theme/app_colors.dart';
import '../../../widgets/logout_action.dart';

class CommunityMobileNoticeScreen extends StatelessWidget {
  const CommunityMobileNoticeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final serverConfig = context.watch<ServerEndpointConfig>();

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text(
          '社区移动端说明',
          style: TextStyle(
            color: AppColors.textMain,
            fontSize: 22,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: const [LogoutAction()],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: AppColors.border),
                boxShadow: const [
                  BoxShadow(
                    color: Color(0x14000000),
                    blurRadius: 16,
                    offset: Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: const Icon(
                      Icons.desktop_windows_rounded,
                      color: AppColors.primary,
                      size: 34,
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    '当前社区角色建议使用 Web 大屏',
                    style: TextStyle(
                      color: AppColors.textMain,
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '为了保证稳定性，移动端暂不开放社区运营首页。社区账号登录后，请优先使用电脑访问社区工作台，以获得完整的总览、告警、成员设备与摄像头能力。',
                    style: TextStyle(
                      color: AppColors.textSub,
                      fontSize: 16,
                      height: 1.7,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF8FAFC),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '建议访问地址',
                          style: TextStyle(
                            color: AppColors.textMain,
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        SelectableText(
                          '${serverConfig.origin}/#/overview',
                          style: const TextStyle(
                            color: AppColors.primary,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    '移动端当前仍可保留登录态，但不会自动拉起社区告警监听或推送注册，避免出现角色错配和误提醒。',
                    style: TextStyle(
                      color: AppColors.textSub,
                      fontSize: 15,
                      height: 1.7,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
