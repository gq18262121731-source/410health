const $ = (id) => document.getElementById(id);

const state = {
  pc: null,
  ws: null,
  lastResult: null,
  connectSeq: 0,
};
window.__VISION_APP_STATE__ = state;

const debugState = window.__VISION_DEBUG__ || {
  overlayMode: new URLSearchParams(window.location.search).get("overlayMode") || "full",
  showRawJson: new URLSearchParams(window.location.search).get("rawJson") !== "0",
  videoSamples: [],
  rtcSamples: [],
  wsSamples: [],
  statusSamples: [],
  counters: {
    wsMessages: 0,
    statusUpdates: 0,
    rawJsonUpdates: 0,
  },
};
window.__VISION_DEBUG__ = debugState;

debugState.setOverlayMode = (mode) => {
  debugState.overlayMode = mode;
  if (mode === "off") {
    const canvas = $("overlay");
    const ctx = canvas?.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  } else if (state.lastResult) {
    drawOverlay($("overlay"), $("video"), state.lastResult);
  }
};
debugState.setRawJson = (enabled) => {
  debugState.showRawJson = Boolean(enabled);
  const box = $("statusBox");
  if (box && !debugState.showRawJson) {
    box.textContent = "Raw JSON hidden for debug";
  }
};
debugState.reset = () => {
  debugState.videoSamples = [];
  debugState.rtcSamples = [];
  debugState.wsSamples = [];
  debugState.statusSamples = [];
  debugState.counters = { wsMessages: 0, statusUpdates: 0, rawJsonUpdates: 0 };
  window.__VISION_OVERLAY_STATS__?.reset?.();
};
debugState.snapshot = () => ({
  overlayMode: debugState.overlayMode,
  showRawJson: debugState.showRawJson,
  counters: debugState.counters,
  video: summarizeVideo(debugState.videoSamples),
  rtc: summarizeRtc(debugState.rtcSamples),
  ws: summarizeSamples(debugState.wsSamples),
  status: summarizeSamples(debugState.statusSamples),
  overlay: window.__VISION_OVERLAY_STATS__?.snapshot?.() || null,
  latestVideo: debugState.videoSamples.at(-1) || null,
  latestRtc: debugState.rtcSamples.at(-1) || null,
});

const FALL_STATE_LABELS = {
  normal: "正常",
  unstable: "姿态异常",
  falling: "疑似跌倒",
  fallen_candidate: "高风险倒地",
  fallen_confirmed: "倒地确认",
  cooldown: "冷却观察",
};

const RISK_LEVEL_LABELS = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "紧急风险",
  cooldown: "观察中",
};

const BEHAVIOR_LABELS = {
  standing: "站立",
  walking: "行走",
  sitting: "坐下",
  bending: "弯腰",
  lying: "躺卧",
  unknown: "未知",
};

const IDENTITY_STATE_LABELS = {
  unbound: "未绑定",
  identifying: "识别中",
  recognized: "已识别",
};

const TRACKING_STATE_LABELS = {
  idle: "空闲",
  target_locked: "已锁定",
  target_lost: "目标丢失",
  target_reacquiring: "重新寻找",
};

function apiBase() {
  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8000";
  }
  return window.location.origin;
}

function wsBase() {
  if (window.location.protocol === "file:") {
    return "ws://127.0.0.1:8000";
  }
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
}

async function startStream() {
  const cameraId = $("cameraId").value.trim() || "camera_01";
  const rtspUrl = $("rtspUrl").value.trim() || null;
  $("startBtn").disabled = true;

  try {
    const status = await fetch(`${apiBase()}/status`).then((response) => response.json());
    const camera = (status.cameras || []).find((item) => item.camera_id === cameraId);
    if (camera?.running) {
      await fetch(`${apiBase()}/stream/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId }),
      });
    }

    const response = await fetch(`${apiBase()}/stream/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id: cameraId, rtsp_url: rtspUrl }),
    });
    const payload = await safeJson(response);
    $("statusBox").textContent = JSON.stringify(payload, null, 2);
    if (!response.ok) {
      throw new Error(payload?.detail || payload?.message || `stream start failed: ${response.status}`);
    }
  } catch (error) {
    $("statusBox").textContent = String(error);
  } finally {
    $("startBtn").disabled = false;
  }
}

