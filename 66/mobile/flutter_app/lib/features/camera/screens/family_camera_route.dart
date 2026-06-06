import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../care/providers/care_provider.dart';
import '../providers/camera_provider.dart';
import 'family_camera_screen.dart';

/// Owns the camera provider for the camera page.
///
/// Keeping this lifecycle in a dedicated route widget is more robust than
/// creating the provider inline inside `MaterialPageRoute.builder`, especially
/// on Android devices where route transitions, dialogs, and provider teardown
/// can overlap.
class FamilyCameraRoute extends StatefulWidget {
  const FamilyCameraRoute({super.key});

  @override
  State<FamilyCameraRoute> createState() => _FamilyCameraRouteState();
}

class _FamilyCameraRouteState extends State<FamilyCameraRoute> {
  CameraProvider? _cameraProvider;
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _cameraProvider ??= context.read<CameraProvider>();
    final careProfile = context.read<CareProvider>().profile;
    final preferredCameraId = careProfile?.relatedCameraIds.isNotEmpty == true
        ? careProfile!.relatedCameraIds.first
        : null;
    _cameraProvider?.setPreferredCameraId(preferredCameraId);
    if (!_started) {
      _started = true;
      _cameraProvider?.start();
    }
  }

  @override
  void dispose() {
    _cameraProvider?.stopFrameRefresh();
    _cameraProvider?.setPreferredCameraId(null);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return const FamilyCameraScreen();
  }
}
