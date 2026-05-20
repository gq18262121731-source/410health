import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../audio/camera_audio_player.dart';
import '../models/camera_models.dart';
import '../repositories/camera_repository.dart';

class CameraProvider extends ChangeNotifier {
  CameraRepository _repository;

  CameraStatus? status;
  CameraStreamStatus? streamStatus;
  CameraAudioStatus? audioStatus;
  CameraDetectionRuntimeStatus? fallDetectionStatus;
  CameraDetectionRuntimeStatus? poseDetectionStatus;
  CameraFrameAnalysisStatus? frameAnalysisStatus;
  PoseDetectionLatest? poseLatest;
  CameraVideoMode videoMode = CameraVideoMode.processed;
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
  String? processedOverlayMessage;
  bool autoRefresh = false;
  bool isConnecting = false;
  bool audioListening = false;
  bool audioConnecting = false;
  bool setupLoading = false;
  bool setupTesting = false;
  bool setupSaving = false;
  bool aiAnalysisRunning = false;
  bool singleFramePoseEnabled = true;
  bool singleFrameFallEnabled = true;
  bool fallDetectionUpdating = false;
  bool poseDetectionUpdating = false;
  bool simulatingFallAlarm = false;
  DateTime? lastAiAnalysisAt;
  String? lastAiAnalysisError;
  DateTime? _lastAnalysisStartedAt;
  DateTime? _lastFallAnalysisStartedAt;
  DateTime? _lastWorkerStatusRefreshAt;
  DateTime? _lastProcessedOverlayPrimeAt;
  DateTime? _lastFrameReceivedAt;
  bool _processedOverlayPrimeInFlight = false;
  int audioLevel = 0;

  WebSocketChannel? _frameChannel;
  WebSocketChannel? _audioChannel;
  StreamSubscription<dynamic>? _frameSubscription;
  StreamSubscription<dynamic>? _audioSubscription;
  StreamSubscription<double>? _audioLevelSubscription;
  Timer? _statusTimer;
  Timer? _reconnectTimer;
  Timer? _snapshotFallbackTimer;
  bool _poseAnalysisInFlight = false;
  bool _fallAnalysisInFlight = false;
  bool _snapshotFallbackInFlight = false;
  int _fpsFrames = 0;
  bool _disposed = false;
  DateTime _fpsStartedAt = DateTime.now();
  double clientFps = 0;
  late final CameraAudioPlayer _audioPlayer;

  CameraProvider(this._repository) {
    _audioPlayer = createCameraAudioPlayer();
    _audioLevelSubscription = _audioPlayer.levels.listen((level) {
      audioLevel = level.round().clamp(0, 100);
      _notifyIfAlive();
    });
  }

  void updateRepository(CameraRepository repository) {
    if (identical(_repository, repository) || _disposed) {
      return;
    }
    _repository = repository;
    if (!autoRefresh) {
      return;
    }
    _closeFrameStream(clearFrame: true);
    if (setupConfig.sourceMode != 'local') {
      if (showingProcessedVideo) {
        unawaited(_prepareProcessedVideoAndStartStream());
      } else {
        _startFrameStream();
      }
      _ensureSnapshotFallbackTimer();
    }
    unawaited(refreshDiagnostics());
  }

  void _notifyIfAlive() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  bool get hasFrame => frameBytes != null;

  bool get showingProcessedVideo => videoMode == CameraVideoMode.processed;

  String get frameAnalysisLabel {
    if (aiAnalysisRunning) return '正在调用接口';
    if (lastAiAnalysisAt != null) {
      return '已调用 ${_formatClock(lastAiAnalysisAt!)}';
    }
    return frameAnalysisStatus?.stateLabel ?? '等待首帧';
  }

  String get streamLabel {
    if (autoRefresh && setupConfig.sourceMode == 'local') {
      return showingProcessedVideo ? '本地处理预览' : '本地原始预览';
    }
    if (!autoRefresh) return '已暂停';
    if (hasFrame) {
      return '${videoMode.shortLabel} ${clientFps.toStringAsFixed(1)} fps';
    }
    if (isConnecting) return '连接中';
    return '暂无画面';
  }