async function connectWebRTC() {
  const cameraId = $("cameraId").value.trim() || "camera_01";
  const connectSeq = ++state.connectSeq;
  closeConnections();
  $("connectBtn").disabled = true;
  $("webrtcState").textContent = "connecting";
  $("wsState").textContent = "idle";

  const pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });
  state.pc = pc;

  pc.addTransceiver("video", { direction: "recvonly" });
  pc.ontrack = (event) => {
    $("video").srcObject = event.streams[0];
  };
  pc.onconnectionstatechange = () => {
    if (state.pc === pc) {
      $("webrtcState").textContent = pc.connectionState;
    }
  };

  try {
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIceGatheringComplete(pc);

    if (!isCurrentPeer(pc, connectSeq)) {
      return;
    }

    const response = await fetch(`${apiBase()}/webrtc/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        camera_id: cameraId,
        sdp: pc.localDescription.sdp,
        type: pc.localDescription.type,
      }),
    });
    const answer = await safeJson(response);
    if (!response.ok) {
      throw new Error(answer?.detail || answer?.message || `webrtc offer failed: ${response.status}`);
    }

    if (!isCurrentPeer(pc, connectSeq)) {
      return;
    }
    await pc.setRemoteDescription(answer);
    connectResults(cameraId);
  } catch (error) {
    if (state.pc === pc) {
      $("webrtcState").textContent = "failed";
      $("statusBox").textContent = String(error);
      closeConnections();
    }
  } finally {
    $("connectBtn").disabled = false;
  }
}

function isCurrentPeer(pc, connectSeq) {
  return state.pc === pc && state.connectSeq === connectSeq && pc.signalingState !== "closed";
}

function closeConnections() {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  if (state.pc) {
    state.pc.close();
    state.pc = null;
  }
}

function waitForIceGatheringComplete(pc) {
  if (pc.iceGatheringState === "complete") {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, 3000);
    const check = () => {
      if (pc.iceGatheringState === "complete") {
        clearTimeout(timer);
        pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", check);
  });
}

function connectResults(cameraId) {
  if (state.ws) {
    state.ws.close();
  }
  const ws = new WebSocket(`${wsBase()}/ws/results?camera_id=${encodeURIComponent(cameraId)}`);
  state.ws = ws;
  ws.onopen = () => {
    $("wsState").textContent = "connected";
  };
  ws.onclose = () => {
    if (state.ws === ws) {
      $("wsState").textContent = "closed";
    }
  };
  ws.onerror = () => {
    if (state.ws === ws) {
      $("wsState").textContent = "error";
    }
  };
  ws.onmessage = (event) => {
    const startedAt = performance.now();
    const result = JSON.parse(event.data);
    state.lastResult = result;
    $("frameInfo").textContent = `${result.frame_width}x${result.frame_height} #${result.frame_seq}`;
    $("personCount").textContent = `${(result.objects || []).length}`;
    $("latency").textContent = `${result.detector?.latency_ms ?? "-"} ms`;
    updateTargetDetails(result);
    drawOverlay($("overlay"), $("video"), result);
    debugState.counters.wsMessages += 1;
    pushLimited(debugState.wsSamples, {
      at: Date.now(),
      elapsedMs: performance.now() - startedAt,
      objects: (result.objects || []).length,
      frameSeq: result.frame_seq,
    });
  };
}

async function refreshStatus() {
  try {
    const startedAt = performance.now();
    const response = await fetch(`${apiBase()}/status`);
    const data = await response.json();
    const jsonStartedAt = performance.now();
    if (debugState.showRawJson) {
      $("statusBox").textContent = JSON.stringify(data, null, 2);
      debugState.counters.rawJsonUpdates += 1;
    }
    const rawJsonMs = performance.now() - jsonStartedAt;
    updateStreamState(data);
    updateMetricPanel(data);
    debugState.counters.statusUpdates += 1;
    pushLimited(debugState.statusSamples, {
      at: Date.now(),
      elapsedMs: performance.now() - startedAt,
      rawJsonMs,
      frameAgeMs: data.cameras?.[0]?.frame_age_ms ?? null,
      publishFps: data.pipeline?.result_publish_fps ?? null,
      poseFps: data.pose?.pose_fps ?? null,
    });
  } catch (error) {
    $("statusBox").textContent = String(error);
  }
}

