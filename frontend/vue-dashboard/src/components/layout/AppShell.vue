<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { LogOut, ShieldCheck } from "lucide-vue-next";
import { api, type AlarmRecord, type FallReviewFinalizedMessage, type FallReviewPendingMessage, type SessionUser } from "../../api/client";
import { focusCommunityWorkspaceDevice } from "../../composables/useCommunityWorkspace";
import type { PageKey } from "../../composables/useHashRouting";
import CommunitySosOverlay from "./CommunitySosOverlay.vue";
import FallAlertOverlay from "./FallAlertOverlay.vue";
import GlobalHeader from "./GlobalHeader.vue";
import PrimaryNav from "./PrimaryNav.vue";
import ReviewPendingOverlay from "./ReviewPendingOverlay.vue";
import ToolEntryMenu from "./ToolEntryMenu.vue";

const props = defineProps<{
  sessionUser: SessionUser;
  activePage: PageKey;
  allowedPages: PageKey[];
  canAccessDebug: boolean;
}>();

const emit = defineEmits<{
  logout: [];
  navigate: [page: PageKey];
}>();

const activeAlarmCount = ref(0);
const activeRealtimeAlarms = ref<AlarmRecord[]>([]);
const alarmSessionStartedAt = ref(Date.now());
const simulatedAlarms = ref<AlarmRecord[]>([]); // 存储模拟告警
const acknowledgingSos = ref(false);
const acknowledgingFall = ref(false);
const manuallyAcknowledging = ref(false); // 标记是否正在手动确认告警
const pendingFallReview = ref<FallReviewPendingMessage | null>(null);
const isCommunityWorkspace = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);
const showStandaloneNav = computed(
  () => !isCommunityWorkspace.value && props.sessionUser.role !== "family" && props.allowedPages.length > 0,
);
const canShowFallOverlay = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin" || props.sessionUser.role === "family",
);
const mergedHeaderPages = new Set<PageKey>(["overview", "topology", "members", "agent"]);
const showGlobalHeader = computed(
  () => props.activePage !== "family" && (!isCommunityWorkspace.value || !mergedHeaderPages.has(props.activePage)),
);
const showMergedPageAccountBar = computed(
  () => isCommunityWorkspace.value && mergedHeaderPages.has(props.activePage),
);
const roleLabel = computed(() => {
  switch (props.sessionUser.role) {
    case "community":
      return "社区值守";
    case "family":
      return "家属查看";
    case "admin":
      return "系统管理";
    default:
      return "成员账号";
  }
});
const activeSosAlarms = computed(() =>
  activeRealtimeAlarms.value
    .filter((alarm) => !alarm.acknowledged && isRealSosAlarm(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()),
);
const primarySosAlarm = computed(() => activeSosAlarms.value[0] ?? null);
const additionalSosCount = computed(() => Math.max(0, activeSosAlarms.value.length - 1));
const activeFallAlarms = computed(() =>
  activeRealtimeAlarms.value
    .filter((alarm) => !alarm.acknowledged && isFallAlarm(alarm))
    .sort((left, right) => {
      const reviewRankDelta = fallPresentationRank(left) - fallPresentationRank(right);
      if (reviewRankDelta !== 0) return reviewRankDelta;
      if (left.alarm_level !== right.alarm_level) return left.alarm_level - right.alarm_level;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    }),
);
const presentableFallAlarms = computed(() =>
  activeFallAlarms.value.filter((alarm) => shouldPresentFallAlarm(alarm)),
);
const primaryFallAlarm = computed(() => presentableFallAlarms.value[0] ?? null);
const additionalFallCount = computed(() => Math.max(0, presentableFallAlarms.value.length - 1));
const shouldShowPendingFallReview = computed(() => {
  if (!pendingFallReview.value || !primaryFallAlarm.value) return false;
  return fallIncidentId(primaryFallAlarm.value) === pendingFallReview.value.incident_id;
});
const primaryAudibleAlarm = computed(() => {
  if (primarySosAlarm.value) return primarySosAlarm.value;
  if (primaryFallAlarm.value && isAudibleFallAlarm(primaryFallAlarm.value)) return primaryFallAlarm.value;
  return null;
});

let refreshTimer: number | null = null;
let alarmChannel: WebSocket | null = null;
let lastPresentedSosAlarmId = "";
let sosAudioElement: HTMLAudioElement | null = null;
let unlockAudioListenerBound = false;
let unlockAudioHandler: (() => void) | null = null;
const FALL_OVERLAY_SESSION_GRACE_MS = 15_000;

function isRealSosAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "sos" && !alarm.acknowledged && Boolean(alarm.metadata?.is_real_device);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isFallAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "fall_detected" || alarm.alarm_type === "fall_injury_risk";
}