  String get processedOverlayNotice {
    if (!showingProcessedVideo) return '';
    final overlay = streamStatus?.processedOverlay;
    if (processedOverlayMessage != null &&
        (overlay == null || !overlay.hasRenderableOverlay)) {
      return processedOverlayMessage!;
    }
    if (overlay?.hasRenderableOverlay == true) {
      return overlay!.label;
    }
    if (overlay?.poseFallbackRunning == true ||
        overlay?.fallFallbackRunning == true ||
        _processedOverlayPrimeInFlight) {
      return '正在基于当前画面生成目标框和姿态骨架';
    }
    return '处理后视频使用同源画面；未检测到人体时会显示原画面并持续重试';
  }

  String get endpointLabel => status?.endpoint ?? '等待后端摄像头配置';

  String get fallDecisionNotice {
    final fall = fallDetectionStatus;
    if (fall == null) return '';
    final lead = fall.decisionStatusLabel;
    final reason = fall.decisionReasonLabel;
    if (reason.isEmpty) return lead;
    return '$lead\n$reason';
  }

  String get audioLabel {
    if (audioConnecting) return '音频连接中';
    if (!audioListening) return '音频关闭';
    if (audioLevel >= 45) return '音量较高 $audioLevel%';
    if (audioLevel >= 12) return '监听中 $audioLevel%';
    return '低音量监听';
  }

  Future<void> start() async {
    await loadSetupConfig();
    startFrameRefresh();
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
    _notifyIfAlive();
  }

  Future<void> loadSetupConfig() async {
    setupLoading = true;
    _notifyIfAlive();
    try {
      setupConfig = await _repository.getSetupConfig();
      setupMessage = null;
    } catch (error) {
      setupMessage = _formatError(error, fallback: '摄像头配置加载失败');
    } finally {
      setupLoading = false;
      _notifyIfAlive();
    }
  }

  void updateSetupConfig(CameraSetupConfig nextConfig) {
    setupConfig = nextConfig;
    setupMessage = null;
    _notifyIfAlive();
  }

  Future<void> testSetupSnapshot() async {
    if (setupConfig.sourceMode == 'local') {
      setupSnapshotBytes = null;
      setupMessage = '本地摄像头由浏览器直接预览和抽帧，不再通过后端 OpenCV 测试快照';
      _notifyIfAlive();
      return;
    }

    setupTesting = true;
    setupMessage = null;
    setupSnapshotBytes = null;
    _notifyIfAlive();
    try {
      setupSnapshotBytes = await _repository.testSetupSnapshot(setupConfig);
      setupMessage = '测试快照成功';
    } catch (error) {
      setupMessage = _formatError(error, fallback: '测试快照失败');
    } finally {
      setupTesting = false;
      _notifyIfAlive();
    }
  }

  Future<void> saveSetupConfig() async {
    setupSaving = true;
    setupMessage = null;
    _notifyIfAlive();
    try {
      setupConfig = await _repository.saveSetupConfig(setupConfig);
      setupMessage = '摄像头配置已保存';
      await refreshDiagnostics();
      if (autoRefresh) {
        _closeFrameStream(clearFrame: true);
        if (setupConfig.sourceMode != 'local') {
          if (showingProcessedVideo) {
            unawaited(_prepareProcessedVideoAndStartStream());
          } else {
            _startFrameStream();
          }
          _ensureSnapshotFallbackTimer();
        } else {
          _stopSnapshotFallbackTimer();
        }
      }
    } catch (error) {
      setupMessage = _formatError(error, fallback: '摄像头配置保存失败');
    } finally {
      setupSaving = false;
      _notifyIfAlive();
    }
  }

