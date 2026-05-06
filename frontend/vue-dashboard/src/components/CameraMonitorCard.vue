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
  VolumeX,
  ZoomIn,
  ZoomOut,
} from "lucide-vue-next";
import {
  api,
  type CameraAudioStatusResponse,
  type CameraAudioStreamStatusResponse,
  type CameraFallDetectionStatusResponse,
  type CameraPtzDirection,
  type CameraStatusResponse,
  type CameraStreamStatusResponse,
} from "../api/client";
import { PcmAudioPlayer, type PcmAudioPlayerState } from "../utils/pcmAudioPlayer";

const status = ref<CameraStatusResponse | null>(null);
const streamStatus = ref<CameraStreamStatusResponse | null>(null);
const audioStatus = ref<CameraAudioStatusResponse | null>(null);
const audioStreamStatus = ref<CameraAudioStreamStatusResponse | null>(null);
const fallStatus = ref<CameraFallDetectionStatusResponse | null>(null);
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
  if (!status.value?.configured) return "Not configured";
  if (status.value.online) return "Online";
  return "Offline";
});

const statusTone = computed(() => {
  if (!status.value?.configured) return "neutral";
  return status.value.online ? "online" : "offline";
});

const endpointLabel = computed(() => {
  if (status.value?.source === "local") {
    return status.value.detail || "Local camera";
  }
  if (!status.value?.ip) return "Waiting for backend config";
  return `${status.value.ip}:${status.value.port}${status.value.path}`;
});

const fallDetectionLabel = computed(() => {
  if (!fallStatus.value?.enabled) return "Fall detection disabled";
  if (fallStatus.value.process_running) {
    return fallStatus.value.accuracy_preserving ? "Fall detection live / accuracy" : "Fall detection live";
  }
  if (fallStatus.value.running) return "Fall detection starting";
  return "Fall detection offline";
});

const fallDetectionTone = computed(() => {
  if (!fallStatus.value?.enabled) return "neutral";
  if (fallStatus.value.process_running) return "online";
  return "offline";
});

const audioListenSupported = computed(() => audioStatus.value?.listen_supported === true);

const audioCapabilityLabel = computed(() => {
  if (!audioStatus.value?.configured) return "Audio not configured";
  if (audioListenSupported.value) {
    const codec = audioStatus.value.audio_codec || "PCM";
    const sampleRate = audioStatus.value.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 0;
    return `${codec} / ${sampleRate || 0}Hz`;
  }
  return audioStatus.value?.error || "Listen unavailable";
});

const audioCapabilityTone = computed(() => {
  if (!audioStatus.value?.configured) return "neutral";
  return audioListenSupported.value ? "online" : "offline";
});

const audioActionLabel = computed(() => {
  if (audioConnecting.value) return "Connecting audio";
  if (audioListening.value) return `Stop listen (${audioLevel.value.toFixed(0)}%)`;
  return "Listen live audio";
});

const audioBrowserSupported = computed(() => {
  if (typeof window === "undefined") return false;
  return typeof window.AudioContext !== "undefined";
});

const relayFpsLabel = computed(() => {
  if (!mjpegFallback.value && clientFps.value > 0) {
    return clientFps.value.toFixed(1);
  }
  const relayFps = streamStatus.value?.source_fps ?? streamStatus.value?.measured_fps ?? 0;
  return relayFps > 0 ? relayFps.toFixed(1) : clientFps.value.toFixed(1);
});

const transportLabel = computed(() => {
  if (mjpegFallback.value) {
    return primaryStreamTransport === "mjpeg" ? "MJPEG relay" : "MJPEG fallback";
  }
  return "WebSocket fallback";
});

function formatCameraError(rawMessage: string) {
  if (!rawMessage) return "";
  if (rawMessage.includes("TimeoutExpired") || rawMessage.includes("timed out after")) {
    return "RTSP relay timed out while probing the configured camera stream. The backend will keep retrying the camera.";
  }
  if (rawMessage.includes("NETWORK_UNAVAILABLE")) {
    return "Unable to reach the backend camera service right now.";
  }
  return rawMessage.replace(/rtsp:\/\/[^@\s]+@/gi, "rtsp://***@");
}

async function refreshStatus() {
  loadingStatus.value = true;
  try {
    status.value = await api.getCameraStatus();
    if (!status.value.online && status.value.error) {
      errorMessage.value = formatCameraError(status.value.error);
    } else if (status.value.online) {
      errorMessage.value = "";
    }
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "Failed to load camera status");
  } finally {
    loadingStatus.value = false;
  }
}

async function refreshStreamStatus() {
  try {
    streamStatus.value = await api.getCameraStreamStatus();
  } catch {
    // Diagnostic only.
  }
}