function fallEvent(alarm: AlarmRecord) {
  return asRecord(alarm.metadata?.event);
}

function fallIncidentId(alarm: AlarmRecord) {
  const value = fallEvent(alarm)?.incident_id ?? alarm.metadata?.incident_id;
  return typeof value === "string" && value.trim() ? value : "";
}

function fallReview(alarm: AlarmRecord) {
  return asRecord(fallEvent(alarm)?.multimodal_review);
}

function fallReviewJudgement(alarm: AlarmRecord) {
  const value = fallReview(alarm)?.judgement;
  return typeof value === "string" && value.trim() ? value : "";
}

function fallReviewConfidence(alarm: AlarmRecord) {
  const value = fallReview(alarm)?.confidence;
  return typeof value === "string" && value.trim() ? value : "";
}

function fallReviewSuppressesStrongAlert(alarm: AlarmRecord) {
  const judgement = fallReviewJudgement(alarm);
  const confidence = fallReviewConfidence(alarm);
  const action = fallReview(alarm)?.recommended_action;
  return (
    judgement === "no_fall" &&
    ((confidence === "medium" || confidence === "high") || action === "downgrade")
  );
}

function fallReviewAction(alarm: AlarmRecord) {
  const value = fallReview(alarm)?.recommended_action;
  return typeof value === "string" && value.trim() ? value : "";
}

function fallSnapshotAvailable(alarm: AlarmRecord) {
  const path = fallEvent(alarm)?.snapshot_path;
  return typeof path === "string" && path.trim().length > 0;
}

function isSeriousFallAlarm(alarm: AlarmRecord) {
  if (alarm.alarm_level <= 2) return true;
  const event = fallEvent(alarm);
  const injury = asRecord(event?.injury);
  const injuryLevel = typeof injury?.level === "string" ? injury.level : "";
  const severity = typeof event?.severity === "string" ? event.severity : "";
  return ["I3", "I4", "I5"].includes(injuryLevel) || ["L3", "L4", "L5"].includes(severity);
}

function shouldShowFullscreenFallOverlay(alarm: AlarmRecord) {
  if (!isFallAlarm(alarm) || alarm.acknowledged) return false;
  if (!fallSnapshotAvailable(alarm)) return false;
  if (fallReviewSuppressesStrongAlert(alarm)) return false;

  const event = fallEvent(alarm);
  const state = typeof event?.state === "string" ? event.state : "";
  const judgement = fallReviewJudgement(alarm);
  const action = fallReviewAction(alarm);

  if (state === "confirmed_fall") {
    return true;
  }

  if (judgement === "fall" || action === "keep_alarm") {
    return true;
  }
  if ((judgement === "possible_fall" || judgement === "uncertain") && isSeriousFallAlarm(alarm)) {
    return true;
  }
  if (!judgement || judgement === "not_available") {
    return isSeriousFallAlarm(alarm) && ["confirmed_fall", "abnormal_recovery", "needs_assistance", "emergency"].includes(state);
  }
  return false;
}

function fallPresentationRank(alarm: AlarmRecord) {
  const judgement = fallReviewJudgement(alarm);
  if (fallReviewSuppressesStrongAlert(alarm)) return 3;
  if (judgement === "fall") return 0;
  if (judgement === "possible_fall") return 1;
  if (judgement === "uncertain") return 2;
  if (judgement === "no_fall") return 2;
  return 1;
}

function isAudibleFallAlarm(alarm: AlarmRecord) {
  if (!isFallAlarm(alarm)) return false;
  if (fallReviewSuppressesStrongAlert(alarm)) return false;
  if (alarm.alarm_level <= 2) return true;
  const event = fallEvent(alarm);
  const injury = asRecord(event?.injury);
  const injuryLevel = typeof injury?.level === "string" ? injury.level : "";
  const severity = typeof event?.severity === "string" ? event.severity : "";
  return ["I3", "I4", "I5"].includes(injuryLevel) || ["L3", "L4", "L5"].includes(severity);
}