  Future<void> refreshDiagnostics() async {
    try {
      if (setupConfig.sourceMode == 'local') {
        final results = await Future.wait<Object>([
          _repository.getDetectionModelsStatus(),
          _repository.getFrameAnalysisStatus(),
        ]);
        final detectionModels =
            results[0] as Map<String, CameraDetectionRuntimeStatus>;
        fallDetectionStatus ??= detectionModels['fall_detection'];
        poseDetectionStatus ??= detectionModels['pose_detection'];
        frameAnalysisStatus = results[1] as CameraFrameAnalysisStatus;
        status ??= const CameraStatus(
          configured: true,
          online: true,
          source: 'browser_local_preview',
        );
        streamStatus ??= const CameraStreamStatus(
          sourceFps: 0,
          measuredFps: 0,
          clients: 1,
        );
        audioStatus ??= const CameraAudioStatus(
          configured: false,
          listenSupported: false,
          talkSupported: false,
          source: 'browser_local_preview',
        );
        _notifyIfAlive();
        return;
      }
      final results = await Future.wait<Object>([
        _repository.getStatus(),
        _repository.getStreamStatus(),
        _repository.getAudioStatus(),
        _repository.getDetectionModelsStatus(),
        _repository.getPoseDetectionLatest(),
        _repository.getFrameAnalysisStatus(),
      ]);
      status = results[0] as CameraStatus;
      streamStatus = results[1] as CameraStreamStatus;
      audioStatus = results[2] as CameraAudioStatus;
      final detectionModels =
          results[3] as Map<String, CameraDetectionRuntimeStatus>;
      fallDetectionStatus = detectionModels['fall_detection'];
      poseDetectionStatus = detectionModels['pose_detection'];
      poseLatest = results[4] as PoseDetectionLatest;
      frameAnalysisStatus = results[5] as CameraFrameAnalysisStatus;
    } catch (_) {
      // Keep the last known diagnostics so the video panel stays usable.
    }
    _notifyIfAlive();
  }

  Future<void> setFallDetectionEnabled(bool enabled) async {
    fallDetectionUpdating = true;
    singleFrameFallEnabled = enabled;
    lastAiAnalysisError = null;
    _notifyIfAlive();
    try {
      if (setupConfig.sourceMode != 'local') {
        fallDetectionStatus =
            await _repository.setFallDetectionEnabled(enabled);
      } else {
        fallDetectionStatus = CameraDetectionRuntimeStatus(
          enabled: enabled,
          running: enabled,
          processRunning: false,
          profile: 'single_frame_fall',
        );
      }
      errorMessage = null;
    } catch (error) {
      errorMessage = _formatError(error, fallback: '跌倒检测模型切换失败');
    } finally {
      fallDetectionUpdating = false;
      _notifyIfAlive();
    }
  }

  Future<void> setPoseDetectionEnabled(bool enabled) async {
    poseDetectionUpdating = true;
    singleFramePoseEnabled = enabled;
    if (!enabled) {
      poseLatest = const PoseDetectionLatest(
        backend: 'single_frame_worker',
        profile: 'browser_preview',
        frameWidth: 640,
        frameHeight: 480,
        tracks: <PoseTrack>[],
      );
    }
    lastAiAnalysisError = null;
    _notifyIfAlive();
    try {
      if (setupConfig.sourceMode != 'local') {
        poseDetectionStatus =
            await _repository.setPoseDetectionEnabled(enabled);
      } else {
        poseDetectionStatus = CameraDetectionRuntimeStatus(
          enabled: enabled,
          running: enabled,
          processRunning: false,
          profile: 'single_frame_pose',
        );
      }
      errorMessage = null;
    } catch (error) {
      errorMessage = _formatError(error, fallback: '姿态检测模型切换失败');
    } finally {
      poseDetectionUpdating = false;
      _notifyIfAlive();
    }
  }

  void startFrameRefresh() {
    if (autoRefresh) return;
    autoRefresh = true;
    if (setupConfig.sourceMode != 'local') {
      if (showingProcessedVideo) {
        unawaited(_prepareProcessedVideoAndStartStream());
      } else {
        _startFrameStream();
      }
      _ensureSnapshotFallbackTimer();
    }
    refreshDiagnostics();
    _notifyIfAlive();
  }

