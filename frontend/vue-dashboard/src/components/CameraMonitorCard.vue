<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Camera,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Mic,
  Move,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Volume2,
  ZoomIn,
  ZoomOut,
} from "lucide-vue-next";
import {
  api,
  type CameraFallDetectionStatusResponse,
  type CameraPtzDirection,
  type CameraStatusResponse,
  type CameraStreamStatusResponse,
} from "../api/client";

const status = ref<CameraStatusResponse | null>(null);
const frameCanvas = ref<HTMLCanvasElement | null>(null);
const hasFrame = ref(false);
const loadingStatus = ref(false);
const autoRefresh = ref(true);
const streamState = ref<"connecting" | "live" | "paused" | "offline">("connecting");
const streamStatus = ref<CameraStreamStatusResponse | null>(null);
const fallStatus = ref<CameraFallDetectionStatusResponse | null>(null);
const clientFps = ref(0);
const mjpegFallback = ref(false);
const mjpegStreamSrc = ref("");
const ptzBusy = ref<CameraPtzDirection | null>(null);
const activePtz = ref<CameraPtzDirection | null>(null);
const errorMessage = ref("");
const audioNotice = ref("");
let statusTimer: number | undefined;
let streamStatusTimer: number | undefined;
let frameSocket: WebSocket | undefined;
let frameWatchdog: number | undefined;
let pendingFrame: Blob | undefined;
let renderingFrame = false;
let renderRequest: number | undefined;
let clientFpsStartedAt = performance.now();
let clientFpsFrames = 0;
let ptzStopTimer: number | undefined;

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
  if (!status.value?.ip) return "等待后端配置";
  return `${status.value.ip}:${status.value.port}${status.value.path}`;
});

const fallDetectionLabel = computed(() => {
  if (!fallStatus.value?.enabled) return "跌倒检测未启用";
  if (fallStatus.value.process_running) {
    return fallStatus.value.accuracy_preserving ? "跌倒检测在线·精度优先" : "跌倒检测在线";
  }
  if (fallStatus.value.running) return "跌倒检测启动中";
  return "跌倒检测离线";
});

const fallDetectionTone = computed(() => {
  if (!fallStatus.value?.enabled) return "neutral";
  if (fallStatus.value.process_running) return "online";
  return "offline";
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
    // Status is diagnostic only; avoid disrupting the video path.
  }
}

async function refreshFallDetectionStatus() {
  try {
    fallStatus.value = await api.getCameraFallDetectionStatus();
  } catch {
    // Model status is diagnostic; alarm delivery still comes from the backend websocket.
  }
}

function refreshFrame() {
  if (!autoRefresh.value) return;
  startCameraSocket();
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
  errorMessage.value = "实时画面暂时不可用，已保留云台控制。请确认后端和摄像头仍在同一局域网。";
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
      startMjpegFallback();
      errorMessage.value = "后端已连接，但还没有收到摄像头视频帧。请确认电脑正连接摄像头局域网，并检查 /camera/stream-status。";
    }
  }, 5000);
  frameSocket = api.cameraFrameSocket();
  frameSocket.binaryType = "blob";
  frameSocket.onmessage = (event) => {
    if (event.data instanceof Blob) {
      queueFrame(event.data);
    }
  };
  frameSocket.onerror = () => {
    streamState.value = "offline";
    startMjpegFallback();
    errorMessage.value = "后端摄像头转发暂时不可用，请确认 Windows 后端仍在运行。";
  };
  frameSocket.onclose = () => {
    const shouldReconnect = autoRefresh.value;
    frameSocket = undefined;
    if (shouldReconnect) {
      streamState.value = "connecting";
      window.setTimeout(startCameraSocket, 1600);
    }
  };
}

function startMjpegFallback() {
  if (!autoRefresh.value) return;
  mjpegStreamSrc.value = api.getCameraStreamUrl();
  mjpegFallback.value = true;
  hasFrame.value = true;
}

function handleMjpegLoaded() {
  streamState.value = "live";
  errorMessage.value = "";
}

function handleMjpegError() {
  streamState.value = "offline";
  handleFrameError();
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
    socket.close();
  }
  mjpegFallback.value = false;
  mjpegStreamSrc.value = "";
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