function alarmCreatedAtMs(alarm: AlarmRecord) {
  const timestamp = new Date(alarm.created_at).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function shouldPresentFallAlarm(alarm: AlarmRecord) {
  if (!isFallAlarm(alarm) || alarm.acknowledged) return false;
  if (!shouldShowFullscreenFallOverlay(alarm)) return false;
  const createdAtMs = alarmCreatedAtMs(alarm);
  if (createdAtMs <= 0) return true;
  return createdAtMs >= alarmSessionStartedAt.value - FALL_OVERLAY_SESSION_GRACE_MS;
}

function ensureSosAudioElement() {
  if (typeof window === "undefined") return null;
  if (!sosAudioElement) {
    const element = new Audio("/sounds/sos_alarm.ogg");
    element.loop = true;
    element.preload = "auto";
    element.volume = 1;
    sosAudioElement = element;
  }
  return sosAudioElement;
}

async function startSosToneLoop() {
  const audio = ensureSosAudioElement();
  if (!audio) return;
  
  // 如果已经在播放，不要重复启动
  if (!audio.paused) {
    console.log('[SOS Audio] Already playing, skip');
    return;
  }
  
  console.log('[SOS Audio] Starting audio loop');
  audio.currentTime = 0;
  try {
    await audio.play();
  } catch (error) {
    console.log('[SOS Audio] Play failed:', error);
    // autoplay may be blocked before first interaction
  }
}

function stopSosToneLoop() {
  if (!sosAudioElement) return;
  console.log('[SOS Audio] Stopping audio loop');
  sosAudioElement.pause();
  sosAudioElement.currentTime = 0;
}

function unlockSosAudio() {
  const audio = ensureSosAudioElement();
  if (!audio) return;
  void audio.play()
    .then(() => {
      audio.pause();
      audio.currentTime = 0;
    })
    .catch(() => undefined);
}

function bindAudioUnlockListeners() {
  if (typeof window === "undefined" || unlockAudioListenerBound) return;
  unlockAudioListenerBound = true;
  unlockAudioHandler = () => {
    unlockSosAudio();
    if (unlockAudioHandler) {
      window.removeEventListener("pointerdown", unlockAudioHandler);
      window.removeEventListener("keydown", unlockAudioHandler);
      window.removeEventListener("touchstart", unlockAudioHandler);
    }
    unlockAudioListenerBound = false;
    unlockAudioHandler = null;
  };
  window.addEventListener("pointerdown", unlockAudioHandler, { once: true, passive: true });
  window.addEventListener("keydown", unlockAudioHandler, { once: true });
  window.addEventListener("touchstart", unlockAudioHandler, { once: true, passive: true });
}

function syncAlarmState(alarms: AlarmRecord[]) {
  // 过滤掉真实告警列表中的模拟告警（避免重复）
  const realAlarms = alarms.filter(alarm => !alarm.id.startsWith('sim_'));
  // 合并真实告警和模拟告警
  const allAlarms = [...realAlarms, ...simulatedAlarms.value];
  activeRealtimeAlarms.value = allAlarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  activeAlarmCount.value = activeRealtimeAlarms.value.length;
  // 处理页面导航（不处理音频，由watch统一管理）
  presentPrimaryAlarm();
}

function upsertAlarm(alarm: AlarmRecord) {
  const next = [...activeRealtimeAlarms.value];
  const index = next.findIndex((item) => item.id === alarm.id);
  if (alarm.acknowledged) {
    if (index >= 0) next.splice(index, 1);
  } else if (index >= 0) {
    next.splice(index, 1, alarm);
  } else {
    next.push(alarm);
  }
  syncAlarmState(next);
}

function mergeAlarmReviewFinalized(message: FallReviewFinalizedMessage) {
  activeRealtimeAlarms.value = activeRealtimeAlarms.value.map((alarm) => {
    if (fallIncidentId(alarm) !== message.incident_id) return alarm;
    const nextMetadata = { ...(alarm.metadata ?? {}) } as Record<string, unknown>;
    const nextEvent = { ...(asRecord(nextMetadata.event) ?? {}) };
    if (message.event && typeof message.event === "object") {
      Object.assign(nextEvent, message.event);
    }
    if (message.review && typeof message.review === "object") {
      nextEvent.multimodal_review = message.review;
    }
    nextMetadata.event = nextEvent;
    if (message.presentation && typeof message.presentation === "object") {
      nextMetadata.presentation = message.presentation;
    }
    if (message.family_guidance && typeof message.family_guidance === "object") {
      nextMetadata.family_guidance = message.family_guidance;
    }
    return {
      ...alarm,
      metadata: nextMetadata,
    };
  });
}

function presentPrimaryAlarm() {
  const current = primarySosAlarm.value ?? primaryFallAlarm.value;
  if (!isCommunityWorkspace.value || !current) {
    return;
  }
  
  // 只处理页面导航和设备聚焦，不处理音频（由watch统一管理）
  if (lastPresentedSosAlarmId !== current.id) {
    lastPresentedSosAlarmId = current.id;
    if (!current.device_mac.startsWith("CAMERA-")) {
      focusCommunityWorkspaceDevice(current.device_mac);
    }
    if (props.activePage !== "overview") {
      emit("navigate", "overview");
    }
  }
}

function stopAlarmRuntime() {
  stopSosToneLoop();
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  alarmChannel?.close();
  alarmChannel = null;
}

async function refreshAlarmState() {
  const alarms = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  syncAlarmState(alarms);
}

function connectAlarmSocket() {
  alarmChannel?.close();
  alarmChannel = null;

  alarmChannel = api.alarmSocket();
  alarmChannel.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AlarmRecord | {
        type?: string;
        queue?: Array<{ alarm?: AlarmRecord }>;
      } | FallReviewPendingMessage | FallReviewFinalizedMessage;
      if ("type" in payload && payload.type === "alarm_queue") {
        const alarms = Array.isArray(payload.queue)
          ? payload.queue
              .map((item) => item.alarm)
              .filter((item): item is AlarmRecord => Boolean(item))
          : [];
        syncAlarmState(alarms);
        return;
      }
      if ("type" in payload && payload.type === "fall_alarm_pending_review") {
        pendingFallReview.value = payload as FallReviewPendingMessage;
        return;
      }
      if ("type" in payload && payload.type === "fall_alarm_finalized") {
        mergeAlarmReviewFinalized(payload as FallReviewFinalizedMessage);
        if (pendingFallReview.value?.incident_id === (payload as FallReviewFinalizedMessage).incident_id) {
          pendingFallReview.value = null;
        }
        return;
      }
      upsertAlarm(payload as AlarmRecord);
    } catch {
      // ignore malformed websocket payloads
    }
  };
  alarmChannel.onclose = () => {
    alarmChannel = null;
    // Auto-reconnect after 2 seconds for real-time SOS delivery
    setTimeout(() => {
      connectAlarmSocket();
    }, 2000);
  };
}

