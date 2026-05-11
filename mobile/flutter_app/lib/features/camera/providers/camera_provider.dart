import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../audio/camera_audio_player.dart';
import '../models/camera_models.dart';
import '../repositories/camera_repository.dart';

class CameraProvider extends ChangeNotifier {
  final CameraRepository _repository;

  CameraStatus? status;
  CameraStreamStatus? streamStatus;
  CameraAudioStatus? audioStatus;
  CameraSetupConfig setupConfig = const CameraSetupConfig(
    sourceMode: 'local',
    localIndex: 0,
    localBackend: 'any',
    ip: '',
    user: 'admin',
    password: '',
    rtspPort: 10554,
    rtspPath: '/tcp/av0_0',
    streamRtspPath: '/tcp/av0_1',
    audioRtspPath: '/tcp/av0_1',
    onvifPort: 10080,
  );
  Uint8List? setupSnapshotBytes;
  Uint8List? frameBytes;
  String? errorMessage;
  String? audioNotice;
  String? setupMessage;
  String? activeDirection;
  bool autoRefresh = false;
  bool isConnecting = false;
  bool audioListening = false;
  bool audioConnecting = false;
  bool setupLoading = false;
  bool setupTesting = false;
  bool setupSaving = false;
  int audioLevel = 0;

  WebSocketChannel? _frameChannel;
  WebSocketChannel? _audioChannel;
  StreamSubscription<dynamic>? _frameSubscription;
  StreamSubscription<dynamic>? _audioSubscription;
  StreamSubscription<double>? _audioLevelSubscription;
  Timer? _statusTimer;
  Timer? _reconnectTimer;
  int _fpsFrames = 0;
  DateTime _fpsStartedAt = DateTime.now();
  double clientFps = 0;
  late final CameraAudioPlayer _audioPlayer;

  CameraProvider(this._repository) {
    _audioPlayer = createCameraAudioPlayer();
    _audioLevelSubscription = _audioPlayer.levels.listen((level) {
      audioLevel = level.round().clamp(0, 100);
      notifyListeners();
    });
  }

  bool get hasFrame => frameBytes != null;

  String get streamLabel {
    if (!autoRefresh) return '已暂停';
    if (hasFrame) return '实时 ${clientFps.toStringAsFixed(1)} fps';
    if (isConnecting) return '连接中';
    return '暂无画面';
  }

  String get endpointLabel => status?.endpoint ?? '等待后端摄像头配置';

  String get audioLabel {
    if (audioConnecting) return '音频连接中';
    if (!audioListening) return '音频关闭';
    if (audioLevel >= 45) return '音量较高 $audioLevel%';
    if (audioLevel >= 12) return '监听中 $audioLevel%';
    return '低音量监听';
  }