function updateStreamState(status) {
  const cameraId = $("cameraId").value.trim() || "camera_01";
  const camera = (status.cameras || []).find((item) => item.camera_id === cameraId);
  if (!camera) {
    $("streamState").textContent = "未连接";
    return;
  }

  const age = camera.frame_age_ms == null ? "-" : `${Math.round(camera.frame_age_ms)}ms`;
  $("streamState").textContent = `${streamStateLabel(camera.stream_state)} (${age})`;
}

function streamStateLabel(streamState) {
  const labels = {
    disconnected: "未连接",
    connecting: "正在连接",
    connected: "画面正常",
    stale: "画面停滞/正在恢复",
    reconnecting: "正在重连",
  };
  return labels[streamState] || streamState;
}

function updateTargetDetails(result) {
  const objects = result.objects || [];
  const target = objects.find((item) => item.is_target === true) || objects[0];
  if (!target) {
    $("targetTrackId").textContent = "-";
    $("targetFlag").textContent = "-";
    $("targetPerson").textContent = "-";
    $("trackingState").textContent = "-";
    $("identityState").textContent = "-";
    $("behaviorState").textContent = "-";
    updateFallPreview(null);
    return;
  }

  const personLabel = target.person_id
    ? `${target.person_id}${target.person_name ? ` / ${target.person_name}` : ""}`
    : "-";
  const behavior = target.behavior;
  const behaviorLabel = behavior
    ? `${localizeBehaviorState(behavior.behavior_state)} (${formatScore(behavior.behavior_confidence)})`
    : "-";

  $("targetTrackId").textContent = target.track_id == null ? "-" : `#${target.track_id}`;
  $("targetFlag").textContent = target.is_target ? "是" : "否";
  $("targetPerson").textContent = personLabel;
  $("trackingState").textContent = localizeTrackingState(target.identity_state);
  $("identityState").textContent = localizeIdentityState(target);
  $("behaviorState").textContent = behaviorLabel;
  updateFallPreview(target);
}

function updateFallPreview(target) {
  const temporal = target?.temporal;
  const decision = target?.fall_decision;
  const alarm = target?.alarm_preview;
  const stateName = decision?.fall_state || "-";
  const risk = alarm?.risk_level || decision?.risk_level || "-";
  const probability = temporal?.fall_probability;
  const countdown = alarm?.countdown_ms ?? decision?.countdown_ms;

  $("fallState").textContent = localizeFallState(stateName);
  $("riskLevel").textContent = localizeRiskLevel(risk);
  $("fallProbability").textContent = formatProbability(probability);
  $("fallCountdown").textContent = formatCountdown(countdown);
  $("fallState").className = riskClass(risk);
  $("riskLevel").className = riskClass(risk);
}

function updateMetricPanel(status) {
  const detection = (status.detection || [])[0];
  $("detectionFps").textContent = detection?.detection_fps ?? "-";
  $("trackingFps").textContent = status.tracking?.tracking_fps ?? "-";
  $("poseFps").textContent = status.pose?.pose_fps ?? "-";
}

function formatScore(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(2);
}