function startAlarmRuntime() {
  stopAlarmRuntime();
  alarmSessionStartedAt.value = Date.now();
  void refreshAlarmState();
  connectAlarmSocket();
  refreshTimer = window.setInterval(() => {
    void refreshAlarmState();
  }, 5000);
}

// 监听SOS模拟事件
function handleSOSSimulation(event: CustomEvent) {
  if (!isCommunityWorkspace.value) return;
  
  const mockAlarm = event.detail as AlarmRecord;
  // 将模拟告警添加到模拟告警列表中，这样不会被刷新覆盖
  simulatedAlarms.value.push(mockAlarm);
  
  // 手动更新activeRealtimeAlarms，避免调用syncAlarmState导致重复
  const realAlarms = activeRealtimeAlarms.value.filter(alarm => !alarm.id.startsWith('sim_'));
  const allAlarms = [...realAlarms, ...simulatedAlarms.value];
  activeRealtimeAlarms.value = allAlarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  activeAlarmCount.value = activeRealtimeAlarms.value.length;
  
  // 处理页面导航（不处理音频，由watch统一管理）
  presentPrimaryAlarm();
}

watch(() => props.sessionUser.id, () => {
  startAlarmRuntime();
});

onMounted(() => {
  bindAudioUnlockListeners();
  startAlarmRuntime();
  
  // 添加SOS模拟事件监听器
  window.addEventListener('sos-simulation', handleSOSSimulation as EventListener);
});