async function moveCamera(direction: CameraPtzDirection) {
  ptzBusy.value = direction;
  errorMessage.value = "";
  try {
    await api.moveCamera(direction);
    if (autoRefresh.value) {
      startCameraSocket();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "云台控制失败";
  } finally {
    ptzBusy.value = null;
  }
}

async function startPtz(direction: CameraPtzDirection) {
  if (direction === "stop") {
    await stopPtz();
    return;
  }

  activePtz.value = direction;
  ptzBusy.value = direction;
  errorMessage.value = "";
  if (ptzStopTimer) {
    window.clearTimeout(ptzStopTimer);
    ptzStopTimer = undefined;
  }

  try {
    await api.moveCamera(direction, "continuous");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "云台控制失败";
    activePtz.value = null;
  } finally {
    ptzBusy.value = null;
  }
}

async function stopPtz() {
  if (ptzStopTimer) {
    window.clearTimeout(ptzStopTimer);
  }
  ptzStopTimer = window.setTimeout(() => {
    ptzStopTimer = undefined;
    activePtz.value = null;
  }, 120);

  try {
    await api.moveCamera("stop", "continuous");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "云台停止失败";
  } finally {
    activePtz.value = null;
  }
}

function showAudioNotice(kind: "voice" | "talk") {
  audioNotice.value =
    kind === "voice"
      ? "远程语音会用到浏览器麦克风和摄像头扬声器通道，下一步需要确认厂商 SDK/音频接口后再开启。"
      : "监听/对讲需要摄像头音频流和上行对讲接口；我先不自动请求麦克风权限，避免误触发隐私授权。";
}

onMounted(() => {
  void refreshStatus().then(refreshFrame);
  void refreshStreamStatus();
  void refreshFallDetectionStatus();
  statusTimer = window.setInterval(refreshStatus, 8000);
  streamStatusTimer = window.setInterval(() => {
    void refreshStreamStatus();
    void refreshFallDetectionStatus();
  }, 3000);
});

onBeforeUnmount(() => {
  if (statusTimer) window.clearInterval(statusTimer);
  if (streamStatusTimer) window.clearInterval(streamStatusTimer);
  if (ptzStopTimer) window.clearTimeout(ptzStopTimer);
  if (activePtz.value) void stopPtz();
  closeCameraSocket();
});
</script>

<template>
  <article class="camera-monitor-card">
    <div class="camera-monitor-card__header">
      <div>
        <p class="section-eyebrow">Live Home Check</p>
        <h3>家中实时看护</h3>
        <p>前端只连接 Windows 后端 WebSocket，后端统一采集摄像头画面并转发，避免多个页面直连摄像头。</p>
      </div>
      <span class="camera-monitor-card__status" :class="`is-${statusTone}`">
        <ShieldCheck :size="15" />
        {{ statusLabel }}
      </span>
    </div>

    <div class="camera-monitor-card__stage">
      <div class="camera-monitor-card__viewport" :class="{ 'has-frame': hasFrame }">
        <canvas
          v-show="hasFrame && !mjpegFallback"
          ref="frameCanvas"
          class="camera-monitor-card__canvas"
          aria-label="home camera realtime video"
        />
        <img
          v-if="mjpegFallback && mjpegStreamSrc"
          class="camera-monitor-card__canvas"
          :src="mjpegStreamSrc"
          alt="home camera realtime video"
          @load="handleMjpegLoaded"
          @error="handleMjpegError"
        />
        <div v-if="!hasFrame" class="camera-monitor-card__empty">
          <Camera :size="32" />
          <span>画面已暂停</span>
        </div>
        <div class="camera-monitor-card__live-mark">
          <span />
          {{
            streamState === "live"
              ? `实收 ${clientFps.toFixed(1)}fps`
              : streamState === "paused"
                ? "已暂停"
                : streamState === "offline"
                  ? "无视频帧"
                  : "连接中"
          }}
        </div>

      </div>
    </div>

    <div class="camera-control-dock">
      <div>
        <p class="section-eyebrow">PTZ Remote</p>
        <h4>模拟摇杆</h4>
      </div>

      <div class="camera-joystick" aria-label="摄像头模拟摇杆">
        <button type="button" class="camera-joystick__zone is-up" aria-label="向上转动" v-bind="bindPtz('up')">
          <ChevronUp :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-left" aria-label="向左转动" v-bind="bindPtz('left')">
          <ChevronLeft :size="28" />
        </button>
        <button type="button" class="camera-joystick__center" aria-label="停止转动" @click="stopPtz">
          <Move :size="23" />
        </button>
        <button type="button" class="camera-joystick__zone is-right" aria-label="向右转动" v-bind="bindPtz('right')">
          <ChevronRight :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-down" aria-label="向下转动" v-bind="bindPtz('down')">
          <ChevronDown :size="28" />
        </button>
      </div>

      <div class="camera-monitor-card__zoom">
        <button type="button" :class="{ 'is-active': activePtz === 'zoom_out' }" v-bind="bindPtz('zoom_out')">
          <ZoomOut :size="16" />
          拉远
        </button>
        <button type="button" :class="{ 'is-active': activePtz === 'zoom_in' }" v-bind="bindPtz('zoom_in')">
          <ZoomIn :size="16" />
          拉近
        </button>
      </div>
    </div>

    <div class="camera-monitor-card__meta">
      <span>{{ endpointLabel }}</span>
      <span v-if="status?.latency_ms !== null && status?.latency_ms !== undefined">
        延迟 {{ status.latency_ms }}ms
      </span>
      <span v-else>局域网 RTSP</span>
      <span v-if="streamStatus">Target {{ (streamStatus.target_fps ?? 0).toFixed(1) }}fps / {{ streamStatus.profile ?? "balanced" }}</span>
      <span v-else>WebSocket /ws/camera</span>
      <span v-if="streamStatus">后端源流 {{ (streamStatus.source_fps ?? streamStatus.measured_fps ?? 0).toFixed(1) }}fps</span>
      <span v-if="streamStatus">JPEG q{{ streamStatus.jpeg_quality ?? 4 }}</span>
      <span class="camera-monitor-card__fall" :class="`is-${fallDetectionTone}`">
        {{ fallDetectionLabel }}
      </span>
      <span v-if="fallStatus?.last_event">最近事件 {{ String(fallStatus.last_event.event_type ?? "status") }}</span>
      <span>ONVIF 云台 10080</span>
    </div>

    <p v-if="errorMessage" class="camera-monitor-card__error">{{ errorMessage }}</p>
    <p v-if="audioNotice" class="camera-monitor-card__notice">{{ audioNotice }}</p>

    <div class="camera-monitor-card__actions">
      <button type="button" class="camera-action camera-action--primary" @click="toggleFrameRefresh">
        <Pause v-if="autoRefresh" :size="16" />
        <Play v-else :size="16" />
        {{ autoRefresh ? "暂停画面" : "继续查看" }}
      </button>
      <button
        type="button"
        class="camera-action"
        :disabled="loadingStatus"
        @click="
          refreshStatus();
          refreshFallDetectionStatus();
        "
      >
        <RefreshCw :size="16" />
        刷新状态
      </button>
      <button type="button" class="camera-action" @click="showAudioNotice('voice')">
        <Mic :size="16" />
        远程语音
      </button>
      <button type="button" class="camera-action" @click="showAudioNotice('talk')">
        <Volume2 :size="16" />
        监听/对讲
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
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(45, 212, 191, 0.2), transparent 28%),
    linear-gradient(145deg, rgba(240, 253, 250, 0.96), rgba(255, 255, 255, 0.98) 46%, rgba(239, 246, 255, 0.92));
  box-shadow: 0 16px 44px rgba(15, 118, 110, 0.12);
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
.camera-action,
.camera-monitor-card__live-mark,
.camera-monitor-card__zoom button {
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

.camera-monitor-card__stage {
  display: block;
}

.camera-control-dock {
  display: grid;
  grid-template-columns: minmax(120px, 0.34fr) auto minmax(180px, 0.42fr);
  gap: 14px;
  align-items: center;
  border: 1px solid rgba(13, 148, 136, 0.14);
  border-radius: 20px;
  padding: 13px 14px;
  background: rgba(255, 255, 255, 0.68);
}

.camera-control-dock h4 {
  margin: 2px 0 0;
  font-size: 1rem;
}

.camera-monitor-card__viewport {
  position: relative;
  min-height: clamp(240px, 32vw, 430px);
  overflow: hidden;
  border-radius: 19px;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.78), rgba(15, 118, 110, 0.54)),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.06) 0 1px, transparent 1px 18px);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2), 0 20px 36px rgba(15, 23, 42, 0.12);
}