  Future<void> simulateFallAlarm({
    String scenario = 'critical',
  }) async {
    if (simulatingFallAlarm) return;
    simulatingFallAlarm = true;
    errorMessage = null;
    _notifyIfAlive();
    try {
      await _repository.simulateFallDetection(
        scenario: scenario,
        trackId: 'family-mobile-demo',
      );
      await refreshDiagnostics();
    } catch (error) {
      errorMessage = _formatError(error, fallback: '模拟跌倒告警失败');
    } finally {
      simulatingFallAlarm = false;
      _notifyIfAlive();
    }
  }

  void stopFrameRefresh({bool clearFrame = false}) {
    if (!autoRefresh && !isConnecting) {
      return;
    }
    autoRefresh = false;
    isConnecting = false;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _stopSnapshotFallbackTimer();
    _closeFrameStream(clearFrame: clearFrame);
    _notifyIfAlive();
  }

  Future<void> setVideoMode(CameraVideoMode mode) async {
    if (videoMode == mode) return;
    videoMode = mode;
    lastAiAnalysisError = null;
    if (!showingProcessedVideo && setupConfig.sourceMode == 'local') {
      poseLatest = null;
    }
    if (autoRefresh && setupConfig.sourceMode != 'local') {
      _closeFrameStream(clearFrame: true);
      if (showingProcessedVideo) {
        unawaited(_prepareProcessedVideoAndStartStream());
      } else {
        _startFrameStream();
      }
      _ensureSnapshotFallbackTimer();
    }
    _notifyIfAlive();
  }

  Future<void> _prepareProcessedVideoAndStartStream() async {
    await _ensureProcessedVideoModels();
    if (autoRefresh && setupConfig.sourceMode != 'local') {
      _startFrameStream();
    }
    unawaited(_primeProcessedOverlayIfNeeded(force: true));
  }

  Future<void> _ensureProcessedVideoModels() async {
    try {
      final statuses = await _repository.setDetectionModelsEnabled(
        poseDetectionEnabled: true,
        fallDetectionEnabled: true,
      );
      poseDetectionStatus = statuses['pose_detection'];
      fallDetectionStatus = statuses['fall_detection'];
      errorMessage = null;
      _notifyIfAlive();
    } catch (error) {
      errorMessage = _formatError(error, fallback: '处理后视频模型启动失败');
      _notifyIfAlive();
    }
  }

  Future<void> _primeProcessedOverlayIfNeeded({bool force = false}) async {
    if (!showingProcessedVideo ||
        setupConfig.sourceMode == 'local' ||
        _processedOverlayPrimeInFlight) {
      return;
    }
    final now = DateTime.now();
    final lastPrime = _lastProcessedOverlayPrimeAt;
    if (!force &&
        lastPrime != null &&
        now.difference(lastPrime).inSeconds < 8) {
      return;
    }
    _processedOverlayPrimeInFlight = true;
    processedOverlayMessage = '正在生成处理后标注...';
    _notifyIfAlive();
    try {
      final result = await _repository.primeProcessedOverlay(includeFall: true);
      _lastProcessedOverlayPrimeAt = DateTime.now();
      final tracks = result['pose_tracks'];
      final poseTracks = tracks is num ? tracks.toInt() : 0;
      final poseSeeded = result['pose_seeded'] == true;
      final fallSeeded = result['fall_seeded'] == true;
      if (poseSeeded || fallSeeded) {
        processedOverlayMessage = poseSeeded
            ? '处理后标注已生成：骨架 $poseTracks 个'
            : '处理后标注已生成：跌倒框';
      } else {
        processedOverlayMessage = '当前帧未检测到可绘制目标，处理流会继续刷新';
      }
      errorMessage = null;
      await refreshDiagnostics();
    } catch (error) {
      processedOverlayMessage = _formatError(error, fallback: '处理后标注预热失败');
    } finally {
      _processedOverlayPrimeInFlight = false;
      _notifyIfAlive();
    }
  }

