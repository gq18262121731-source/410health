<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Camera,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Move,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Volume2,
  VolumeX,
} from "lucide-vue-next";
import {
  api,
  type CameraAudioStatusResponse,
  type CameraAudioStreamStatusResponse,
  type CameraFallDetectionStatusResponse,
  type CameraPoseDetectionConfigResponse,
  type CameraPoseDetectionStatusResponse,
  type CameraPtzDirection,
  type CameraStatusResponse,
  type CameraStreamStatusResponse,
  type AlarmRecord,
  type ExternalCameraFallDetectResponse,
  type ExternalCameraHealthResponse,
  type TargetUserRecord,
} from "../api/client";
import { PcmAudioPlayer, type PcmAudioPlayerState } from "../utils/pcmAudioPlayer";

type CameraViewMode = "live" | "fall" | "pose";
type FallSafetyTone = "safe" | "review" | "danger" | "offline";

const status = ref<CameraStatusResponse | null>(null);
const streamStatus = ref<CameraStreamStatusResponse | null>(null);
const audioStatus = ref<CameraAudioStatusResponse | null>(null);
const audioStreamStatus = ref<CameraAudioStreamStatusResponse | null>(null);
const fallStatus = ref<CameraFallDetectionStatusResponse | null>(null);
const poseStatus = ref<CameraPoseDetectionStatusResponse | null>(null);
const poseConfig = ref<CameraPoseDetectionConfigResponse | null>(null);
const frameCanvas = ref<HTMLCanvasElement | null>(null);
const hasFrame = ref(false);
const loadingStatus = ref(false);
const autoRefresh = ref(true);
const streamState = ref<"connecting" | "live" | "paused" | "offline">("connecting");
const clientFps = ref(0);
const mjpegFallback = ref(true);
const mjpegStreamSrc = ref("");
const activePtz = ref<CameraPtzDirection | null>(null);
const errorMessage = ref("");
const audioNotice = ref("");
const audioListening = ref(false);
const audioConnecting = ref(false);
const audioDesired = ref(false);
const audioLevel = ref(0);
const audioQueuedMs = ref(0);
const audioDroppedBacklog = ref(0);
const targetUsers = ref<TargetUserRecord[]>([]);
const externalCameraHealth = ref<ExternalCameraHealthResponse | null>(null);
const externalCameraResult = ref<ExternalCameraFallDetectResponse | null>(null);
const activeAlarms = ref<AlarmRecord[]>([]);
const cameraViewMode = ref<CameraViewMode>("live");
const externalCameraBusy = ref(false);
const poseBusy = ref(false);
const acknowledgingFall = ref(false);
const lastStatusErrorAt = ref(0);
const streamFailureCount = ref(0);
let statusTimer: number | undefined;
let streamStatusTimer: number | undefined;
let frameSocket: WebSocket | undefined;
let audioSocket: WebSocket | undefined;
let frameWatchdog: number | undefined;
let audioReconnectTimer: number | undefined;
let pendingFrame: Blob | undefined;
let renderingFrame = false;
let renderRequest: number | undefined;
let clientFpsStartedAt = performance.now();
let clientFpsFrames = 0;
let ptzStopTimer: number | undefined;
let pausedForVisibility = false;
let intentionalFrameSocketClose: WebSocket | undefined;
let audioPlayer: PcmAudioPlayer | undefined;
let removeAudioStateListener: (() => void) | undefined;

const primaryStreamTransport =
  (import.meta.env.VITE_CAMERA_PRIMARY_TRANSPORT === "websocket" ? "websocket" : "mjpeg") as "websocket" | "mjpeg";

const statusLabel = computed(() => {
  if (!status.value?.configured) return "未配置";
  if (status.value.online) return "在线";
  return "离线";
});

const statusTone = computed(() => {
  if (!status.value?.configured) return "neutral";
  return status.value.online ? "online" : "offline";
});

const endpointLabel = computed(() => {
  if (status.value?.source === "local") {
    return status.value.detail || "本地摄像头";
  }
  if (!status.value?.ip) return "等待后端配置";
  return `${status.value.ip}:${status.value.port}${status.value.path}`;
});

const fallDetectionLabel = computed(() => {
  if (!fallStatus.value?.enabled) return "跌倒检测未启用";
  if (fallStatus.value.process_running) {
    return fallStatus.value.accuracy_preserving ? "跌倒检测运行中 / 精度优先" : "跌倒检测运行中";
  }
  if (fallStatus.value.running) return "跌倒检测启动中";
  return "跌倒检测离线";
});

const fallDetectionTone = computed(() => {
  if (!fallStatus.value?.enabled) return "neutral";
  if (fallStatus.value.process_running) return "online";
  return "offline";
});

const poseDetectionLabel = computed(() => {
  if (!poseConfig.value?.enabled) return "姿态检测未开启";
  if (poseStatus.value?.process_running) return "姿态检测运行中";
  if (poseStatus.value?.running) return "姿态检测启动中";
  return "姿态检测未就绪";
});

const poseDetectionTone = computed(() => {
  if (!poseConfig.value?.enabled) return "neutral";
  if (poseStatus.value?.process_running) return "online";
  return "offline";
});

const poseActionLabel = computed(() => {
  if (poseBusy.value) return "姿态模式切换中...";
  return cameraViewMode.value === "pose" ? "退出姿态模式" : "姿态检测";
});

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function isFallAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "fall_detected" || alarm.alarm_type === "fall_injury_risk";
}

function fallEvent(alarm: AlarmRecord | null | undefined) {
  return asRecord(alarm?.metadata?.event);
}

function fallReview(alarm: AlarmRecord | null | undefined) {
  return asRecord(fallEvent(alarm)?.multimodal_review);
}