  Future<void> start() async {
    await loadSetupConfig();
    await refreshStatus();
    _statusTimer?.cancel();
    _statusTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      refreshDiagnostics();
    });
  }

  Future<void> refreshStatus() async {
    try {
      status = await _repository.getStatus();
      if (status?.online == true) {
        errorMessage = null;
      } else if (status?.error != null) {
        errorMessage = status!.error;
      }
    } catch (error) {
      errorMessage = _formatError(error, fallback: '摄像头状态加载失败');
    }
    notifyListeners();
  }

  Future<void> loadSetupConfig() async {
    setupLoading = true;
    notifyListeners();
    try {
      setupConfig = await _repository.getSetupConfig();
      setupMessage = null;
    } catch (error) {
      setupMessage = _formatError(error, fallback: '摄像头配置加载失败');
    } finally {
      setupLoading = false;
      notifyListeners();
    }
  }

  void updateSetupConfig(CameraSetupConfig nextConfig) {
    setupConfig = nextConfig;
    setupMessage = null;
    notifyListeners();
  }

  Future<void> testSetupSnapshot() async {
    setupTesting = true;
    setupMessage = null;
    setupSnapshotBytes = null;
    notifyListeners();
    try {
      setupSnapshotBytes = await _repository.testSetupSnapshot(setupConfig);
      setupMessage = '测试快照成功';
    } catch (error) {
      setupMessage = _formatError(error, fallback: '测试快照失败');
    } finally {
      setupTesting = false;
      notifyListeners();
    }
  }

  Future<void> saveSetupConfig() async {
    setupSaving = true;
    setupMessage = null;
    notifyListeners();
    try {
      setupConfig = await _repository.saveSetupConfig(setupConfig);
      setupMessage = '摄像头配置已保存';
      await refreshDiagnostics();
      if (autoRefresh) {
        _closeFrameStream(clearFrame: true);
        _startFrameStream();
      }
    } catch (error) {
      setupMessage = _formatError(error, fallback: '摄像头配置保存失败');
    } finally {
      setupSaving = false;
      notifyListeners();
    }
  }

  Future<void> refreshDiagnostics() async {
    try {
      final results = await Future.wait<Object>([
        _repository.getStatus(),
        _repository.getStreamStatus(),
        _repository.getAudioStatus(),
      ]);
      status = results[0] as CameraStatus;
      streamStatus = results[1] as CameraStreamStatus;
      audioStatus = results[2] as CameraAudioStatus;
    } catch (_) {
      // Keep the last known diagnostics so the video panel stays usable.
    }
    notifyListeners();
  }

  void toggleFrameRefresh() {
    if (autoRefresh) {
      autoRefresh = false;
      _closeFrameStream();
    } else {
      autoRefresh = true;
      _startFrameStream();
    }
    notifyListeners();
  }

  Future<void> startPtz(String direction) async {
    activeDirection = direction;
    notifyListeners();
    try {
      await _repository.moveCamera(direction);
    } catch (error) {
      errorMessage = _formatError(error, fallback: '云台控制失败');
      activeDirection = null;
      notifyListeners();
    }
  }

  Future<void> stopPtz() async {
    activeDirection = null;
    notifyListeners();
    try {
      await _repository.moveCamera('stop');
    } catch (error) {
      errorMessage = _formatError(error, fallback: '云台停止失败');
      notifyListeners();
    }
  }

  Future<void> toggleAudioListen() async {
    if (audioListening || audioConnecting) {
      await stopAudioListen(notice: '已停止音频监听');
      return;
    }
    await startAudioListen();
  }

  Future<void> startAudioListen() async {
    audioConnecting = true;
    audioNotice = '正在连接摄像头环境音...';
    notifyListeners();

    try {
      final latestStatus = await _repository.getAudioStatus();
      audioStatus = latestStatus;
      if (!latestStatus.listenSupported) {
        throw Exception(latestStatus.error ?? '当前摄像头没有可监听的音频轨道。');
      }
      if (!_audioPlayer.isSupported) {
        throw Exception(_audioPlayer.unsupportedReason ?? '当前平台不支持音频播放。');
      }

      await _audioPlayer.start(sampleRate: latestStatus.sampleRate ?? 8000);
      _audioChannel = _repository.connectAudioListenStream();
      _audioSubscription = _audioChannel!.stream.listen(
        _handleAudioFrame,
        onError: (Object error) {
          audioNotice = _formatError(error, fallback: '音频监听失败');
          stopAudioListen();
        },
        onDone: () {
          if (audioListening || audioConnecting) {
            audioNotice = '音频监听连接已关闭。';
          }
          stopAudioListen();
        },
      );

      audioListening = true;
      audioConnecting = false;
      final codec = latestStatus.audioCodec ?? 'PCM';
      final rate = latestStatus.sampleRate ?? 8000;
      audioNotice = '音频监听中：$codec / ${rate}Hz';
      notifyListeners();
    } catch (error) {
      audioNotice = _formatError(error, fallback: '音频监听启动失败');
      await stopAudioListen();
      notifyListeners();
    }
  }

  Future<void> stopAudioListen({String? notice}) async {
    await _audioSubscription?.cancel();
    _audioSubscription = null;
    await _audioChannel?.sink.close();
    _audioChannel = null;
    await _audioPlayer.stop();
    audioListening = false;
    audioConnecting = false;
    audioLevel = 0;
    if (notice != null) {
      audioNotice = notice;
    }
    notifyListeners();
  }

  void _startFrameStream() {
    if (!autoRefresh || _frameChannel != null) {
      return;
    }
    isConnecting = true;
    errorMessage = null;
    notifyListeners();

    try {
      _frameChannel = _repository.connectFrameStream();
      _frameSubscription = _frameChannel!.stream.listen(
        _handleFrame,
        onError: (Object error) {
          errorMessage = _formatError(error, fallback: '视频连接失败');
          _scheduleReconnect();
        },
        onDone: _scheduleReconnect,
      );
    } catch (error) {
      errorMessage = _formatError(error, fallback: '视频连接失败');
      _scheduleReconnect();
    }
  }

  void _handleFrame(dynamic data) {
    Uint8List? bytes;
    if (data is Uint8List) {
      bytes = data;
    } else if (data is List<int>) {
      bytes = Uint8List.fromList(data);
    }

    if (bytes == null || bytes.isEmpty) {
      return;
    }
    frameBytes = bytes;
    isConnecting = false;
    errorMessage = null;
    _recordFrame();
    notifyListeners();
  }

  void _handleAudioFrame(dynamic data) {
    Uint8List? bytes;
    if (data is Uint8List) {
      bytes = data;
    } else if (data is List<int>) {
      bytes = Uint8List.fromList(data);
    }
    if (bytes == null || bytes.isEmpty) {
      return;
    }
    _audioPlayer.playPcm16(bytes);
  }

  void _recordFrame() {
    _fpsFrames += 1;
    final now = DateTime.now();
    final elapsed = now.difference(_fpsStartedAt).inMilliseconds / 1000;
    if (elapsed >= 2) {
      clientFps = _fpsFrames / elapsed;
      _fpsFrames = 0;
      _fpsStartedAt = now;
    }
  }

  void _scheduleReconnect() {
    _closeFrameStream(clearFrame: false);
    if (!autoRefresh) {
      return;
    }
    isConnecting = true;
    notifyListeners();
    _reconnectTimer?.cancel();
    _reconnectTimer =
        Timer(const Duration(milliseconds: 1200), _startFrameStream);
  }

  void _closeFrameStream({bool clearFrame = false}) {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _frameSubscription?.cancel();
    _frameSubscription = null;
    _frameChannel?.sink.close();
    _frameChannel = null;
    isConnecting = false;
    if (clearFrame) {
      frameBytes = null;
    }
  }

  String _formatError(Object error, {required String fallback}) {
    final message = error.toString().trim();
    if (message.isEmpty) return fallback;
    return message.replaceFirst('Exception: ', '');
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    _audioLevelSubscription?.cancel();
    if (activeDirection != null) {
      _repository.moveCamera('stop').catchError((_) {});
    }
    _audioSubscription?.cancel();
    _audioChannel?.sink.close();
    _audioPlayer.dispose();
    _closeFrameStream();
    super.dispose();
  }
}
