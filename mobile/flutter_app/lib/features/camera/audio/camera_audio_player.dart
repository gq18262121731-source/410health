import 'camera_audio_player_base.dart';
import 'camera_audio_player_soloud.dart';

export 'camera_audio_player_base.dart';

CameraAudioPlayer createCameraAudioPlayer() {
  return SoLoudCameraAudioPlayer();
}