const activeFallAlarms = computed(() => activeAlarms.value.filter((alarm) => !alarm.acknowledged && isFallAlarm(alarm)));

const primaryFallAlarm = computed(() => {
  return [...activeFallAlarms.value].sort((left, right) => {
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  })[0] ?? null;
});

const fallScore = computed(() => {
  const eventScore = numberValue(fallEvent(primaryFallAlarm.value)?.fall_score);
  return eventScore ?? numberValue(primaryFallAlarm.value?.anomaly_probability);
});

const fallScoreLabel = computed(() => {
  const score = fallScore.value;
  if (score == null) return "暂无置信度";
  const normalized = score <= 1 ? score * 100 : score;
  return `${normalized.toFixed(0)}%`;
});

const fallSnapshotUrl = computed(() => {
  const path = stringValue(fallEvent(primaryFallAlarm.value)?.snapshot_path);
  return path ? api.getCameraFallSnapshotUrl(path) : "";
});

const fallRiskTitle = computed(() => {
  const alarm = primaryFallAlarm.value;
  if (!fallStatus.value?.enabled) return "跌倒检测未启用";
  if (!fallStatus.value.process_running) return "跌倒检测未运行";
  if (!alarm) return "安全看护中";
  const judgement = stringValue(fallReview(alarm)?.judgement);
  if (judgement === "no_fall") return "复核建议：暂未确认跌倒";
  if (judgement === "possible_fall" || judgement === "uncertain") return "疑似跌倒，建议查看";
  return "疑似跌倒告警";
});

const fallSafetyTone = computed<FallSafetyTone>(() => {
  if (!fallStatus.value?.enabled || !fallStatus.value.process_running) return "offline";
  const alarm = primaryFallAlarm.value;
  if (!alarm) return "safe";
  const judgement = stringValue(fallReview(alarm)?.judgement);
  if (judgement === "no_fall") return "review";
  if (judgement === "possible_fall" || judgement === "uncertain") return "review";
  return "danger";
});

const fallRiskLead = computed(() => {
  const alarm = primaryFallAlarm.value;
  if (!fallStatus.value?.enabled) return "开启后，系统会从当前摄像头画面中持续识别跌倒风险。";
  if (!fallStatus.value.process_running) return fallStatus.value.last_error || "检测服务暂未进入运行态。";
  if (!alarm) {
    const lastEventAt = fallStatus.value.last_event_at;
    if (lastEventAt) {
      const deltaSeconds = Math.max(0, Math.round(Date.now() / 1000 - lastEventAt));
      return `最近检测 ${deltaSeconds} 秒前，未发现跌倒风险。`;
    }
    return "模型正在看护当前画面，暂无跌倒告警。";
  }
  const event = fallEvent(alarm);
  const severity = stringValue(event?.severity) || "风险";
  const state = stringValue(event?.state) || alarm.alarm_type;
  return `${severity} · ${state} · 置信度 ${fallScoreLabel.value}`;
});

const fallRiskMeta = computed(() => {
  const alarm = primaryFallAlarm.value;
  if (!alarm) return fallStatus.value?.process_running ? "无活跃跌倒告警" : "等待模型运行";
  return `告警时间 ${new Date(alarm.created_at).toLocaleTimeString("zh-CN", { hour12: false })}`;
});

const audioListenSupported = computed(() => audioStatus.value?.listen_supported === true);

const audioCapabilityLabel = computed(() => {
  if (!audioStatus.value?.configured) return "音频未配置";
  if (audioListenSupported.value) {
    const codec = audioStatus.value.audio_codec || "PCM";
    const sampleRate = audioStatus.value.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 0;
    return `${codec} / ${sampleRate || 0}Hz`;
  }
  return audioStatus.value?.error || "当前不支持收听";
});

const audioCapabilityTone = computed(() => {
  if (!audioStatus.value?.configured) return "neutral";
  return audioListenSupported.value ? "online" : "offline";
});

const audioActionLabel = computed(() => {
  if (audioConnecting.value) return "音频连接中";
  if (audioListening.value) return `停止收听（${audioLevel.value.toFixed(0)}%）`;
  return "收听实时音频";
});

const relayFpsLabel = computed(() => {
  if (!mjpegFallback.value && clientFps.value > 0) {
    return clientFps.value.toFixed(1);
  }
  const relayFps = streamStatus.value?.source_fps ?? streamStatus.value?.measured_fps ?? 0;
  return relayFps > 0 ? relayFps.toFixed(1) : clientFps.value.toFixed(1);
});

const externalTargetSummary = computed(() => {
  if (!targetUsers.value.length) return "暂无目标用户";
  const names = targetUsers.value.slice(0, 2).map((item) => item.display_name).join(" / ");
  const extra = targetUsers.value.length > 2 ? ` +${targetUsers.value.length - 2}` : "";
  return `${targetUsers.value.length} 个目标用户：${names}${extra}`;
});

const externalHealthLabel = computed(() => {
  if (!externalCameraHealth.value) return "外部运行时未接通";
  if (externalCameraHealth.value.running && externalCameraHealth.value.has_frame) return "外部运行时在线";
  if (externalCameraHealth.value.running) return "外部运行时已启动";
  return "外部运行时离线";
});

function emitDiagnosticsLog(reason: string) {
  if (typeof console === "undefined") return;
  console.info("[CameraMonitorCard]", {
    reason,
    cameraStatus: status.value,
    streamStatus: streamStatus.value,
    audioStatus: audioStatus.value,
    audioStreamStatus: audioStreamStatus.value,
    fallStatus: fallStatus.value,
    externalCameraHealth: externalCameraHealth.value,
    externalCameraResult: externalCameraResult.value,
  });
}