.camera-monitor-card__viewport img,
.camera-monitor-card__canvas {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  object-fit: cover;
}

.camera-monitor-card__canvas {
  position: absolute;
  inset: 0;
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
  font-weight: 700;
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

.camera-joystick {
  position: relative;
  width: clamp(146px, 18vw, 188px);
  aspect-ratio: 1;
  border-radius: 999px;
  touch-action: none;
  user-select: none;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.9) 0 21%, transparent 22%),
    radial-gradient(circle at center, rgba(15, 118, 110, 0.14) 0 41%, rgba(15, 23, 42, 0.16) 42% 100%);
  box-shadow:
    inset 0 0 0 1px rgba(13, 148, 136, 0.12),
    0 18px 34px rgba(15, 118, 110, 0.12);
}

.camera-joystick__zone,
.camera-joystick__center {
  position: absolute;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  color: rgba(15, 118, 110, 0.72);
  cursor: pointer;
  touch-action: none;
  user-select: none;
  transition: transform var(--trans-base), color var(--trans-base), background var(--trans-base);
  will-change: transform;
}

.camera-joystick__zone {
  width: 36%;
  height: 36%;
  border-radius: 999px;
  background: transparent;
}

.camera-joystick__zone:hover:not(:disabled) {
  color: #0f766e;
  background: rgba(255, 255, 255, 0.46);
  transform: scale(1.04);
}

