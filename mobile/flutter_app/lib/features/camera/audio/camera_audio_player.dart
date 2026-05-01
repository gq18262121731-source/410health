import 'camera_audio_player_base.dart';
import 'camera_audio_player_stub.dart'
    if (dart.library.html) 'camera_audio_player_web.dart' as platform;

export 'camera_audio_player_base.dart';

CameraAudioPlayer createCameraAudioPlayer() {
  return platform.createCameraAudioPlayer();
}