function clearStaleCameraError() {
  if (!errorMessage.value) return;
  const now = Date.now();
  if (lastStatusErrorAt.value <= 0 || now - lastStatusErrorAt.value > 6000) {
    errorMessage.value = "";
  }
}

function formatCameraError(rawMessage: string) {
  if (!rawMessage) return "";
  if (rawMessage.includes("Invalid data found when processing input")) {
    return "当前主码流不稳定，系统已自动切换到更稳的预览流或快照中继方式。";
  }
  if (rawMessage.includes("TimeoutExpired") || rawMessage.includes("timed out after")) {
    return "RTSP 中继在探测摄像头流时超时，后端会继续重试。";
  }
  if (rawMessage.includes("NETWORK_UNAVAILABLE")) {
    return "当前无法连接到后端摄像头服务。";
  }
  return rawMessage.replace(/rtsp:\/\/[^@\s]+@/gi, "rtsp://***@");
}

async function refreshStatus() {
  loadingStatus.value = true;
  try {
    status.value = await api.getActiveCameraStatus();
    if (!status.value.online && status.value.error) {
      errorMessage.value = formatCameraError(status.value.error);
      lastStatusErrorAt.value = Date.now();
      streamFailureCount.value += 1;
    } else if (status.value.online) {
      if (streamFailureCount.value <= 1) {
        errorMessage.value = "";
      }
      lastStatusErrorAt.value = 0;
    }
    emitDiagnosticsLog("refreshStatus");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "摄像头状态加载失败");
    lastStatusErrorAt.value = Date.now();
  } finally {
    loadingStatus.value = false;
  }
}

async function refreshStreamStatus() {
  try {
    streamStatus.value = await api.getActiveCameraStreamStatus();
  } catch {
    // diagnostics only
  }
}

async function refreshAudioStatus() {
  try {
    audioStatus.value = await api.getActiveCameraAudioStatus();
  } catch {
    // diagnostics only
  }
}

async function refreshAudioStreamStatus() {
  try {
    audioStreamStatus.value = await api.getActiveCameraAudioStreamStatus();
  } catch {
    // diagnostics only
  }
}

async function refreshFallDetectionStatus() {
  try {
    fallStatus.value = await api.getCameraFallDetectionStatus();
  } catch {
    // diagnostics only
  }
}

async function refreshPoseStatus() {
  try {
    poseStatus.value = await api.getCameraPoseDetectionStatus();
  } catch {
    // diagnostics only
  }
}

async function refreshPoseConfig() {
  try {
    poseConfig.value = await api.getCameraPoseDetectionConfig();
  } catch {
    // diagnostics only
  }
}

async function refreshTargetUsers() {
  try {
    targetUsers.value = await api.listTargetUsers();
  } catch {
    targetUsers.value = [];
  }
}

async function refreshAlarms() {
  try {
    activeAlarms.value = await api.listAlarms();
  } catch {
    activeAlarms.value = [];
  }
}

async function refreshExternalCameraHealth() {
  try {
    externalCameraHealth.value = await api.getExternalCameraHealth();
    emitDiagnosticsLog("refreshExternalCameraHealth");
  } catch {
    externalCameraHealth.value = null;
  }
}

async function runExternalCameraCheck() {
  externalCameraBusy.value = true;
  try {
    externalCameraResult.value = await api.runExternalCameraFallDetect({
      target_only: true,
      session_id: "camera-monitor-card",
      mode: "metadata",
    });
    await refreshExternalCameraHealth();
    emitDiagnosticsLog("runExternalCameraCheck");
  } finally {
    externalCameraBusy.value = false;
  }
}

async function togglePoseDetection() {
  if (cameraViewMode.value === "pose") {
    setCameraViewMode("live");
    return;
  }
  poseBusy.value = true;
  try {
    if (!poseConfig.value?.enabled) {
      const result = await api.updateCameraPoseDetectionConfig({
        pose_detection_enabled: true,
      });
      poseConfig.value = result.config;
    }
    await refreshPoseStatus();
    await refreshStatus();
    await refreshStreamStatus();
    setCameraViewMode("pose");
    emitDiagnosticsLog("togglePoseDetection");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "姿态检测切换失败");
    lastStatusErrorAt.value = Date.now();
  } finally {
    poseBusy.value = false;
  }
}

async function acknowledgePrimaryFallAlarm() {
  const alarm = primaryFallAlarm.value;
  if (!alarm) return;
  acknowledgingFall.value = true;
  try {
    await api.ackAlarm(alarm.id);
    await refreshAlarms();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "跌倒告警确认失败";
    lastStatusErrorAt.value = Date.now();
  } finally {
    acknowledgingFall.value = false;
  }
}

function setCameraViewMode(mode: CameraViewMode) {
  if (cameraViewMode.value === mode && autoRefresh.value) return;
  cameraViewMode.value = mode;
  if (!autoRefresh.value) return;
  closeCameraTransport();
  hasFrame.value = false;
  clientFps.value = 0;
  clientFpsFrames = 0;
  clientFpsStartedAt = performance.now();
  startPrimaryVideoTransport();
}

function ensureAudioPlayer() {
  if (audioPlayer) return audioPlayer;
  audioPlayer = new PcmAudioPlayer();
  removeAudioStateListener = audioPlayer.onState((playerState: PcmAudioPlayerState) => {
    audioLevel.value = playerState.level;
    audioQueuedMs.value = playerState.queuedMs;
    audioDroppedBacklog.value = playerState.droppedBacklogCount;
  });
  return audioPlayer;
}

function resumeFrameRefresh() {
  autoRefresh.value = true;
  startPrimaryVideoTransport();
}