onUnmounted(() => {
  stopAlarmRuntime();
  if (unlockAudioListenerBound && unlockAudioHandler) {
    window.removeEventListener("pointerdown", unlockAudioHandler);
    window.removeEventListener("keydown", unlockAudioHandler);
    window.removeEventListener("touchstart", unlockAudioHandler);
  }
  unlockAudioListenerBound = false;
  unlockAudioHandler = null;
  if (sosAudioElement) {
    sosAudioElement.pause();
    sosAudioElement.src = "";
  }
  sosAudioElement = null;
});

async function acknowledgePrimarySos() {
  const current = primarySosAlarm.value;
  if (!current) return;
  
  console.log('[SOS Acknowledge] Starting acknowledgment for:', current.id);
  
  // 标记正在手动确认，防止watch触发音频
  manuallyAcknowledging.value = true;
  acknowledgingSos.value = true;
  
  // 先停止音频
  stopSosToneLoop();
  
  try {
    // 如果是模拟告警，直接从模拟列表中移除
    if (current.id.startsWith('sim_')) {
      console.log('[SOS Acknowledge] Removing simulated alarm');
      simulatedAlarms.value = simulatedAlarms.value.filter(alarm => alarm.id !== current.id);
      // 手动更新状态
      const realAlarms = activeRealtimeAlarms.value.filter(alarm => !alarm.id.startsWith('sim_'));
      const allAlarms = [...realAlarms, ...simulatedAlarms.value];
      activeRealtimeAlarms.value = allAlarms
        .filter((alarm) => !alarm.acknowledged)
        .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
      activeAlarmCount.value = activeRealtimeAlarms.value.length;
      console.log('[SOS Acknowledge] Remaining alarms:', activeRealtimeAlarms.value.length);
    } else {
      // 真实告警通过API确认
      console.log('[SOS Acknowledge] Acknowledging real alarm via API');
      await api.ackAlarm(current.id);
      await refreshAlarmState();
    }
    lastPresentedSosAlarmId = "";
  } finally {
    acknowledgingSos.value = false;
    // 延迟重置标记，确保watch不会立即触发
    setTimeout(() => {
      console.log('[SOS Acknowledge] Resetting manual acknowledgment flag');
      manuallyAcknowledging.value = false;
    }, 100);
  }
}

async function acknowledgePrimaryFall() {
  const current = primaryFallAlarm.value;
  if (!current) return;

  manuallyAcknowledging.value = true;
  acknowledgingFall.value = true;
  stopSosToneLoop();

  try {
    activeRealtimeAlarms.value = activeRealtimeAlarms.value.filter((alarm) => alarm.id !== current.id);
    activeAlarmCount.value = activeRealtimeAlarms.value.length;
    if (pendingFallReview.value && pendingFallReview.value.incident_id === fallIncidentId(current)) {
      pendingFallReview.value = null;
    }
    await api.ackAlarm(current.id);
    await refreshAlarmState();
    lastPresentedSosAlarmId = "";
  } finally {
    acknowledgingFall.value = false;
    setTimeout(() => {
      manuallyAcknowledging.value = false;
    }, 100);
  }
}

watch(
  [primaryAudibleAlarm, isCommunityWorkspace],
  ([alarm, canRing], [oldAlarm]) => {
    console.log('[SOS Watch] Triggered', {
      alarm: alarm?.id,
      oldAlarm: oldAlarm?.id,
      canRing,
      manuallyAcknowledging: manuallyAcknowledging.value
    });
    
    // 如果正在手动确认告警，不要播放音频
    if (manuallyAcknowledging.value) {
      console.log('[SOS Watch] Skipping due to manual acknowledgment');
      return;
    }
    
    if (!canRing || !alarm) {
      console.log('[SOS Watch] Stopping audio - no alarm or not community');
      stopSosToneLoop();
      return;
    }
    
    // 只在新告警出现时播放音频（告警ID改变）
    if (alarm && (!oldAlarm || alarm.id !== oldAlarm.id)) {
      console.log('[SOS Watch] New alarm detected, starting audio');
      void startSosToneLoop();
    } else {
      console.log('[SOS Watch] Same alarm, no action');
    }
  },
  { immediate: true },
);
</script>

