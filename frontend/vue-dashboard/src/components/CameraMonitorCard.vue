<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Camera,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Move,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Volume2,
} from "lucide-vue-next";
import { api, type CameraPtzDirection, type CameraStatusResponse, type CameraStreamStatusResponse } from "../api/client";

const status = ref<CameraStatusResponse | null>(null);
const streamStatus = ref<CameraStreamStatusResponse | null>(null);
const frameCanvas = ref<HTMLCanvasElement | null>(null);
const hasFrame = ref(false);
const loadingStatus = ref(false);
const autoRefresh = ref(true);
const streamState = ref<"connecting" | "live" | "paused" | "offline">("connecting");
const clientFps = ref(0);
const activePtz = ref<CameraPtzDirection | null>(null);
const ptzBusy = ref<CameraPtzDirection | null>(null);
const errorMessage = ref("");
const audioNotice = ref("");
const audioListening = ref(false);
const audioLevel = ref(0);
const showDiagnostics = ref(false);
const frameAspectRatio = ref("16 / 9");

let statusTimer: number | undefined;
let streamStatusTimer: number | undefined;
let frameSocket: WebSocket | undefined;
let audioSocket: WebSocket | undefined;
let audioContext: AudioContext | undefined;
let audioNextTime = 0;
let frameWatchdog: number | undefined;
let pendingFrame: Blob | undefined;
let renderingFrame = false;
let renderRequest: number | undefined;
let clientFpsStartedAt = performance.now();
let clientFpsFrames = 0;
let ptzReleaseTimer: number | undefined;
let joystickPointerId: number | null = null;

const statusLabel = computed(() => {
  if (!status.value?.configured) return "未配置";
  if (status.value.online) return "在线";
  return "离线";
});

const statusTone = computed(() => {
  if (!status.value?.configured) return "neutral";
  return status.value.online ? "online" : "offline";
});

const streamLabel = computed(() => {
  if (streamState.value === "live") return `实收 ${clientFps.value.toFixed(1)}fps`;
  if (streamState.value === "paused") return "画面已暂停";
  if (streamState.value === "offline") return "暂无视频帧";
  return "连接中";
});

const endpointLabel = computed(() => {
  if (!status.value?.ip) return "等待后端配置";
  return `${status.value.ip}:${status.value.port}${status.value.path}`;
});

const sourceFps = computed(() => streamStatus.value?.source_fps ?? streamStatus.value?.measured_fps ?? 0);

const listeningLabel = computed(() => {
  if (!audioListening.value) return "监听未开启";
  if (audioLevel.value >= 45) return `环境声较明显 ${audioLevel.value}%`;
  if (audioLevel.value >= 12) return `正在监听 ${audioLevel.value}%`;
  return "正在监听，环境较安静";
});