async function refreshAudioStatus() {
  try {
    audioStatus.value = await api.getCameraAudioStatus();
  } catch {
    // Diagnostic only.
  }
}

async function refreshAudioStreamStatus() {
  try {
    audioStreamStatus.value = await api.getCameraAudioStreamStatus();
  } catch {
    // Diagnostic only.
  }
}

async function refreshFallDetectionStatus() {
  try {
    fallStatus.value = await api.getCameraFallDetectionStatus();
  } catch {
    // Diagnostic only.
  }
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
    await stopAudioListen({ reason: "Audio listen stopped." });
    return;
  }
  await startAudioListen();
}

async function startAudioListen() {
  audioDesired.value = true;
  audioConnecting.value = true;
  audioNotice.value = "Connecting to the camera audio relay...";

  try {
    await refreshAudioStatus();
    await refreshAudioStreamStatus();
    if (!audioListenSupported.value) {
      throw new Error(audioStatus.value?.error || "This camera is not exposing a listenable audio track.");
    }
    if (!audioBrowserSupported.value) {
      throw new Error("This browser cannot play the live PCM stream.");
    }

    const player = ensureAudioPlayer();
    await player.start(audioStatus.value?.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 8000);
    connectAudioSocket();
  } catch (error) {
    audioDesired.value = false;
    audioConnecting.value = false;
    audioListening.value = false;
    audioNotice.value = error instanceof Error ? error.message : "Failed to start live audio.";
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

  const socket = api.cameraAudioSocket();
  audioSocket = socket;
  socket.binaryType = "arraybuffer";
  socket.onopen = () => {
    audioConnecting.value = false;
    audioListening.value = true;
    const codec = audioStatus.value?.audio_codec || "PCM";
    const rate = audioStatus.value?.sample_rate ?? audioStreamStatus.value?.sample_rate ?? 8000;
    audioNotice.value = `Listening live audio via ${codec} / ${rate}Hz relay.`;
  };
  socket.onmessage = async (event) => {
    try {
      if (event.data instanceof ArrayBuffer) {
        ensureAudioPlayer().pushChunk(event.data);
      } else if (event.data instanceof Blob) {
        ensureAudioPlayer().pushChunk(await event.data.arrayBuffer());
      }
    } catch (error) {
      audioNotice.value = error instanceof Error ? error.message : "Audio playback failed.";
      await stopAudioListen({ reason: audioNotice.value });
    }
  };
  socket.onerror = () => {
    audioNotice.value = "Audio relay connection failed.";
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
  errorMessage.value = "Realtime camera stream is temporarily unavailable.";
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

  mjpegFallback.value = false;
  mjpegStreamSrc.value = "";
  streamState.value = "connecting";
  if (frameWatchdog) window.clearTimeout(frameWatchdog);
  frameWatchdog = window.setTimeout(() => {
    if (streamState.value === "connecting") {
      streamState.value = "offline";
      startMjpegFallback();
      errorMessage.value = "Connected to backend, but no video frame has arrived yet.";
    }
  }, 5000);
  const socket = api.cameraFrameSocket();
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
    errorMessage.value = "Backend camera relay is temporarily unavailable.";
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
  if (primaryStreamTransport === "websocket") {
    startCameraSocket();
    return;
  }
  startMjpegFallback();
}

function buildMjpegStreamUrl() {
  const useDetectionStream = fallStatus.value?.enabled === true;
  const baseUrl = useDetectionStream ? api.getCameraDetectionStreamUrl() : api.getCameraStreamUrl();
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
    errorMessage.value = "WebSocket relay fell behind. Switched to MJPEG relay for smoother playback.";
  }
}

function handleMjpegLoaded() {
  hasFrame.value = true;
  streamState.value = "live";
  errorMessage.value = "";
}

function handleMjpegError() {
  streamState.value = "offline";
  errorMessage.value = "MJPEG relay is temporarily unavailable. Trying WebSocket fallback...";
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
    await api.moveCamera(direction, "continuous");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "PTZ control failed");
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
    await api.moveCamera("stop", "continuous");
  } catch (error) {
    errorMessage.value = formatCameraError(error instanceof Error ? error.message : "PTZ stop failed");
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
  statusTimer = window.setInterval(refreshStatus, 8000);
  streamStatusTimer = window.setInterval(() => {
    void refreshStreamStatus();
    void refreshAudioStatus();
    void refreshAudioStreamStatus();
    void refreshFallDetectionStatus();
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
        <p class="section-eyebrow">Live Camera</p>
        <h3>Home camera monitor</h3>
        <p>The browser connects to the backend camera relay instead of opening multiple direct RTSP sessions.</p>
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
        aria-label="home camera realtime video"
      />
      <img
        v-if="mjpegFallback && mjpegStreamSrc"
        class="camera-monitor-card__canvas"
        :src="mjpegStreamSrc"
        alt="home camera realtime video"
        decoding="async"
        fetchpriority="high"
        @load="handleMjpegLoaded"
        @error="handleMjpegError"
      />
      <div v-if="!hasFrame" class="camera-monitor-card__empty">
        <Camera :size="32" />
        <span>Video paused</span>
      </div>
      <div class="camera-monitor-card__live-mark">
        <span />
        {{
          streamState === "live"
            ? `${mjpegFallback ? "Relay" : "Client"} ${relayFpsLabel}fps`
            : streamState === "paused"
              ? "Paused"
              : streamState === "offline"
                ? "Offline"
                : "Connecting"
        }}
      </div>
      <div v-if="audioListening || audioConnecting" class="camera-monitor-card__audio-mark">
        <Volume2 :size="15" />
        <span>{{ audioConnecting ? "Connecting audio" : `Live audio ${audioLevel.toFixed(0)}%` }}</span>
      </div>
    </div>

    <div class="camera-control-dock">
      <div>
        <p class="section-eyebrow">PTZ</p>
        <h4>Remote control</h4>
      </div>

      <div class="camera-joystick" aria-label="camera joystick">
        <button type="button" class="camera-joystick__zone is-up" aria-label="move up" v-bind="bindPtz('up')">
          <ChevronUp :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-left" aria-label="move left" v-bind="bindPtz('left')">
          <ChevronLeft :size="28" />
        </button>
        <button type="button" class="camera-joystick__center" aria-label="stop move" @click="stopPtz">
          <Move :size="23" />
        </button>
        <button type="button" class="camera-joystick__zone is-right" aria-label="move right" v-bind="bindPtz('right')">
          <ChevronRight :size="28" />
        </button>
        <button type="button" class="camera-joystick__zone is-down" aria-label="move down" v-bind="bindPtz('down')">
          <ChevronDown :size="28" />
        </button>
      </div>

      <div class="camera-monitor-card__zoom">
        <button type="button" :class="{ 'is-active': activePtz === 'zoom_out' }" v-bind="bindPtz('zoom_out')">
          <ZoomOut :size="16" />
          Zoom out
        </button>
        <button type="button" :class="{ 'is-active': activePtz === 'zoom_in' }" v-bind="bindPtz('zoom_in')">
          <ZoomIn :size="16" />
          Zoom in
        </button>
      </div>
    </div>

    <div class="camera-monitor-card__meta">
      <span>{{ endpointLabel }}</span>
      <span v-if="status?.source === 'local'">Source local camera</span>
      <span v-if="status?.latency_ms !== null && status?.latency_ms !== undefined">Latency {{ status.latency_ms }}ms</span>
      <span v-else>Local RTSP</span>
      <span v-if="streamStatus">Target {{ (streamStatus.target_fps ?? 0).toFixed(1) }}fps</span>
      <span v-if="streamStatus">Source {{ (streamStatus.source_fps ?? streamStatus.measured_fps ?? 0).toFixed(1) }}fps</span>
      <span v-if="streamStatus">JPEG q{{ streamStatus.jpeg_quality ?? 4 }}</span>
      <span :class="`camera-monitor-card__fall is-${audioCapabilityTone}`">{{ audioCapabilityLabel }}</span>
      <span class="camera-monitor-card__fall" :class="`is-${fallDetectionTone}`">
        {{ fallDetectionLabel }}
      </span>
    </div>

    <p v-if="errorMessage" class="camera-monitor-card__error">{{ errorMessage }}</p>
    <p v-if="audioNotice" class="camera-monitor-card__notice">{{ audioNotice }}</p>

    <div class="camera-monitor-card__actions">
      <button type="button" class="camera-action camera-action--primary" @click="toggleFrameRefresh">
        <Pause v-if="autoRefresh" :size="16" />
        <Play v-else :size="16" />
        {{ autoRefresh ? "Pause video" : "Resume video" }}
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
        "
      >
        <RefreshCw :size="16" />
        Refresh status
      </button>
    </div>

    <div class="camera-diagnostics-grid">
      <section class="camera-diagnostic-panel">
        <header>
          <p class="section-eyebrow">Video Relay</p>
          <h4>Frame transport</h4>
        </header>
        <dl>
          <div>
            <dt>Relay clients</dt>
            <dd>{{ streamStatus?.clients ?? 0 }}</dd>
          </div>
          <div>
            <dt>Transport</dt>
            <dd>{{ transportLabel }}</dd>
          </div>
          <div>
            <dt>Measured fps</dt>
            <dd>{{ relayFpsLabel }}</dd>
          </div>
          <div>
            <dt>Active URL</dt>
            <dd>{{ streamStatus?.active_url || "Waiting for stream" }}</dd>
          </div>
        </dl>
      </section>

      <section class="camera-diagnostic-panel">
        <header>
          <p class="section-eyebrow">Audio Relay</p>
          <h4>Listen diagnostics</h4>
        </header>
        <dl>
          <div>
            <dt>Browser playback</dt>
            <dd>{{ audioBrowserSupported ? "Supported" : "Unsupported" }}</dd>
          </div>
          <div>
            <dt>Relay state</dt>
            <dd>{{ audioStreamStatus?.running ? "Running" : audioListening ? "Opening" : "Idle" }}</dd>
          </div>
          <div>
            <dt>Queue</dt>
            <dd>{{ audioQueuedMs.toFixed(0) }} ms</dd>
          </div>
          <div>
            <dt>Level</dt>
            <dd class="camera-diagnostic-panel__level">
              <span class="camera-diagnostic-panel__bar">
                <span :style="{ width: `${Math.max(4, Math.min(audioLevel, 100))}%` }" />
              </span>
              {{ audioLevel.toFixed(0) }}%
            </dd>
          </div>
          <div>
            <dt>Source format</dt>
            <dd>{{ audioStatus?.audio_codec || "Unknown" }} / {{ audioStatus?.sample_rate ?? audioStreamStatus?.sample_rate ?? 0 }}Hz</dd>
          </div>
          <div>
            <dt>Buffered drops</dt>
            <dd>{{ audioDroppedBacklog }}</dd>
          </div>
          <div>
            <dt>Relay throughput</dt>
            <dd>{{ (audioStreamStatus?.kbps ?? 0).toFixed(1) }} kbps</dd>
          </div>
          <div>
            <dt>Listen clients</dt>
            <dd>{{ audioStreamStatus?.clients ?? 0 }}</dd>
          </div>
        </dl>
      </section>

      <section class="camera-diagnostic-panel">
        <header>
          <p class="section-eyebrow">Detection</p>
          <h4>Risk pipeline</h4>
        </header>
        <dl>
          <div>
            <dt>Process</dt>
            <dd>{{ fallStatus?.process_running ? "Running" : "Stopped" }}</dd>
          </div>
          <div>
            <dt>Mode</dt>
            <dd>{{ fallStatus?.speed_profile || "n/a" }}</dd>
          </div>
          <div>
            <dt>ROI</dt>
            <dd>{{ fallStatus?.roi?.enabled ? `On (${fallStatus.roi.rect || "configured"})` : "Off" }}</dd>
          </div>
          <div>
            <dt>Last event</dt>
            <dd>{{ fallStatus?.last_event_at ? new Date(fallStatus.last_event_at * 1000).toLocaleString("zh-CN", { hour12: false }) : "No event yet" }}</dd>
          </div>
        </dl>
      </section>
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

.camera-monitor-card__audio-mark {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 7px 11px;
  background: rgba(15, 23, 42, 0.62);
  color: #ecfeff;
  font-size: 0.78rem;
  font-weight: 800;
  backdrop-filter: blur(12px);
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

.camera-joystick__zone:hover:not(:disabled),
.camera-joystick__zone.is-active,
.camera-joystick__zone:active {
  color: #0f766e;
  background: rgba(255, 255, 255, 0.7);
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

.camera-monitor-card__zoom {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.camera-monitor-card__zoom button {
  min-height: 44px;
  border: 1px solid rgba(13, 148, 136, 0.17);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.86);
  color: #0f766e;
  cursor: pointer;
  justify-content: center;
  font-weight: 800;
}

.camera-monitor-card__zoom button.is-active,
.camera-monitor-card__zoom button:active {
  background: #ecfeff;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.16);
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

.camera-action {
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 999px;
  padding: 9px 13px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--text-main);
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 700;
}

.camera-action--primary {
  border-color: transparent;
  background: #0f766e;
  color: #ffffff;
}

.camera-action:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.camera-diagnostics-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.camera-diagnostic-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(13, 148, 136, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}

.camera-diagnostic-panel h4 {
  margin: 2px 0 0;
  font-size: 0.98rem;
}

.camera-diagnostic-panel dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

.camera-diagnostic-panel dl > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.camera-diagnostic-panel dt {
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 600;
}

.camera-diagnostic-panel dd {
  margin: 0;
  min-width: 0;
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 700;
  text-align: right;
  overflow-wrap: anywhere;
}

.camera-diagnostic-panel__level {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.camera-diagnostic-panel__bar {
  position: relative;
  width: 88px;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.camera-diagnostic-panel__bar > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #22c55e, #0ea5e9);
}

@media (max-width: 900px) {
  .camera-control-dock {
    grid-template-columns: 1fr;
  }

  .camera-joystick {
    justify-self: center;
    width: clamp(156px, 44vw, 210px);
  }

  .camera-diagnostics-grid {
    grid-template-columns: 1fr;
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