<template>
  <main class="app-shell" :class="{ 'app-shell--workspace': isCommunityWorkspace }">
    <aside v-if="isCommunityWorkspace" class="workspace-sidebar">
      <PrimaryNav
        v-if="allowedPages.length"
        :active-page="activePage"
        :allowed-pages="allowedPages"
        @navigate="emit('navigate', $event)"
      />

      <div class="workspace-sidebar__footer">
        <ToolEntryMenu
          v-if="canAccessDebug"
          :active-page="activePage"
          :can-access-debug="canAccessDebug"
          @navigate="emit('navigate', $event)"
        />
      </div>
    </aside>

    <div class="workspace-stage">
      <GlobalHeader
        v-if="showGlobalHeader"
        :session-user="sessionUser"
        :active-alarm-count="activeAlarmCount"
        :active-page="activePage"
        @logout="emit('logout')"
      />

      <div
        v-if="showStandaloneNav"
        class="app-shell__controls"
      >
        <PrimaryNav
          :active-page="activePage"
          :allowed-pages="allowedPages"
          @navigate="emit('navigate', $event)"
        />
        <ToolEntryMenu
          v-if="canAccessDebug"
          :active-page="activePage"
          :can-access-debug="canAccessDebug"
          @navigate="emit('navigate', $event)"
        />
      </div>

      <div class="app-shell__content">
        <div v-if="showMergedPageAccountBar" class="app-shell__account-bar">
          <div class="app-shell__user-info">
            <span class="app-shell__user-name">{{ sessionUser.name }}</span>
            <span class="app-shell__user-role">
              <ShieldCheck :size="14" />
              {{ roleLabel }}
            </span>
          </div>

          <button type="button" class="app-shell__logout-btn" @click="emit('logout')">
            <LogOut :size="16" />
            <span>退出</span>
          </button>
        </div>

        <slot />
      </div>
    </div>

    <CommunitySosOverlay
      v-if="isCommunityWorkspace"
      :alarm="primarySosAlarm"
      :additional-count="additionalSosCount"
      :acknowledging="acknowledgingSos"
      @acknowledge="acknowledgePrimarySos"
    />
    <FallAlertOverlay
      v-if="canShowFallOverlay && (!isCommunityWorkspace || !primarySosAlarm)"
      :alarm="primaryFallAlarm"
      :additional-count="additionalFallCount"
      :acknowledging="acknowledgingFall"
      @acknowledge="acknowledgePrimaryFall"
    />
    <ReviewPendingOverlay
      :visible="Boolean(canShowFallOverlay && shouldShowPendingFallReview)"
      :title="pendingFallReview?.title"
      :lead="pendingFallReview?.lead"
      :expected-seconds="pendingFallReview?.expected_seconds ?? null"
    />
  </main>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  width: 100%;
  background: var(--bg-base);
}

.app-shell--workspace {
  display: flex;
  min-height: 100vh;
  overflow: visible;
}

.workspace-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 12px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border-right: 1px solid #e2e8f0;
  overflow: hidden;
  z-index: 100;
}

.workspace-sidebar__footer {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.workspace-stage {
  flex: 1;
  margin-left: 260px;
  width: calc(100% - 260px);
  min-height: 100vh;
  overflow-y: visible;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 14px 20px 32px;
}

.app-shell__controls {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.app-shell__content {
  flex: 1;
  width: 100%;
  min-height: 0;
  position: relative;
}

.app-shell__account-bar {
  position: absolute;
  top: 22px;
  right: 22px;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.app-shell__user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(14px);
}

.app-shell__user-name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.app-shell__user-role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
}

.app-shell__logout-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 1px solid #dbe4f0;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  color: #64748b;
  font-size: 0.92rem;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(14px);
  cursor: pointer;
  transition: all 180ms ease;
}

.app-shell__logout-btn:hover {
  color: #ffffff;
  background: #ef4444;
  border-color: #ef4444;
}

.app-shell__logout-btn:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 2px;
}

@media (max-width: 960px) {
  .app-shell--workspace {
    flex-direction: column;
    height: auto;
    overflow: visible;
  }

  .workspace-sidebar {
    position: static;
    width: 100%;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }

  .workspace-stage {
    margin-left: 0;
    width: 100%;
    height: auto;
    overflow: visible;
  }

  .app-shell__account-bar {
    position: static;
    justify-content: flex-end;
    margin-bottom: 14px;
  }
}
</style>