function formatProbability(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function formatCountdown(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) / 1000).toFixed(1)}秒`;
}

function localizeFallState(value) {
  return FALL_STATE_LABELS[value] || value || "-";
}

function localizeRiskLevel(value) {
  return RISK_LEVEL_LABELS[value] || value || "-";
}

function localizeBehaviorState(value) {
  return BEHAVIOR_LABELS[value] || value || "-";
}

function localizeTrackingState(value) {
  return TRACKING_STATE_LABELS[value] || value || "-";
}

function localizeIdentityState(target) {
  if (!target?.person_id) {
    return IDENTITY_STATE_LABELS.unbound;
  }
  return IDENTITY_STATE_LABELS.recognized;
}

function riskClass(risk) {
  return RISK_LEVEL_LABELS[risk] ? `risk-${risk}` : "";
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (_) {
    return { status: response.status, message: response.statusText };
  }
}

function pushLimited(items, item, limit = 600) {
  items.push(item);
  if (items.length > limit) {
    items.splice(0, items.length - limit);
  }
}

function summarizeSamples(samples) {
  if (!samples.length) {
    return { count: 0 };
  }
  const elapsedValues = samples
    .map((item) => item.elapsedMs)
    .filter((value) => Number.isFinite(value));
  return {
    count: samples.length,
    avgElapsedMs: average(elapsedValues),
    maxElapsedMs: max(elapsedValues),
    firstAt: samples[0].at,
    lastAt: samples.at(-1).at,
  };
}

function summarizeRtc(samples) {
  if (!samples.length) {
    return { count: 0 };
  }
  const first = samples[0];
  const last = samples.at(-1);
  return {
    count: samples.length,
    framesDecodedDelta: diff(last.framesDecoded, first.framesDecoded),
    framesDroppedDelta: diff(last.framesDropped, first.framesDropped),
    framesReceivedDelta: diff(last.framesReceived, first.framesReceived),
    packetsLostDelta: diff(last.packetsLost, first.packetsLost),
    jitterLatest: last.jitter,
    freezeCountLatest: last.freezeCount,
    totalFreezesDurationLatest: last.totalFreezesDuration,
  };
}

function summarizeVideo(samples) {
  if (!samples.length) {
    return { count: 0 };
  }
  const first = samples[0];
  const last = samples.at(-1);
  return {
    ...summarizeSamples(samples),
    currentTimeDelta: round(diff(last.currentTime, first.currentTime)),
    totalVideoFramesDelta: diff(last.totalVideoFrames, first.totalVideoFrames),
    droppedVideoFramesDelta: diff(last.droppedVideoFrames, first.droppedVideoFrames),
    droppedVideoFramesLatest: last.droppedVideoFrames,
    totalVideoFramesLatest: last.totalVideoFrames,
    readyStateLatest: last.readyState,
    pausedLatest: last.paused,
  };
}

function average(values) {
  if (!values.length) {
    return null;
  }
  return round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function max(values) {
  if (!values.length) {
    return null;
  }
  return round(Math.max(...values));
}

function diff(last, first) {
  if (!Number.isFinite(last) || !Number.isFinite(first)) {
    return null;
  }
  return round(last - first);
}

function round(value) {
  return Math.round(Number(value) * 100) / 100;
}

function sampleVideoQuality() {
  const video = $("video");
  if (!video) {
    return;
  }
  const quality = typeof video.getVideoPlaybackQuality === "function"
    ? video.getVideoPlaybackQuality()
    : null;
  pushLimited(debugState.videoSamples, {
    at: Date.now(),
    currentTime: video.currentTime,
    readyState: video.readyState,
    paused: video.paused,
    totalVideoFrames: quality?.totalVideoFrames ?? null,
    droppedVideoFrames: quality?.droppedVideoFrames ?? null,
    corruptedVideoFrames: quality?.corruptedVideoFrames ?? null,
  });
}

async function sampleRtcStats() {
  const pc = state.pc;
  if (!pc || pc.connectionState === "closed") {
    return;
  }
  try {
    const stats = await pc.getStats();
    let sample = null;
    stats.forEach((report) => {
      if (report.type === "inbound-rtp" && (report.kind === "video" || report.mediaType === "video")) {
        sample = {
          at: Date.now(),
          framesDecoded: report.framesDecoded ?? null,
          framesDropped: report.framesDropped ?? null,
          framesReceived: report.framesReceived ?? null,
          packetsLost: report.packetsLost ?? null,
          jitter: report.jitter ?? null,
          freezeCount: report.freezeCount ?? null,
          totalFreezesDuration: report.totalFreezesDuration ?? null,
        };
      }
    });
    if (sample) {
      pushLimited(debugState.rtcSamples, sample);
    }
  } catch (_) {
    // Debug-only sampling must never affect the demo.
  }
}

$("startBtn").addEventListener("click", startStream);
$("connectBtn").addEventListener("click", connectWebRTC);
window.addEventListener("resize", () => drawOverlay($("overlay"), $("video"), state.lastResult));
setInterval(refreshStatus, 2000);
setInterval(sampleVideoQuality, 1000);
setInterval(sampleRtcStats, 1000);
refreshStatus();