async function refreshStatus() {
  loadingStatus.value = true;
  try {
    status.value = await api.getCameraStatus();
    if (!status.value.online && status.value.error) {
      errorMessage.value = status.value.error;
    } else if (status.value.online) {
      errorMessage.value = "";
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "摄像头状态读取失败";
  } finally {
    loadingStatus.value = false;
  }
}

async function refreshStreamStatus() {
  try {
    streamStatus.value = await api.getCameraStreamStatus();
  } catch {
    // 诊断信息读取失败不影响视频主链路。
  }
}

function resumeFrameRefresh() {
  autoRefresh.value = true;
  startCameraSocket();
}

function pauseFrameRefresh() {
  autoRefresh.value = false;
  streamState.value = "paused";
  closeCameraSocket();
}

function toggleFrameRefresh() {
  if (autoRefresh.value) {
    pauseFrameRefresh();
  } else {
    resumeFrameRefresh();
  }
}

function handleFrameError() {
  streamState.value = "offline";
  errorMessage.value = "实时画面暂时不可用。请确认后端正在运行，并且电脑仍连接摄像头所在局域网。";
}

async function setFrame(frame: Blob) {
  const canvas = frameCanvas.value;
  if (!canvas) return;

  try {
    const bitmap = await createImageBitmap(frame);
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
    }
    frameAspectRatio.value = `${bitmap.width} / ${bitmap.height}`;
    const context = canvas.getContext("2d", { alpha: false });
    context?.drawImage(bitmap, 0, 0);
    bitmap.close();
    hasFrame.value = true;
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
  const now = performance.now();
  const elapsed = (now - clientFpsStartedAt) / 1000;
  if (elapsed >= 2) {
    clientFps.value = Number((clientFpsFrames / elapsed).toFixed(2));
    clientFpsFrames = 0;
    clientFpsStartedAt = now;
  }
}

function startCameraSocket() {
  if (!autoRefresh.value || frameSocket?.readyState === WebSocket.OPEN || frameSocket?.readyState === WebSocket.CONNECTING) {
    return;
  }

  streamState.value = "connecting";
  if (frameWatchdog) window.clearTimeout(frameWatchdog);
  frameWatchdog = window.setTimeout(() => {
    if (streamState.value === "connecting") {
      streamState.value = "offline";
      errorMessage.value = "后端已连接，但还没有收到摄像头视频帧。请检查局域网连接和 /camera/stream-status。";
    }
  }, 5000);

  frameSocket = api.cameraFrameSocket();
  frameSocket.binaryType = "blob";
  frameSocket.onmessage = (event) => {
    if (event.data instanceof Blob) queueFrame(event.data);
  };
  frameSocket.onerror = () => {
    streamState.value = "offline";
    errorMessage.value = "后端摄像头转发暂时不可用，请确认 Windows 后端仍在运行。";
  };
  frameSocket.onclose = () => {
    const shouldReconnect = autoRefresh.value;
    frameSocket = undefined;
    if (shouldReconnect) {
      streamState.value = "connecting";
      window.setTimeout(startCameraSocket, 1200);
    }
  };
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
  if (socket && socket.readyState !== WebSocket.CLOSED) socket.close();
}

function joystickDirectionFromEvent(event: PointerEvent): CameraPtzDirection | null {
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const x = event.clientX - rect.left - rect.width / 2;
  const y = event.clientY - rect.top - rect.height / 2;
  const distance = Math.hypot(x, y);
  if (distance < rect.width * 0.16) return "stop";
  if (Math.abs(x) > Math.abs(y)) return x > 0 ? "right" : "left";
  return y > 0 ? "down" : "up";
}

function handleJoystickDown(event: PointerEvent) {
  event.preventDefault();
  const target = event.currentTarget as HTMLElement;
  joystickPointerId = event.pointerId;
  target.setPointerCapture?.(event.pointerId);
  const direction = joystickDirectionFromEvent(event);
  if (direction) void startPtz(direction);
}

function handleJoystickMove(event: PointerEvent) {
  if (joystickPointerId !== event.pointerId) return;
  event.preventDefault();
  const direction = joystickDirectionFromEvent(event);
  if (direction && direction !== activePtz.value) {
    void startPtz(direction);
  }
}

function handleJoystickUp(event: PointerEvent) {
  if (joystickPointerId !== event.pointerId) return;
  event.preventDefault();
  joystickPointerId = null;
  void stopPtz();
}

function stopPtzOnSafetyEvent() {
  if (activePtz.value || joystickPointerId !== null) {
    joystickPointerId = null;
    void stopPtz();
  }
}

function handleVisibilityChange() {
  if (document.hidden) stopPtzOnSafetyEvent();
}

async function startPtz(direction: CameraPtzDirection) {
  if (direction === "stop") {
    await stopPtz();
    return;
  }

  if (ptzReleaseTimer) {
    window.clearTimeout(ptzReleaseTimer);
    ptzReleaseTimer = undefined;
  }
  if (activePtz.value === direction) return;

  activePtz.value = direction;
  ptzBusy.value = direction;
  errorMessage.value = "";

  try {
    await api.moveCamera(direction, "continuous");
    if (autoRefresh.value) startCameraSocket();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "云台控制失败";
    activePtz.value = null;
  } finally {
    ptzBusy.value = null;
  }
}

async function stopPtz() {
  if (ptzReleaseTimer) window.clearTimeout(ptzReleaseTimer);
  activePtz.value = null;
  ptzReleaseTimer = window.setTimeout(() => {
    ptzReleaseTimer = undefined;
  }, 120);

  try {
    await api.moveCamera("stop", "continuous");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "云台停止失败";
  }
}

async function toggleAudioListen() {
  if (audioListening.value) {
    stopAudioListen();
    audioNotice.value = "监听已关闭。";
    return;
  }

  try {
    const audioStatus = await api.getCameraAudioStatus();
    if (!audioStatus.listen_supported) {
      audioNotice.value = audioStatus.error
        ? `暂时没有拿到摄像头声音：${audioStatus.error}`
        : "暂时没有拿到摄像头声音，请确认摄像头 RTSP 音频已开启。";
      return;
    }

    audioContext = audioContext ?? new AudioContext({ sampleRate: 8000 });
    if (audioContext.state === "suspended") await audioContext.resume();
    audioNextTime = audioContext.currentTime + 0.08;

    audioSocket = api.cameraAudioSocket();
    audioSocket.binaryType = "arraybuffer";
    audioSocket.onopen = () => {
      audioListening.value = true;
      const codec = audioStatus.audio_codec ?? "G711/PCM";
      const rate = audioStatus.sample_rate ?? 8000;
      audioNotice.value = `监听已开启：正在播放摄像头周围声音（${codec} / ${rate}Hz）。`;
    };
    audioSocket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) playPcmChunk(event.data);
    };
    audioSocket.onerror = () => {
      audioNotice.value = "监听连接失败，请确认后端和摄像头仍在同一局域网。";
      stopAudioListen();
    };
    audioSocket.onclose = () => {
      audioListening.value = false;
      audioLevel.value = 0;
      audioSocket = undefined;
    };
  } catch (error) {
    audioNotice.value = error instanceof Error ? error.message : "监听启动失败";
    stopAudioListen();
  }
}