function pauseFrameRefresh() {
  autoRefresh.value = false;
  streamState.value = "paused";
  closeCameraTransport();
}

function toggleFrameRefresh() {
  if (autoRefresh.value) pauseFrameRefresh();
  else resumeFrameRefresh();
}

async function toggleAudioListen() {
  if (audioListening.value || audioConnecting.value) {
    await stopAudioListen({ reason: "已停止收听实时音频。" });
    return;
  }
  await startAudioListen();
}

async function startAudioListen() {
  audioDesired.value = true;
  audioConnecting.value = true;
  audioNotice.value = "正在连接摄像头音频中继...";

  try {
    await refreshAudioStatus();
    await refreshAudioStreamStatus();
    if (!audioListenSupported.value) {
      throw new Error(audioStatus.value?.error || "当前摄像头没有可收听的音频轨道。");
    }

    const player = ensureAudioPlayer();
    await player.start(audioStatus.value?.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 8000);
    connectAudioSocket();
  } catch (error) {
    audioDesired.value = false;
    audioConnecting.value = false;
    audioListening.value = false;
    audioNotice.value = error instanceof Error ? error.message : "实时音频启动失败。";
  }
}

async function stopAudioListen(options?: { reason?: string; keepDesired?: boolean }) {
  if (!options?.keepDesired) {
    audioDesired.value = false;
  }
  if (audioReconnectTimer) {
    window.clearTimeout(audioReconnectTimer);
    audioReconnectTimer = undefined;
  }
  const socket = audioSocket;
  audioSocket = undefined;
  if (socket && socket.readyState !== WebSocket.CLOSED) {
    socket.close();
  }
  audioConnecting.value = false;
  audioListening.value = false;
  audioPlayer?.stop();
  if (options?.reason) {
    audioNotice.value = options.reason;
  }
}

function connectAudioSocket() {
  if (audioSocket?.readyState === WebSocket.OPEN || audioSocket?.readyState === WebSocket.CONNECTING) return;

  const socket = api.activeCameraAudioSocket();
  audioSocket = socket;
  socket.binaryType = "arraybuffer";
  socket.onopen = () => {
    audioConnecting.value = false;
    audioListening.value = true;
    const codec = audioStatus.value?.audio_codec || "PCM";
    const rate = audioStatus.value?.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 8000;
    audioNotice.value = `已连接实时音频：${codec} / ${rate}Hz`;
  };
  socket.onmessage = async (event) => {
    try {
      if (event.data instanceof ArrayBuffer) {
        ensureAudioPlayer().pushChunk(event.data);
      } else if (event.data instanceof Blob) {
        ensureAudioPlayer().pushChunk(await event.data.arrayBuffer());
      }
    } catch (error) {
      audioNotice.value = error instanceof Error ? error.message : "音频播放失败。";
      await stopAudioListen({ reason: audioNotice.value });
    }
  };
  socket.onerror = () => {
    audioNotice.value = "音频中继连接失败。";
  };
  socket.onclose = () => {
    audioSocket = undefined;
    audioListening.value = false;
    audioConnecting.value = false;
    if (audioDesired.value) {
      audioReconnectTimer = window.setTimeout(() => {
        audioReconnectTimer = undefined;
        void startAudioListen();
      }, 1400);
    }
  };
}

function handleFrameError() {
  streamFailureCount.value += 1;
  if (streamFailureCount.value >= 2) {
    errorMessage.value = "实时画面暂时不可用，系统正在自动切换到更稳的中继方式。";
  }
  lastStatusErrorAt.value = Date.now();
}

async function setFrame(frame: Blob) {
  const canvas = frameCanvas.value;
  if (!canvas) return;

  try {
    if (frameWatchdog) {
      window.clearTimeout(frameWatchdog);
      frameWatchdog = undefined;
    }
    const bitmap = await createImageBitmap(frame);
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
    }
    const context = canvas.getContext("2d", { alpha: false });
    context?.drawImage(bitmap, 0, 0);
    bitmap.close();
    hasFrame.value = true;
    mjpegFallback.value = false;
    streamState.value = "live";
    recordClientFrame();
    errorMessage.value = "";
  } catch {
    handleFrameError();
  }
}

function queueFrame(frame: Blob) {
  pendingFrame = frame;
  if (renderingFrame || renderRequest !== undefined) return;
  renderRequest = window.requestAnimationFrame(() => {
    renderRequest = undefined;
    renderingFrame = true;
    void renderQueuedFrame();
  });
}

async function renderQueuedFrame() {
  while (pendingFrame) {
    const frame = pendingFrame;
    pendingFrame = undefined;
    await setFrame(frame);
  }
  renderingFrame = false;
}

function recordClientFrame() {
  clientFpsFrames += 1;
  streamFailureCount.value = 0;
  const now = performance.now();
  const elapsed = (now - clientFpsStartedAt) / 1000;
  if (elapsed >= 2) {
    clientFps.value = Number((clientFpsFrames / elapsed).toFixed(2));
    clientFpsFrames = 0;
    clientFpsStartedAt = now;
  }
}

