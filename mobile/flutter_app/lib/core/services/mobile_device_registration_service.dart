import '../../features/auth/repositories/auth_repository.dart';
import '../../features/session/services/session_manager.dart';
import 'app_notification_service.dart';

class MobileDeviceRegistrationService {
  final AuthRepository _authRepository;
  final SessionManager _sessionManager;
  final AppNotificationService _notificationService;

  MobileDeviceRegistrationService(
    this._authRepository,
    this._sessionManager,
    this._notificationService,
  );

  String get installationId => _sessionManager.getOrCreateInstallationId();

  Future<void> syncCurrentInstallation() async {
    try {
      final snapshot = await _notificationService.registrationSnapshot();
      final currentInstallationId = installationId;
      await _authRepository.registerMobileDevice({
        'installation_id': currentInstallationId,
        'provider': 'local',
        'platform': snapshot.platform,
        'push_token': 'local-installation::$currentInstallationId',
        'notifications_enabled': snapshot.notificationsEnabled,
        'remote_push_ready': snapshot.remotePushReady,
        'app_version': '0.1.0+1',
        'metadata': {
          'integration_stage': 'local-notification-ready',
          'supports_remote_push': false,
        },
      });
    } catch (_) {}
  }

  Future<void> revokeCurrentInstallation() async {
    try {
      await _authRepository.revokeMobileDevice(installationId);
    } catch (_) {}
  }
}