  Future<void> analyzeBrowserFrame(Uint8List imageBytes) async {
    final now = DateTime.now();
    if (!autoRefresh ||
        !showingProcessedVideo ||
        imageBytes.isEmpty ||
        (!singleFramePoseEnabled && !singleFrameFallEnabled) ||
        (_lastAnalysisStartedAt != null &&
            now.difference(_lastAnalysisStartedAt!).inMilliseconds < 800)) {
      return;
    }
    _lastAnalysisStartedAt = now;
    final shouldRunPose = singleFramePoseEnabled && !_poseAnalysisInFlight;
    if (shouldRunPose) {
      unawaited(_analyzePoseFrame(imageBytes));
    }
    final shouldRunFall = singleFrameFallEnabled &&
        !_fallAnalysisInFlight &&
        (_lastFallAnalysisStartedAt == null ||
            now.difference(_lastFallAnalysisStartedAt!).inSeconds >= 6);
    if (shouldRunFall) {
      _lastFallAnalysisStartedAt = now;
      unawaited(_analyzeFallFrame(imageBytes));
    }
  }

  Future<void> _analyzePoseFrame(Uint8List imageBytes) async {
    if (_poseAnalysisInFlight) return;
    _poseAnalysisInFlight = true;
    lastAiAnalysisError = null;
    try {
      final result = await _repository.analyzePoseFrame(imageBytes);
      if (result['ok'] == false && result['error'] != null) {
        lastAiAnalysisError = result['error'].toString();
      }
      final latest = result['pose_latest'];
      if (latest is Map) {
        poseLatest = PoseDetectionLatest.fromJson(
          Map<String, dynamic>.from(latest),
        );
      }
      poseDetectionStatus = const CameraDetectionRuntimeStatus(
        enabled: true,
        running: true,
        processRunning: false,
        profile: 'single_frame_pose',
      );
      lastAiAnalysisAt = DateTime.now();
      errorMessage = null;
    } catch (error) {
      lastAiAnalysisError = _formatError(error, fallback: '姿态单帧分析失败');
      errorMessage = lastAiAnalysisError;
    } finally {
      _poseAnalysisInFlight = false;
      await _refreshFrameAnalysisStatusIfNeeded();
      _notifyIfAlive();
    }
  }

  Future<void> _analyzeFallFrame(Uint8List imageBytes) async {
    if (_fallAnalysisInFlight) return;
    _fallAnalysisInFlight = true;
    try {
      final result = await _repository.analyzeFallFrame(imageBytes);
      final fall = result['fall'];
      if (fall is Map) {
        final fallResult = Map<String, dynamic>.from(fall);
        fallDetectionStatus = CameraDetectionRuntimeStatus(
          enabled: true,
          running: true,
          processRunning: false,
          profile: 'single_frame_fall',
          lastEvent: fallResult['fall_result'] is Map
              ? Map<String, dynamic>.from(fallResult['fall_result'] as Map)
              : fallResult,
          multimodalReview: result['multimodal_review'] is Map
              ? Map<String, dynamic>.from(result['multimodal_review'] as Map)
              : null,
          lastError: fallResult['error']?.toString(),
        );
      }
    } catch (error) {
      lastAiAnalysisError = _formatError(error, fallback: '跌倒单帧分析失败');
    } finally {
      _fallAnalysisInFlight = false;
      await _refreshFrameAnalysisStatusIfNeeded();
      _notifyIfAlive();
    }
  }

  Future<void> _refreshFrameAnalysisStatusIfNeeded() async {
    final now = DateTime.now();
    final lastRefresh = _lastWorkerStatusRefreshAt;
    if (lastRefresh != null && now.difference(lastRefresh).inSeconds < 3) {
      return;
    }
    _lastWorkerStatusRefreshAt = now;
    await _refreshFrameAnalysisStatus();
  }

  Future<void> _refreshFrameAnalysisStatus() async {
    try {
      frameAnalysisStatus = await _repository.getFrameAnalysisStatus();
    } catch (_) {
      // Keep last worker status; analysis errors are surfaced separately.
    }
  }

  Future<void> startPtz(String direction) async {
    activeDirection = direction;
    _notifyIfAlive();
    try {
      await _repository.moveCamera(direction);
    } catch (error) {
      errorMessage = _formatError(error, fallback: '云台控制失败');
      activeDirection = null;
      _notifyIfAlive();
    }
  }