function startCameraSocket() {
  if (
    cameraViewMode.value !== "live" ||
    !autoRefresh.value ||
    frameSocket?.readyState === WebSocket.OPEN ||
    frameSocket?.readyState === WebSocket.CONNECTING
  ) {
    return;
  }

  mjpegFallback.value = false;
  mjpegStreamSrc.value = "";
  streamState.value = "connecting";
  if (frameWatchdog) window.clearTimeout(frameWatchdog);
  frameWatchdog = window.setTimeout(() => {
    if (streamState.value === "connecting") {
      streamState.value = "offline";
      startMjpegFallback();
      errorMessage.value = "已经连到后端，但暂时还没有收到视频帧。";
    }
  }, 5000);
  const socket = api.activeCameraFrameSocket();
  frameSocket = socket;
  socket.binaryType = "blob";
  socket.onmessage = (event) => {
    if (event.data instanceof Blob) {
      queueFrame(event.data);
    }
  };
  socket.onerror = () => {
    streamState.value = "offline";
    startMjpegFallback({ asFallback: true });
    errorMessage.value = "后端摄像头中继暂时不可用。";
  };
  socket.onclose = () => {
    const wasIntentional = intentionalFrameSocketClose === socket;
    if (wasIntentional) {
      intentionalFrameSocketClose = undefined;
    }
    if (frameSocket === socket) {
      frameSocket = undefined;
    }
    const shouldReconnect = autoRefresh.value;
    if (shouldReconnect && !wasIntentional) {
      streamState.value = "connecting";
      window.setTimeout(startCameraSocket, 1600);
    }
  };
}

function startPrimaryVideoTransport() {
  if (cameraViewMode.value !== "live") {
    startMjpegFallback();
    return;
  }
  startMjpegFallback();
  if (primaryStreamTransport === "websocket") {
    window.setTimeout(startCameraSocket, 1200);
  }
}

function buildMjpegStreamUrl() {
  const baseUrl =
    cameraViewMode.value === "fall"
      ? api.getCameraDetectionStreamUrl()
      : cameraViewMode.value === "pose"
        ? api.getCameraPoseStreamUrl()
        : api.getActiveCameraStreamUrl();
  return `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}_ts=${Date.now()}`;
}

function startMjpegFallback(options?: { asFallback?: boolean }) {
  if (!autoRefresh.value) return;
  closeCameraSocket();
  streamState.value = "connecting";
  hasFrame.value = false;
  mjpegStreamSrc.value = buildMjpegStreamUrl();
  mjpegFallback.value = true;
  if (options?.asFallback) {
    errorMessage.value = "WebSocket 中继跟不上，已切换到 MJPEG 画面。";
    lastStatusErrorAt.value = Date.now();
  }
}

function handleMjpegLoaded() {
  hasFrame.value = true;
  streamState.value = "live";
  errorMessage.value = "";
}

function handleMjpegError() {
  streamState.value = "offline";
  errorMessage.value = "MJPEG 中继暂时不可用，正在尝试 WebSocket 回退...";
  lastStatusErrorAt.value = Date.now();
  mjpegFallback.value = false;
  mjpegStreamSrc.value = "";
  startCameraSocket();
}

function closeCameraSocket() {
  if (frameWatchdog) {
    window.clearTimeout(frameWatchdog);
    frameWatchdog = undefined;
  }
  if (renderRequest !== undefined) {
    window.cancelAnimationFrame(renderRequest);
    renderRequest = undefined;
  }
  const socket = frameSocket;
  frameSocket = undefined;
  if (socket && socket.readyState !== WebSocket.CLOSED) {
    intentionalFrameSocketClose = socket;
    socket.close();
  }
}

function closeCameraTransport() {
  closeCameraSocket();
  mjpegFallback.value = false;
  mjpegStreamSrc.value = "";
}

function handleVisibilityChange() {
  if (typeof document === "undefined") return;
  if (document.visibilityState === "hidden") {
    pausedForVisibility = autoRefresh.value;
    closeCameraTransport();
    streamState.value = "paused";
    return;
  }
  if (pausedForVisibility && autoRefresh.value) {
    pausedForVisibility = false;
    startPrimaryVideoTransport();
  }
}

function bindPtz(direction: CameraPtzDirection) {
  return {
    class: { "is-active": activePtz.value === direction },
    disabled: false,
    onPointerdown: (event: PointerEvent) => {
      event.preventDefault();
      const target = event.currentTarget as HTMLElement;
      target.setPointerCapture?.(event.pointerId);
      void startPtz(direction);
    },
    onPointerup: (event: PointerEvent) => {
      event.preventDefault();
      void stopPtz();
    },
    onPointercancel: () => {
      void stopPtz();
    },
    onLostpointercapture: () => {
      void stopPtz();
    },
  };
}

async function startPtz(direction: CameraPtzDirection) {
  if (direction === "stop") {
    await stopPtz();
    return;
  }

  activePtz.value = direction;
  errorMessage.value = "";
  if (ptzStopTimer) {
    window.clearTimeout(ptzStopTimer);
    ptzStopTimer = undefined;
  }

  try {
    await api.moveActiveCamera(direction, "continuous");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "云台控制失败");
    activePtz.value = null;
  }
}

async function stopPtz() {
  if (ptzStopTimer) window.clearTimeout(ptzStopTimer);
  ptzStopTimer = window.setTimeout(() => {
    ptzStopTimer = undefined;
    activePtz.value = null;
  }, 120);

  try {
    await api.moveActiveCamera("stop", "continuous");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "云台停止失败");
  } finally {
    activePtz.value = null;
  }
}