.camera-joystick__zone.is-active,
.camera-joystick__zone:active {
  color: #0f766e;
  background: rgba(255, 255, 255, 0.7);
  transform: scale(1.1);
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
  background: rgba(255, 255, 255, 0.96);
  color: rgba(15, 118, 110, 0.7);
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.14);
}

.camera-joystick__center:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.92);
  color: #0f766e;
}

.camera-joystick__center:active {
  transform: translate(-50%, -50%) scale(0.96);
}

.camera-joystick__zone:disabled,
.camera-joystick__center:disabled {
  cursor: wait;
  opacity: 0.64;
}

.camera-monitor-card__ptz {
  display: grid;
  align-content: center;
  gap: 12px;
  border: 1px solid rgba(13, 148, 136, 0.16);
  border-radius: 19px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.62);
}

.camera-monitor-card__ptz-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #0f766e;
  font-size: 0.86rem;
  font-weight: 800;
}

.ptz-pad {
  display: grid;
  grid-template-columns: repeat(3, minmax(42px, 1fr));
  gap: 8px;
}

.ptz-pad button,
.camera-monitor-card__zoom button {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  border: 1px solid rgba(13, 148, 136, 0.17);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.86);
  color: #0f766e;
  cursor: pointer;
  justify-content: center;
  font-weight: 800;
  transition: transform var(--trans-base), box-shadow var(--trans-base), background var(--trans-base);
}

.ptz-pad button {
  aspect-ratio: 1;
}

.ptz-pad button:hover:not(:disabled),
.camera-monitor-card__zoom button:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.12);
}

.camera-monitor-card__zoom button.is-active,
.camera-monitor-card__zoom button:active {
  background: #ecfeff;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.16);
  transform: translateY(-1px) scale(1.02);
}

.ptz-pad button:disabled,
.camera-monitor-card__zoom button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.camera-monitor-card__zoom {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.camera-monitor-card__ptz-hint {
  margin: 0;
  color: var(--text-sub);
  font-size: 0.78rem;
  line-height: 1.5;
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

.camera-monitor-card__fall.is-neutral {
  color: var(--text-sub);
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
}

.camera-action {
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 999px;
  padding: 9px 13px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--text-main);
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 700;
  transition: transform var(--trans-base), box-shadow var(--trans-base), background var(--trans-base);
}

.camera-action:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.12);
}

.camera-action--primary {
  border-color: transparent;
  background: #0f766e;
  color: #ffffff;
}

.camera-action--primary:hover:not(:disabled) {
  background: #115e59;
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
    justify-self: center;
    width: clamp(156px, 44vw, 210px);
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