  Future<void> stopPtz() async {
    activeDirection = null;
    _notifyIfAlive();
    try {
      await _repository.moveCamera('stop');
    } catch (error) {
      errorMessage = _formatError(error, fallback: '云台停止失败');
      _notifyIfAlive();
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
    _notifyIfAlive();

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
      _notifyIfAlive();
    } catch (error) {
      audioNotice = _formatError(error, fallback: '音频监听启动失败');
      await stopAudioListen();
      _notifyIfAlive();
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
    _notifyIfAlive();
  }

  void _startFrameStream() {
    if (_disposed) {
      return;
    }
    if (!autoRefresh ||
        setupConfig.sourceMode == 'local' ||
        _frameChannel != null) {
      return;
    }
    isConnecting = true;
    errorMessage = null;
    _notifyIfAlive();

    try {
      _frameChannel = _repository.connectFrameStream(mode: videoMode);
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
    _lastFrameReceivedAt = DateTime.now();
    isConnecting = false;
    errorMessage = null;
    if (showingProcessedVideo) {
      unawaited(_primeProcessedOverlayIfNeeded());
    }
    _recordFrame();
    _notifyIfAlive();
  }

  void _ensureSnapshotFallbackTimer() {
    if (_snapshotFallbackTimer != null || setupConfig.sourceMode == 'local') {
      return;
    }
    _snapshotFallbackTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => unawaited(_refreshSnapshotFallbackIfNeeded()),
    );
  }

  Future<void> _refreshSnapshotFallbackIfNeeded({bool force = false}) async {
    if (!autoRefresh ||
        setupConfig.sourceMode == 'local' ||
        _snapshotFallbackInFlight) {
      return;
    }
    final now = DateTime.now();
    final lastFrame = _lastFrameReceivedAt;
    final secondsSinceFrame =
        lastFrame == null ? 999 : now.difference(lastFrame).inSeconds;
    final streamFps = streamStatus?.displayFps ?? 0;
    final shouldRefresh =
        force || secondsSinceFrame >= 5 || clientFps < 1.0 || streamFps < 2.0;
    if (!shouldRefresh) return;

    _snapshotFallbackInFlight = true;
    try {
      final bytes = await _repository.getCurrentFrameSnapshot(mode: videoMode);
      if (bytes.isEmpty) return;
      frameBytes = bytes;
      _lastFrameReceivedAt = DateTime.now();
      isConnecting = false;
      errorMessage = null;
      _recordFrame();
      _notifyIfAlive();
    } catch (error) {
      if (lastFrame == null || secondsSinceFrame >= 10) {
        errorMessage = _formatError(error, fallback: '摄像头自动刷新失败');
        _notifyIfAlive();
      }
    } finally {
      _snapshotFallbackInFlight = false;
    }
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
    if (_disposed) {
      return;
    }
    _closeFrameStream(clearFrame: false);
    if (!autoRefresh || setupConfig.sourceMode == 'local') {
      return;
    }
    isConnecting = true;
    _notifyIfAlive();
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

  void _stopSnapshotFallbackTimer() {
    _snapshotFallbackTimer?.cancel();
    _snapshotFallbackTimer = null;
    _snapshotFallbackInFlight = false;
  }

  String _formatError(Object error, {required String fallback}) {
    final message = error.toString().trim();
    if (message.isEmpty) return fallback;
    return message.replaceFirst('Exception: ', '');
  }

  static String _formatClock(DateTime time) {
    final hour = time.hour.toString().padLeft(2, '0');
    final minute = time.minute.toString().padLeft(2, '0');
    final second = time.second.toString().padLeft(2, '0');
    return '$hour:$minute:$second';
  }

  @override
  void dispose() {
    _disposed = true;
    _statusTimer?.cancel();
    _audioLevelSubscription?.cancel();
    if (activeDirection != null) {
      _repository.moveCamera('stop').catchError((_) {});
    }
    _audioSubscription?.cancel();
    _audioChannel?.sink.close();
    _audioPlayer.dispose();
    _stopSnapshotFallbackTimer();
    _closeFrameStream();
    super.dispose();
  }
}