onMounted(() => {
  void refreshStatus().then(startPrimaryVideoTransport);
  void refreshStreamStatus();
  void refreshAudioStatus();
  void refreshAudioStreamStatus();
  void refreshFallDetectionStatus();
  void refreshPoseStatus();
  void refreshPoseConfig();
  void refreshTargetUsers();
  void refreshAlarms();
  void refreshExternalCameraHealth();
  window.setInterval(clearStaleCameraError, 3000);
  statusTimer = window.setInterval(refreshStatus, 8000);
  streamStatusTimer = window.setInterval(() => {
    void refreshStreamStatus();
    void refreshAudioStatus();
    void refreshAudioStreamStatus();
    void refreshFallDetectionStatus();
    void refreshPoseStatus();
    void refreshPoseConfig();
    void refreshAlarms();
    void refreshExternalCameraHealth();
  }, 3000);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onBeforeUnmount(() => {
  if (statusTimer) window.clearInterval(statusTimer);
  if (streamStatusTimer) window.clearInterval(streamStatusTimer);
  if (ptzStopTimer) window.clearTimeout(ptzStopTimer);
  if (audioReconnectTimer) window.clearTimeout(audioReconnectTimer);
  if (activePtz.value) void stopPtz();
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  void stopAudioListen();
  removeAudioStateListener?.();
  void audioPlayer?.dispose();
  closeCameraTransport();
});
</script>

<template>
  <article class="camera-monitor-card">
    <div class="camera-monitor-card__header">
      <div>
        <p class="section-eyebrow">家庭摄像头</p>
        <h3>居家摄像头监护</h3>
        <p>浏览器通过后端摄像头中继查看画面，不再直接开启多路 RTSP 连接。</p>
      </div>
      <span class="camera-monitor-card__status" :class="`is-${statusTone}`">
        <ShieldCheck :size="15" />
        {{ statusLabel }}
      </span>
    </div>

    <div class="camera-monitor-card__viewport" :class="{ 'has-frame': hasFrame }">
      <canvas
        v-show="hasFrame && !mjpegFallback"
        ref="frameCanvas"
        class="camera-monitor-card__canvas"
        aria-label="家庭摄像头实时画面"
      />
      <img
        v-if="mjpegFallback && mjpegStreamSrc"
        class="camera-monitor-card__canvas"
        :src="mjpegStreamSrc"
        alt="家庭摄像头实时画面"
        decoding="async"
        fetchpriority="high"
        @load="handleMjpegLoaded"
        @error="handleMjpegError"
      />
      <div v-if="!hasFrame" class="camera-monitor-card__empty">
        <Camera :size="32" />
        <span>视频已暂停</span>
      </div>
      <div class="camera-monitor-card__live-mark">
        <span />
        {{
          streamState === "live"
            ? `${mjpegFallback ? "中继" : "客户端"} ${relayFpsLabel}fps`
            : streamState === "paused"
              ? "已暂停"
              : streamState === "offline"
                ? "离线"
                : "连接中"
        }}
      </div>
      <div v-if="audioListening || audioConnecting" class="camera-monitor-card__audio-mark">
        <Volume2 :size="15" />
        <span>{{ audioConnecting ? "音频连接中" : `实时音量 ${audioLevel.toFixed(0)}%` }}</span>
      </div>
      <div class="camera-monitor-card__safety" :class="`is-${fallSafetyTone}`">
        <div>
          <span class="camera-monitor-card__safety-kicker">
            {{ cameraViewMode === "fall" ? "跌倒检测画面" : "安全看护" }}
          </span>
          <strong>{{ fallRiskTitle }}</strong>
          <p>{{ fallRiskLead }}</p>
        </div>
        <div class="camera-monitor-card__safety-side">
          <span>{{ fallRiskMeta }}</span>
          <button
            v-if="primaryFallAlarm"
            type="button"
            :disabled="acknowledgingFall"
            @click="acknowledgePrimaryFallAlarm"
          >
            {{ acknowledgingFall ? "确认中" : "确认已处理" }}
          </button>
        </div>
      </div>
      <a
        v-if="fallSnapshotUrl"
        class="camera-monitor-card__snapshot-link"
        :href="fallSnapshotUrl"
        target="_blank"
        rel="noreferrer"
      >
        查看跌倒截图
      </a>
    </div>

    <div class="camera-control-dock">
      <div>
        <p class="section-eyebrow">云台控制</p>
        <h4>远程控制</h4>
      </div>

      <div class="camera-joystick" aria-label="摄像头方向控制">
        <button type="button" class="camera-joystick__zone is-up" aria-label="向上" v-bind="bindPtz('up')">
          <ChevronUp :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-left" aria-label="向左" v-bind="bindPtz('left')">
          <ChevronLeft :size="28" />
        </button>
        <button type="button" class="camera-joystick__center" aria-label="停止" @click="stopPtz">
          <Move :size="23" />
        </button>
        <button type="button" class="camera-joystick__zone is-right" aria-label="向右" v-bind="bindPtz('right')">
          <ChevronRight :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-down" aria-label="向下" v-bind="bindPtz('down')">
          <ChevronDown :size="28" />
        </button>
      </div>
    </div>

    <div class="camera-monitor-card__meta">
      <span>{{ endpointLabel }}</span>
      <span v-if="status?.source === 'local'">来源：本地摄像头</span>
      <span v-if="status?.latency_ms !== null && status?.latency_ms !== undefined">延迟 {{ status.latency_ms }}ms</span>
      <span v-else>来源：本地 RTSP</span>
      <span v-if="streamStatus">目标 {{ (streamStatus.target_fps ?? 0).toFixed(1) }}fps</span>
      <span v-if="streamStatus">源流 {{ (streamStatus.source_fps ?? streamStatus.measured_fps ?? 0).toFixed(1) }}fps</span>
      <span v-if="streamStatus">JPEG q{{ streamStatus.jpeg_quality ?? 4 }}</span>
      <span :class="`camera-monitor-card__fall is-${audioCapabilityTone}`">{{ audioCapabilityLabel }}</span>
      <span class="camera-monitor-card__fall" :class="`is-${fallDetectionTone}`">{{ fallDetectionLabel }}</span>
      <span class="camera-monitor-card__fall" :class="`is-${poseDetectionTone}`">{{ poseDetectionLabel }}</span>
      <span class="camera-monitor-card__fall">{{ externalHealthLabel }}</span>
      <span class="camera-monitor-card__fall">{{ externalTargetSummary }}</span>
    </div>

    <p v-if="errorMessage" class="camera-monitor-card__error">{{ errorMessage }}</p>
    <p v-if="audioNotice" class="camera-monitor-card__notice">{{ audioNotice }}</p>

    <div class="camera-monitor-card__actions">
      <button type="button" class="camera-action camera-action--primary" @click="toggleFrameRefresh">
        <Pause v-if="autoRefresh" :size="16" />
        <Play v-else :size="16" />
        {{ autoRefresh ? "暂停视频" : "恢复视频" }}
      </button>
      <button
        type="button"
        class="camera-action"
        :disabled="audioConnecting || !audioStatus?.configured"
        @click="toggleAudioListen"
      >
        <VolumeX v-if="audioListening" :size="16" />
        <Volume2 v-else :size="16" />
        {{ audioActionLabel }}
      </button>
      <button
        type="button"
        class="camera-action"
        :disabled="loadingStatus"
        @click="
          refreshStatus();
          refreshStreamStatus();
          refreshAudioStatus();
          refreshAudioStreamStatus();
          refreshFallDetectionStatus();
          refreshAlarms();
          refreshTargetUsers();
          refreshExternalCameraHealth();
        "
      >
        <RefreshCw :size="16" />
        刷新状态
      </button>
      <div class="camera-mode-switch" aria-label="画面模式切换">
        <button
          type="button"
          :class="{ 'is-active': cameraViewMode === 'live' }"
          @click="setCameraViewMode('live')"
        >
          实时画面
        </button>
        <button
          type="button"
          :class="{ 'is-active': cameraViewMode === 'fall' }"
          @click="setCameraViewMode('fall')"
        >
          跌倒检测
        </button>
        <button
          type="button"
          :class="{ 'is-active': cameraViewMode === 'pose' }"
          :disabled="poseBusy"
          @click="togglePoseDetection"
        >
          {{ poseActionLabel }}
        </button>
      </div>
      <button
        type="button"
        class="camera-action"
        :disabled="externalCameraBusy"
        @click="runExternalCameraCheck"
      >
        <ShieldCheck :size="16" />
        {{ externalCameraBusy ? "筛选中..." : "执行目标用户筛选" }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.camera-monitor-card {
  position: relative;
  display: grid;
  gap: 14px;
  padding: 18px;
  overflow: hidden;
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(59, 130, 246, 0.1), transparent 28%),
    linear-gradient(145deg, rgba(248, 251, 255, 0.96), rgba(255, 255, 255, 0.98) 46%, rgba(239, 246, 255, 0.92));
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.08);
}

.camera-monitor-card__header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.camera-monitor-card__header h3 {
  margin: 2px 0 0;
  font-size: 1.18rem;
  letter-spacing: -0.03em;
}

.camera-monitor-card__header p:last-child {
  max-width: 680px;
  margin: 7px 0 0;
  color: var(--text-sub);
  font-size: 0.88rem;
  line-height: 1.7;
}

.camera-monitor-card__status,
.camera-monitor-card__meta span,
.camera-action {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.camera-monitor-card__status {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 0.82rem;
  font-weight: 700;
}

.camera-monitor-card__status.is-online {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.camera-monitor-card__status.is-offline {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.camera-monitor-card__status.is-neutral {
  background: rgba(100, 116, 139, 0.1);
  color: var(--text-sub);
}

.camera-monitor-card__viewport {
  position: relative;
  aspect-ratio: 16 / 9;
  min-height: clamp(260px, 32vw, 460px);
  overflow: hidden;
  border-radius: 19px;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.82), rgba(30, 64, 175, 0.48)),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.05) 0 1px, transparent 1px 18px);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.15), 0 16px 28px rgba(15, 23, 42, 0.1);
}