function playPcmChunk(buffer: ArrayBuffer) {
  if (!audioContext || buffer.byteLength < 2) return;

  const samples = new Int16Array(buffer);
  const audioBuffer = audioContext.createBuffer(1, samples.length, 8000);
  const channel = audioBuffer.getChannelData(0);
  let peak = 0;
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index] / 32768;
    channel[index] = value;
    peak = Math.max(peak, Math.abs(value));
  }
  audioLevel.value = Math.round(peak * 100);

  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);

  const startAt = Math.max(audioContext.currentTime + 0.02, audioNextTime);
  source.start(startAt);
  audioNextTime = startAt + audioBuffer.duration;
  if (audioNextTime - audioContext.currentTime > 0.6) {
    audioNextTime = audioContext.currentTime + 0.12;
  }
}

function stopAudioListen() {
  const socket = audioSocket;
  audioSocket = undefined;
  if (socket && socket.readyState !== WebSocket.CLOSED) socket.close();
  audioListening.value = false;
  audioLevel.value = 0;
}

onMounted(() => {
  void refreshStatus().then(() => {
    if (autoRefresh.value) startCameraSocket();
  });
  void refreshStreamStatus();
  statusTimer = window.setInterval(refreshStatus, 8000);
  streamStatusTimer = window.setInterval(refreshStreamStatus, 3000);
  window.addEventListener("blur", stopPtzOnSafetyEvent);
  document.addEventListener("visibilitychange", handleVisibilityChange);
});

onBeforeUnmount(() => {
  if (statusTimer) window.clearInterval(statusTimer);
  if (streamStatusTimer) window.clearInterval(streamStatusTimer);
  if (ptzReleaseTimer) window.clearTimeout(ptzReleaseTimer);
  if (activePtz.value) void stopPtz();
  window.removeEventListener("blur", stopPtzOnSafetyEvent);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  stopAudioListen();
  closeCameraSocket();
});
</script>

<template>
  <article class="camera-monitor-card">
    <header class="camera-monitor-card__header">
      <div>
        <h3>家中实时看护</h3>
      </div>
      <span class="camera-monitor-card__status" :class="`is-${statusTone}`">
        <ShieldCheck :size="15" />
        {{ statusLabel }}
      </span>
    </header>

    <section class="camera-monitor-card__stage">
      <div class="camera-monitor-card__viewport" :class="{ 'has-frame': hasFrame }" :style="{ aspectRatio: frameAspectRatio }">
        <canvas
          v-show="hasFrame"
          ref="frameCanvas"
          class="camera-monitor-card__canvas"
          aria-label="家中摄像头实时画面"
        />
        <div v-if="!hasFrame" class="camera-monitor-card__empty">
          <Camera :size="34" />
          <span>{{ streamState === "connecting" ? "正在连接摄像头画面" : "画面已暂停" }}</span>
        </div>
        <div class="camera-monitor-card__live-mark">
          <span />
          {{ streamLabel }}
        </div>
        <div v-if="audioListening" class="camera-monitor-card__audio-mark">
          <Volume2 :size="15" />
          {{ listeningLabel }}
        </div>
      </div>
    </section>

    <section class="camera-control-dock" aria-label="摄像头云台控制">
      <div class="camera-control-dock__copy">
        <h4>云台控制</h4>
      </div>

      <div
        class="camera-joystick"
        :class="activePtz ? `is-${activePtz}` : ''"
        role="application"
        aria-label="摄像头模拟摇杆"
        @pointerdown="handleJoystickDown"
        @pointermove="handleJoystickMove"
        @pointerup="handleJoystickUp"
        @pointercancel="handleJoystickUp"
        @lostpointercapture="handleJoystickUp"
      >
        <span class="camera-joystick__zone is-up"><ChevronUp :size="30" /></span>
        <span class="camera-joystick__zone is-left"><ChevronLeft :size="30" /></span>
        <span class="camera-joystick__zone is-right"><ChevronRight :size="30" /></span>
        <span class="camera-joystick__zone is-down"><ChevronDown :size="30" /></span>
        <span class="camera-joystick__center"><Move :size="23" /></span>
      </div>

      <div class="camera-monitor-card__actions" aria-label="摄像头操作">
        <button type="button" class="camera-action camera-action--primary" @click="toggleFrameRefresh">
          <Pause v-if="autoRefresh" :size="16" />
          <Play v-else :size="16" />
          {{ autoRefresh ? "暂停画面" : "继续查看" }}
        </button>
        <button type="button" class="camera-action" :disabled="loadingStatus" @click="refreshStatus">
          <RefreshCw :size="16" />
          刷新状态
        </button>
        <button type="button" class="camera-action" :class="{ 'is-listening': audioListening }" @click="toggleAudioListen">
          <Volume2 :size="16" />
          {{ audioListening ? `监听中 ${audioLevel}%` : "开始监听" }}
        </button>
        <button type="button" class="camera-action camera-action--ghost" @click="showDiagnostics = !showDiagnostics">
          {{ showDiagnostics ? "收起诊断" : "查看诊断" }}
        </button>
      </div>
    </section>

    <section v-if="showDiagnostics" class="camera-monitor-card__meta" aria-label="摄像头诊断信息">
      <span>{{ endpointLabel }}</span>
      <span v-if="status?.latency_ms !== null && status?.latency_ms !== undefined">局域网延迟 {{ status.latency_ms }}ms</span>
      <span v-else>局域网 RTSP</span>
      <span>前端实收 {{ clientFps.toFixed(1) }}fps</span>
      <span v-if="streamStatus">摄像头源流 {{ sourceFps.toFixed(1) }}fps</span>
      <span>云台 ONVIF 10080</span>
    </section>
    <p v-if="errorMessage" class="camera-monitor-card__error">{{ errorMessage }}</p>
    <p v-if="audioNotice" class="camera-monitor-card__notice">{{ audioNotice }}</p>
  </article>
</template>

<style scoped>
.camera-monitor-card {
  position: relative;
  display: grid;
  gap: 15px;
  padding: clamp(16px, 2vw, 20px);
  overflow: hidden;
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(45, 212, 191, 0.2), transparent 28%),
    linear-gradient(145deg, rgba(240, 253, 250, 0.96), rgba(255, 255, 255, 0.98) 48%, rgba(239, 246, 255, 0.92));
  box-shadow: 0 16px 44px rgba(15, 118, 110, 0.12);
}

.camera-monitor-card__header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.camera-monitor-card__header h3 {
  margin: 0;
  font-size: clamp(1.12rem, 2vw, 1.28rem);
  letter-spacing: -0.03em;
}

.camera-monitor-card__status,
.camera-monitor-card__meta span,
.camera-action,
.camera-monitor-card__live-mark {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.camera-monitor-card__status {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 0.82rem;
  font-weight: 800;
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
  width: 100%;
  aspect-ratio: 16 / 9;
  min-height: 0;
  overflow: hidden;
  border-radius: 19px;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.78), rgba(15, 118, 110, 0.54)),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.06) 0 1px, transparent 1px 18px);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 20px 36px rgba(15, 23, 42, 0.12);
}

.camera-monitor-card__canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
}

.camera-monitor-card__viewport.has-frame .camera-monitor-card__empty {
  display: none;
}

.camera-monitor-card__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.88);
  font-weight: 800;
}

.camera-monitor-card__live-mark {
  position: absolute;
  left: 14px;
  top: 14px;
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(15, 23, 42, 0.62);
  color: #ecfeff;
  font-size: 0.78rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
}

.camera-monitor-card__live-mark span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.18);
}