.camera-monitor-card__viewport img,
.camera-monitor-card__canvas {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  object-fit: contain;
  object-position: center;
}

.camera-monitor-card__canvas {
  position: absolute;
  inset: 0;
}

.camera-monitor-card__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 700;
}

.camera-monitor-card__live-mark {
  position: absolute;
  left: 14px;
  top: 14px;
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(255, 255, 255, 0.9);
  color: #1e3a8a;
  font-size: 0.78rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
}

.camera-monitor-card__live-mark span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.16);
}

.camera-monitor-card__audio-mark {
  position: absolute;
  right: 14px;
  top: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(255, 255, 255, 0.9);
  color: #1e3a8a;
  font-size: 0.78rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
}

.camera-monitor-card__safety {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 14px;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-end;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 18px;
  padding: 13px 14px;
  color: #f8fafc;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.42)),
    radial-gradient(circle at 0% 0%, rgba(34, 197, 94, 0.18), transparent 35%);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(16px);
}

.camera-monitor-card__safety.is-danger {
  border-color: rgba(248, 113, 113, 0.4);
  background:
    linear-gradient(135deg, rgba(127, 29, 29, 0.82), rgba(15, 23, 42, 0.52)),
    radial-gradient(circle at 0% 0%, rgba(248, 113, 113, 0.34), transparent 38%);
}

.camera-monitor-card__safety.is-review {
  border-color: rgba(251, 191, 36, 0.42);
  background:
    linear-gradient(135deg, rgba(120, 53, 15, 0.78), rgba(15, 23, 42, 0.5)),
    radial-gradient(circle at 0% 0%, rgba(251, 191, 36, 0.34), transparent 38%);
}

.camera-monitor-card__safety.is-offline {
  border-color: rgba(148, 163, 184, 0.3);
  background:
    linear-gradient(135deg, rgba(51, 65, 85, 0.78), rgba(15, 23, 42, 0.5)),
    radial-gradient(circle at 0% 0%, rgba(148, 163, 184, 0.2), transparent 38%);
}