.camera-monitor-card__audio-mark {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(4, 120, 87, 0.74);
  color: #ecfdf5;
  font-size: 0.78rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
  box-shadow: 0 10px 20px rgba(6, 95, 70, 0.18);
}

.camera-control-dock {
  display: grid;
  grid-template-columns: minmax(100px, 0.28fr) auto minmax(240px, 0.5fr);
  gap: 14px;
  align-items: center;
  border: 1px solid rgba(13, 148, 136, 0.14);
  border-radius: 20px;
  padding: 13px 14px;
  background: rgba(255, 255, 255, 0.68);
}

.camera-control-dock h4 {
  margin: 0;
  font-size: 1rem;
}

.camera-control-dock__copy {
  color: #0f766e;
  font-weight: 900;
}

.camera-joystick {
  position: relative;
  justify-self: center;
  width: clamp(156px, 18vw, 196px);
  aspect-ratio: 1;
  border-radius: 999px;
  cursor: grab;
  touch-action: none;
  user-select: none;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.96) 0 19%, transparent 20%),
    conic-gradient(from 45deg, rgba(13, 148, 136, 0.1), rgba(15, 23, 42, 0.16), rgba(13, 148, 136, 0.1)),
    radial-gradient(circle at center, rgba(15, 118, 110, 0.12) 0 48%, rgba(15, 23, 42, 0.14) 49% 100%);
  box-shadow:
    inset 0 0 0 1px rgba(13, 148, 136, 0.12),
    0 18px 34px rgba(15, 118, 110, 0.12);
}

.camera-joystick:active {
  cursor: grabbing;
}

.camera-joystick__zone,
.camera-joystick__center {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgba(15, 118, 110, 0.72);
  pointer-events: none;
  transition: transform 140ms ease, color 140ms ease, background 140ms ease;
}

.camera-joystick__zone {
  width: 40%;
  height: 40%;
  border-radius: 999px;
}

.camera-joystick__zone.is-up {
  top: 2%;
  left: 30%;
}

.camera-joystick__zone.is-left {
  top: 30%;
  left: 2%;
}

.camera-joystick__zone.is-right {
  top: 30%;
  right: 2%;
}

.camera-joystick__zone.is-down {
  bottom: 2%;
  left: 30%;
}

.camera-joystick.is-up .is-up,
.camera-joystick.is-left .is-left,
.camera-joystick.is-right .is-right,
.camera-joystick.is-down .is-down {
  color: #0f766e;
  background: rgba(255, 255, 255, 0.68);
  transform: scale(1.08);
}

.camera-joystick__center {
  top: 50%;
  left: 50%;
  width: 30%;
  aspect-ratio: 1;
  border-radius: 999px;
  transform: translate(-50%, -50%);
  background: rgba(255, 255, 255, 0.96);
  color: rgba(15, 118, 110, 0.7);
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.14);
}

.camera-monitor-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.camera-monitor-card__meta span {
  border-radius: 999px;
  padding: 6px 11px;
  border: 1px solid rgba(13, 148, 136, 0.14);
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 700;
}

.camera-monitor-card__error,
.camera-monitor-card__notice {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.6;
}

.camera-monitor-card__error {
  color: #dc2626;
}

.camera-monitor-card__notice {
  color: #0f766e;
}

.camera-monitor-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  justify-content: flex-end;
}

.camera-action {
  min-height: 42px;
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 999px;
  padding: 9px 13px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--text-main);
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 800;
  transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
}

.camera-action:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.12);
}

.camera-action.is-listening {
  border-color: rgba(5, 150, 105, 0.44);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(240, 253, 250, 0.92));
  color: #047857;
}

.camera-action--primary {
  border-color: transparent;
  background: #0f766e;
  color: #ffffff;
}

.camera-action--primary:hover:not(:disabled) {
  background: #115e59;
}

.camera-action--ghost {
  background: rgba(255, 255, 255, 0.42);
  color: #0f766e;
}

.camera-action:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

@media (max-width: 900px) {
  .camera-control-dock {
    grid-template-columns: 1fr;
  }

  .camera-joystick {
    width: clamp(168px, 46vw, 220px);
  }

  .camera-monitor-card__actions {
    justify-content: center;
  }
}

@media (max-width: 720px) {
  .camera-monitor-card__header {
    flex-direction: column;
  }

  .camera-action {
    width: 100%;
    justify-content: center;
  }
}
</style>