.camera-monitor-card__safety-kicker {
  display: block;
  margin-bottom: 3px;
  color: rgba(226, 232, 240, 0.78);
  font-size: 0.7rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.camera-monitor-card__safety strong {
  display: block;
  font-size: clamp(1rem, 1.7vw, 1.28rem);
  letter-spacing: -0.04em;
}

.camera-monitor-card__safety p {
  max-width: 560px;
  margin: 5px 0 0;
  color: rgba(248, 250, 252, 0.82);
  font-size: 0.82rem;
  line-height: 1.45;
}

.camera-monitor-card__safety-side {
  display: grid;
  justify-items: end;
  gap: 8px;
  flex-shrink: 0;
}

.camera-monitor-card__safety-side span {
  color: rgba(248, 250, 252, 0.72);
  font-size: 0.74rem;
  font-weight: 700;
}

.camera-monitor-card__safety-side button,
.camera-monitor-card__snapshot-link {
  border: 0;
  border-radius: 999px;
  padding: 7px 11px;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 900;
  text-decoration: none;
}

.camera-monitor-card__safety-side button:disabled {
  cursor: wait;
  opacity: 0.68;
}

.camera-monitor-card__snapshot-link {
  position: absolute;
  right: 14px;
  top: 52px;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.16);
}

.camera-control-dock {
  display: grid;
  grid-template-columns: minmax(120px, 0.34fr) auto;
  gap: 14px;
  align-items: center;
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-radius: 20px;
  padding: 13px 14px;
  background: rgba(255, 255, 255, 0.78);
}

.camera-control-dock h4 {
  margin: 2px 0 0;
  font-size: 1rem;
}

.camera-joystick {
  position: relative;
  width: clamp(146px, 18vw, 188px);
  aspect-ratio: 1;
  border-radius: 999px;
  touch-action: none;
  user-select: none;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.92) 0 21%, transparent 22%),
    radial-gradient(circle at center, rgba(37, 99, 235, 0.1) 0 41%, rgba(15, 23, 42, 0.1) 42% 100%);
  box-shadow:
    inset 0 0 0 1px rgba(37, 99, 235, 0.1),
    0 12px 24px rgba(37, 99, 235, 0.08);
}

.camera-joystick__zone,
.camera-joystick__center {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  color: rgba(37, 99, 235, 0.78);
  cursor: pointer;
  touch-action: none;
  user-select: none;
  transition: transform var(--trans-base), color var(--trans-base), background var(--trans-base);
}

.camera-joystick__zone {
  width: 36%;
  height: 36%;
  border-radius: 999px;
  background: transparent;
}

.camera-joystick__zone:hover:not(:disabled),
.camera-joystick__zone.is-active,
.camera-joystick__zone:active {
  color: #1d4ed8;
  background: rgba(255, 255, 255, 0.78);
}

.camera-joystick__zone.is-up {
  top: 3%;
  left: 32%;
}

.camera-joystick__zone.is-left {
  top: 32%;
  left: 3%;
}

.camera-joystick__zone.is-right {
  top: 32%;
  right: 3%;
}

.camera-joystick__zone.is-down {
  bottom: 3%;
  left: 32%;
}

.camera-joystick__center {
  top: 50%;
  left: 50%;
  width: 28%;
  aspect-ratio: 1;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.98);
  color: rgba(37, 99, 235, 0.8);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.08);
}

.camera-monitor-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.camera-monitor-card__meta span {
  border-radius: 999px;
  padding: 6px 11px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: rgba(255, 255, 255, 0.86);
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 600;
}

.camera-monitor-card__fall {
  border-radius: 999px;
  padding: 6px 11px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: rgba(255, 255, 255, 0.86);
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 600;
}

.camera-monitor-card__fall.is-online {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.11);
  color: #047857;
}

.camera-monitor-card__fall.is-offline {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.camera-monitor-card__error {
  margin: 0;
  color: #dc2626;
  font-size: 0.86rem;
  line-height: 1.6;
}

.camera-monitor-card__notice {
  margin: 0;
  color: #0f766e;
  font-size: 0.86rem;
  line-height: 1.6;
}

.camera-monitor-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}

.camera-mode-switch {
  display: inline-flex;
  gap: 4px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: 999px;
  padding: 4px;
  background: rgba(241, 245, 249, 0.86);
}

.camera-mode-switch button {
  border: 0;
  border-radius: 999px;
  padding: 8px 12px;
  background: transparent;
  color: #475569;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 800;
}

.camera-mode-switch button.is-active {
  color: #ffffff;
  background: #0f766e;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.18);
}

.camera-mode-switch button:disabled {
  cursor: wait;
  opacity: 0.62;
}

.camera-action {
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 999px;
  padding: 9px 13px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--text-main);
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 700;
}

.camera-action--primary {
  border-color: transparent;
  background: #2563eb;
  color: #ffffff;
}

.camera-action:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

@media (max-width: 900px) {
  .camera-control-dock {
    grid-template-columns: 1fr;
  }

  .camera-joystick {
    justify-self: center;
    width: clamp(156px, 44vw, 210px);
  }
}

@media (max-width: 720px) {
  .camera-monitor-card__header {
    flex-direction: column;
  }

  .camera-monitor-card__safety {
    flex-direction: column;
    align-items: flex-start;
  }

  .camera-monitor-card__safety-side {
    justify-items: start;
  }

  .camera-mode-switch {
    width: 100%;
    justify-content: space-between;
  }

  .camera-mode-switch button {
    flex: 1;
  }

  .camera-action {
    width: 100%;
    justify-content: center;
  }
}
</style>
