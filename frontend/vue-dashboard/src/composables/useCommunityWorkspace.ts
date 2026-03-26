import { computed, onMounted, onUnmounted, ref, watch, type ComputedRef, type Ref } from "vue";
import {
  api,
  type AlarmRecord,
  type CommunityDashboardDeviceItem,
  type CommunityDashboardSummary,
  type CommunityRelationTopology,
  type HealthSample,
  type SessionUser,
} from "../api/client";
import { getStoredSessionToken } from "./useSessionAuth";

export const SELECTED_DEVICE_STORAGE_KEY = "community-workspace-selected-device";

const summary = ref<CommunityDashboardSummary | null>(null);
const dashboardLoading = ref(false);
const dashboardLoadError = ref("");
const selectedDeviceMac = ref("");
const lastSyncAt = ref<Date | null>(null);
const latestByDevice = ref<Record<string, HealthSample>>({});
const trendStore = ref<Record<string, HealthSample[]>>({});
const trendWindowMinutes = ref(60);

let activeConsumers = 0;
let dashboardTimer: number | null = null;
let trendTimer: number | null = null;
let healthSocket: WebSocket | null = null;
let alarmSocket: WebSocket | null = null;
let runtimeUserId = "";
let trendRuntimeVersion = 0;
let serialTargetSyncVersion = 0;
let alarmReconnectTimer: number | null = null;
let alarmReconnectAttempts = 0;

const activeAlarms = ref<AlarmRecord[]>([]);
const sosAlarmQueue = ref<AlarmRecord[]>([]);

type SerialSelectionGate = {
  deviceMac: string;
  switchedAtMs: number;
  hasFreshSample: boolean;
};

const DISPLAY_READY_SERIAL_PACKET_TYPES = new Set(["response_ab", "response_a", "response_a_only", "broadcast", "legacy_response", "legacy_response_a", "legacy_response_b"]);

const serialSelectionGate = ref<SerialSelectionGate | null>(null);

const community = computed(() => summary.value?.community ?? null);
const metrics = computed(() => summary.value?.metrics ?? null);
const topRiskElders = computed(() => summary.value?.top_risk_elders ?? []);
const deviceStatuses = computed(() => summary.value?.device_statuses ?? []);
const recentAlerts = computed(() => summary.value?.recent_alerts ?? []);
const scoreTrend = computed(() => summary.value?.trend ?? []);
const relationTopology = computed(() => summary.value?.relation_topology ?? null);
const focusLatest = computed(() =>
  selectedDeviceMac.value ? latestByDevice.value[selectedDeviceMac.value] ?? null : null,
);
const focusTrend = computed(() => trendStore.value[selectedDeviceMac.value] ?? []);
const selectedDevice = computed<CommunityDashboardDeviceItem | null>(
  () => deviceStatuses.value.find((item) => item.device_mac === selectedDeviceMac.value) ?? null,
);
const selectedStructured = computed(() => selectedDevice.value?.structured_health ?? null);
const isAwaitingSelectedRealtime = computed(
  () => false
);

function getDeviceByMac(mac: string): CommunityDashboardDeviceItem | null {
  return deviceStatuses.value.find((item) => item.device_mac === mac) ?? null;
}

function isSerialDevice(mac: string) {
  return getDeviceByMac(mac)?.ingest_mode === "serial";
}

function getSerialGate(mac: string): SerialSelectionGate | null {
  const gate = serialSelectionGate.value;
  if (!gate || gate.deviceMac !== mac) return null;
  return gate;
}

function sampleTimestampMs(sample: Pick<HealthSample, "timestamp">) {
  return new Date(sample.timestamp).getTime();
}

function mergeTrendPoints(samples: HealthSample[]) {
  return [...samples]
    .sort((left, right) => sampleTimestampMs(left) - sampleTimestampMs(right))
    .filter((item, index, array) => index === 0 || item.timestamp !== array[index - 1].timestamp);
}

/**
 * 对连续相同值的样本进行稀疏化：
 * 如果连续超过 N 个点的核心指标完全相同，只保留首尾，
 * 这样图表不会显示为"水平直线"而是正常曲线。
 */
function sparseDeduplicateSamples(samples: HealthSample[], maxFlatRun = 10): HealthSample[] {
  if (samples.length <= 2) return samples;
  const result: HealthSample[] = [samples[0]];
  let runStart = 0;
  for (let i = 1; i < samples.length; i++) {
    const prev = samples[i - 1];
    const curr = samples[i];
    const isSameValue =
      curr.heart_rate === prev.heart_rate &&
      curr.blood_oxygen === prev.blood_oxygen &&
      Math.abs(curr.temperature - prev.temperature) < 0.05;
    if (!isSameValue) {
      runStart = i;
      result.push(curr);
    } else {
      const runLength = i - runStart;
      if (runLength >= maxFlatRun) {
        // only keep every maxFlatRun-th duplicate to show the flat but not excessively
        if (runLength % maxFlatRun === 0) result.push(curr);
      } else {
        result.push(curr);
      }
    }
  }
  // Always include the last sample
  const last = samples[samples.length - 1];
  if (result[result.length - 1]?.timestamp !== last.timestamp) {
    result.push(last);
  }
  return result;
}

function isDisplayReadySample(sample: HealthSample | null | undefined, ingestMode?: string | null): sample is HealthSample {
  if (!sample) return false;
  if (ingestMode === "serial" || sample.source === "serial") {
    // 串口模式：收到什么参数就更新什么参数，缺失字段由后端回填上一时刻值。
    if (sample.packet_type && !DISPLAY_READY_SERIAL_PACKET_TYPES.has(sample.packet_type)) return false;
    if (sample.heart_rate <= 0 || sample.blood_oxygen <= 0 || sample.temperature <= 0) return false;
    return true;
  }
  if (sample.heart_rate <= 0 || sample.blood_oxygen <= 0 || sample.temperature <= 30) return false;
  return true;
}

function samplePassesSelectionGate(...args: [HealthSample, string]) {
  void args;
  // Always allow samples to pass through immediately for faster real-time curve rendering
  return true;
}

function markFreshSerialSample(mac: string, sample: HealthSample) {
  const gate = getSerialGate(mac);
  if (!gate || gate.hasFreshSample) return;
  // Mark fresh as soon as any post-switch sample passes the time gate.
  if (sampleTimestampMs(sample) >= gate.switchedAtMs) {
    serialSelectionGate.value = { ...gate, hasFreshSample: true };
  }
}

function shouldAcceptSample(sample: HealthSample, mac: string, ingestMode?: string | null) {
  return isDisplayReadySample(sample, ingestMode);
}

function buildSnapshotSample(device: CommunityDashboardDeviceItem | null): HealthSample | null {
  if (!device) return null;
  const candidate: HealthSample = {
    device_mac: device.device_mac,
    timestamp: device.latest_timestamp ?? new Date().toISOString(),
    heart_rate: device.heart_rate ?? 0,
    temperature: device.temperature ?? 0,
    blood_oxygen: device.blood_oxygen ?? 0,
    blood_pressure: device.blood_pressure ?? undefined,
    battery: device.battery ?? undefined,
    steps: device.steps ?? undefined,
    health_score: device.latest_health_score ?? undefined,
    sos_flag: false,
  };
  return isDisplayReadySample(candidate, device.ingest_mode) ? candidate : null;
}

const selectedMonitorSamples = computed<HealthSample[]>(() => {
  const ingestMode = selectedDevice.value?.ingest_mode ?? null;
  const selectedMac = selectedDeviceMac.value;
  // serial 设备心率/血氧变化缓慢，不做稀疏化，避免曲线出现间隙
  const flatRunLimit = ingestMode === "serial" ? 99999 : 10;
  const displayReadyTrend = focusTrend.value.filter((sample) => isDisplayReadySample(sample, ingestMode));
  const validTrend = displayReadyTrend;
  
  if (ingestMode === "serial") {
    if (validTrend.length >= 1) return sparseDeduplicateSamples(validTrend, flatRunLimit);
    return [];
  }
  if (validTrend.length) {
    return sparseDeduplicateSamples(validTrend, flatRunLimit);
  }

  if (focusLatest.value && shouldAcceptSample(focusLatest.value, selectedMac, ingestMode)) {
    if (displayReadyTrend.length) {
      return sparseDeduplicateSamples(mergeTrendPoints([...displayReadyTrend, focusLatest.value]).slice(-120), flatRunLimit);
    }
    return [focusLatest.value];
  }

  if (displayReadyTrend.length) {
    return sparseDeduplicateSamples(displayReadyTrend.slice(-120), flatRunLimit);
  }

  const snapshot = buildSnapshotSample(selectedDevice.value);
  if (!snapshot) {
    return [];
  }
  return [snapshot];
});

const selectedMonitorCurrentSample = computed<HealthSample | null>(() => {
  const ingestMode = selectedDevice.value?.ingest_mode ?? null;
  const selectedMac = selectedDeviceMac.value;
  if (focusLatest.value && shouldAcceptSample(focusLatest.value, selectedMac, ingestMode)) {
    return focusLatest.value;
  }
  const samples = selectedMonitorSamples.value;
  return samples.length ? samples[samples.length - 1] : null;
});

function persistSelectedDevice(mac: string) {
  const unchanged = selectedDeviceMac.value === mac;
  selectedDeviceMac.value = mac;
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(SELECTED_DEVICE_STORAGE_KEY, mac);
  }
  if (unchanged && activeConsumers > 0 && mac && isSerialDevice(mac)) {
    void handleSelectedDeviceChange(mac);
  }
}

export function focusCommunityWorkspaceDevice(mac: string) {
  if (!mac) return;
  persistSelectedDevice(mac);
}

function restoreSelectedDevice() {
  if (typeof window === "undefined") return;
  const stored = window.sessionStorage.getItem(SELECTED_DEVICE_STORAGE_KEY);
  if (stored) selectedDeviceMac.value = stored;
}

function stopDashboardPolling() {
  if (dashboardTimer !== null) {
    window.clearInterval(dashboardTimer);
    dashboardTimer = null;
  }
}

function stopTrendRuntime() {
  trendRuntimeVersion += 1;
  if (trendTimer !== null) {
    window.clearInterval(trendTimer);
    trendTimer = null;
  }
  healthSocket?.close();
  healthSocket = null;
}

function stopWorkspaceRuntime() {
  stopDashboardPolling();
  stopTrendRuntime();
  stopAlarmSocket();
}

function stopAlarmSocket() {
  if (alarmReconnectTimer !== null) {
    window.clearTimeout(alarmReconnectTimer);
    alarmReconnectTimer = null;
  }
  alarmSocket?.close();
  alarmSocket = null;
}

function connectAlarmSocket() {
  stopAlarmSocket();
  const WS_BASE = (typeof window !== "undefined")
    ? window.location.origin.replace(/^http/, "ws")
    : "ws://localhost:8000";
  // 如果 API_BASE 不是 localhost，用配置的后端地址
  const apiBase = (window as Window & { __API_BASE__?: string }).__API_BASE__ ?? "";
  const wsBase = apiBase
    ? apiBase.replace(/^http/, "ws").replace(/\/api\/v1$/, "")
    : WS_BASE;
  try {
    alarmSocket = new WebSocket(`${wsBase}/ws/alarms`);
    alarmSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>;
        if (data["type"] === "alarm_queue") {
          const queue = (data["queue"] as AlarmRecord[]) ?? [];
          activeAlarms.value = queue;
          const sosList = queue.filter((a) => a.alarm_type === "sos" && !a.acknowledged);
          for (const sos of sosList) {
            if (!sosAlarmQueue.value.some((s) => s.id === sos.id)) {
              sosAlarmQueue.value = [...sosAlarmQueue.value, sos];
            }
          }
        } else if (data["id"] && data["alarm_type"]) {
          const alarm = data as unknown as AlarmRecord;
          const idx = activeAlarms.value.findIndex((a) => a.id === alarm.id);
          if (idx !== -1) {
            activeAlarms.value = activeAlarms.value.map((a, i) => i === idx ? alarm : a);
          } else {
            activeAlarms.value = [alarm, ...activeAlarms.value];
          }
          if (alarm.alarm_type === "sos" && !alarm.acknowledged) {
            if (!sosAlarmQueue.value.some((s) => s.id === alarm.id)) {
              sosAlarmQueue.value = [...sosAlarmQueue.value, alarm];
            }
          }
        }
      } catch { /* ignore malformed */ }
    };
    alarmSocket.onclose = () => {
      if (activeConsumers > 0) {
        const delay = Math.min(1000 * (1 << alarmReconnectAttempts), 30000);
        alarmReconnectAttempts += 1;
        alarmReconnectTimer = window.setTimeout(connectAlarmSocket, delay);
      }
    };
    alarmSocket.onopen = () => { alarmReconnectAttempts = 0; };
  } catch { /* ignore in SSR */ }
}

function dismissSosAlarm(id: string) {
  sosAlarmQueue.value = sosAlarmQueue.value.filter((a) => a.id !== id);
}

function updateLatestFromDevices(list: CommunityDashboardDeviceItem[]) {
  const nextLatest = { ...latestByDevice.value };
  for (const device of list) {
    const snapshot = buildSnapshotSample(device);
    if (!snapshot) continue;
    if (!samplePassesSelectionGate(snapshot, device.device_mac)) continue;
    const existing = nextLatest[device.device_mac];
    if (!existing || sampleTimestampMs(snapshot) >= sampleTimestampMs(existing)) {
      nextLatest[device.device_mac] = snapshot;
    }
  }
  latestByDevice.value = nextLatest;
}

async function refreshDashboardData() {
  const token = getStoredSessionToken();
  if (!token) {
    summary.value = null;
    dashboardLoadError.value = "当前登录状态已失效，请重新登录。";
    return;
  }

  dashboardLoading.value = true;
  dashboardLoadError.value = "";
  try {
    const data = await api.getCommunityDashboard(token);
    summary.value = data;
    updateLatestFromDevices(data.device_statuses);

    const visibleDeviceMacs = new Set(data.device_statuses.map((item) => item.device_mac));
    if (!selectedDeviceMac.value || !visibleDeviceMacs.has(selectedDeviceMac.value)) {
      persistSelectedDevice(
        data.top_risk_elders.find((item) => item.device_mac)?.device_mac
          ?? data.device_statuses[0]?.device_mac
          ?? "",
      );
    }

    lastSyncAt.value = data.metrics.last_sync_at ? new Date(data.metrics.last_sync_at) : new Date();
    if (
      activeConsumers > 0
      && selectedDeviceMac.value
      && isSerialDevice(selectedDeviceMac.value)
      && getSerialGate(selectedDeviceMac.value) === null
    ) {
      void handleSelectedDeviceChange(selectedDeviceMac.value);
    }
  } catch (error) {
    summary.value = null;
    dashboardLoadError.value = error instanceof Error ? error.message : "社区工作台数据加载失败，请稍后重试。";
  } finally {
    dashboardLoading.value = false;
  }
}

async function refreshRealtime(mac = selectedDeviceMac.value) {
  if (!mac) return;
  const sample = await api.getRealtime(mac).catch(() => null as HealthSample | null);
  if (!sample) return;
  const ingestMode = getDeviceByMac(mac)?.ingest_mode ?? null;
  if (!shouldAcceptSample(sample, mac, ingestMode)) return;
  markFreshSerialSample(mac, sample);
  latestByDevice.value = { ...latestByDevice.value, [mac]: sample };
}

async function refreshTrend(mac = selectedDeviceMac.value, minutes = trendWindowMinutes.value) {
  if (!mac) return;
  const ingestMode = getDeviceByMac(mac)?.ingest_mode ?? null;
  const trend = await api.getTrend(mac, minutes, 120).catch(() => [] as HealthSample[]);
  const displayReady = trend.filter((sample) => isDisplayReadySample(sample, ingestMode));
  const gate = getSerialGate(mac);
  // For serial devices with an active gate, only keep post-switch samples in the store.
  // This ensures the chart never shows pre-switch data after a device switch.
  const storeSamples = gate
    ? displayReady.filter((sample) => sampleTimestampMs(sample) >= gate.switchedAtMs)
    : displayReady;
  const gated = storeSamples.filter((sample) => samplePassesSelectionGate(sample, mac));
  if (gated.length) {
    markFreshSerialSample(mac, gated[gated.length - 1]);
    latestByDevice.value = { ...latestByDevice.value, [mac]: gated[gated.length - 1] };
  }
  trendStore.value = { ...trendStore.value, [mac]: storeSamples.slice(-120) };
}

function connectHealthSocket(mac: string) {
  healthSocket?.close();
  healthSocket = null;
  if (!mac) return;

  healthSocket = api.healthSocket(mac);
  healthSocket.onmessage = (event) => {
    try {
      const sample = JSON.parse(event.data) as HealthSample;
      const ingestMode = getDeviceByMac(sample.device_mac)?.ingest_mode ?? null;
      if (!shouldAcceptSample(sample, sample.device_mac, ingestMode)) return;
      markFreshSerialSample(sample.device_mac, sample);
      latestByDevice.value = { ...latestByDevice.value, [sample.device_mac]: sample };
      const gate = getSerialGate(sample.device_mac);
      const previous = (trendStore.value[sample.device_mac] ?? []).filter(
        (s) => !gate || sampleTimestampMs(s) >= gate.switchedAtMs,
      );
      const merged = mergeTrendPoints([...previous, sample]);
      trendStore.value = { ...trendStore.value, [sample.device_mac]: merged.slice(-240) };
    } catch {
      // keep runtime stable on malformed socket payloads
    }
  };
}

async function syncSelectedSerialTarget(mac: string) {
  if (!mac) {
    serialSelectionGate.value = null;
    return;
  }
  const device = getDeviceByMac(mac);
  if (!device || device.ingest_mode !== "serial") {
    serialSelectionGate.value = null;
    return;
  }

  const token = getStoredSessionToken();
  if (!token) return;

  const version = ++serialTargetSyncVersion;
  const result = await api.switchSerialTarget({ mac_address: mac }, token).catch(() => null);
  if (!result || version !== serialTargetSyncVersion || selectedDeviceMac.value !== mac) return;

  serialSelectionGate.value = {
    deviceMac: mac,
    switchedAtMs: new Date(result.switched_at).getTime(),
    hasFreshSample: false,
  };
}

async function startTrendRuntime() {
  stopTrendRuntime();
  const mac = selectedDeviceMac.value;
  if (!mac) return;
  const runtimeVersion = ++trendRuntimeVersion;

  connectHealthSocket(mac);
  await Promise.all([refreshRealtime(mac), refreshTrend(mac)]);
  if (runtimeVersion !== trendRuntimeVersion || selectedDeviceMac.value !== mac) return;
  trendTimer = window.setInterval(() => {
    void refreshRealtime(mac);
    void refreshTrend(mac);
  }, 8000);
}

async function handleSelectedDeviceChange(mac: string) {
  if (!mac) {
    serialSelectionGate.value = null;
    stopTrendRuntime();
    return;
  }
  if (isSerialDevice(mac)) {
    // Clear trend so the chart starts fresh from the moment of switch.
    // Any samples older than switchedAtMs will be excluded by samplePassesSelectionGate.
    trendStore.value = { ...trendStore.value, [mac]: [] };
    latestByDevice.value = { ...latestByDevice.value, [mac]: undefined as unknown as HealthSample };
  }
  await syncSelectedSerialTarget(mac);
  if (activeConsumers > 0) {
    await startTrendRuntime();
  }
}

function startDashboardPolling() {
  stopDashboardPolling();
  void refreshDashboardData();
  dashboardTimer = window.setInterval(() => {
    void refreshDashboardData();
  }, 15000);
}

function startWorkspaceRuntime(sessionUser: SessionUser | null) {
  if (!sessionUser || (sessionUser.role !== "community" && sessionUser.role !== "admin")) return;
  runtimeUserId = sessionUser.id;
  restoreSelectedDevice();
  startDashboardPolling();
  void startTrendRuntime();
  connectAlarmSocket();
}

export type CommunityWorkspaceState = {
  activeAlarms: Ref<AlarmRecord[]>;
  community: ComputedRef<CommunityDashboardSummary["community"] | null>;
  dashboardLoadError: Ref<string>;
  dashboardLoading: Ref<boolean>;
  deviceStatuses: ComputedRef<CommunityDashboardDeviceItem[]>;
  dismissSosAlarm: (id: string) => void;
  focusLatest: ComputedRef<HealthSample | null>;
  focusTrend: ComputedRef<HealthSample[]>;
  isAwaitingSelectedRealtime: ComputedRef<boolean>;
  lastSyncAt: Ref<Date | null>;
  latestByDevice: Ref<Record<string, HealthSample>>;
  metrics: ComputedRef<CommunityDashboardSummary["metrics"] | null>;
  recentAlerts: ComputedRef<CommunityDashboardSummary["recent_alerts"]>;
  refreshDashboardData: () => Promise<void>;
  refreshTrend: (mac?: string, minutes?: number) => Promise<void>;
  relationTopology: ComputedRef<CommunityRelationTopology | null | undefined>;
  scoreTrend: ComputedRef<CommunityDashboardSummary["trend"]>;
  selectedDevice: ComputedRef<CommunityDashboardDeviceItem | null>;
  selectedDeviceMac: Ref<string>;
  selectedMonitorCurrentSample: ComputedRef<HealthSample | null>;
  selectedMonitorSamples: ComputedRef<HealthSample[]>;
  selectedStructured: ComputedRef<CommunityDashboardDeviceItem["structured_health"] | null>;
  setSelectedDeviceMac: (mac: string) => void;
  sosAlarmQueue: Ref<AlarmRecord[]>;
  summary: Ref<CommunityDashboardSummary | null>;
  topRiskElders: ComputedRef<CommunityDashboardSummary["top_risk_elders"]>;
  trendStore: Ref<Record<string, HealthSample[]>>;
  trendWindowMinutes: Ref<number>;
};

export function useCommunityWorkspace(sessionUser: Ref<SessionUser | null>): CommunityWorkspaceState {
  watch(
    () => sessionUser.value?.id ?? "",
    (nextId) => {
      if (!nextId) {
        runtimeUserId = "";
        stopWorkspaceRuntime();
        summary.value = null;
        latestByDevice.value = {};
        trendStore.value = {};
        serialSelectionGate.value = null;
        return;
      }

      if (nextId !== runtimeUserId && activeConsumers > 0) {
        startWorkspaceRuntime(sessionUser.value);
      }
    },
    { immediate: true },
  );

  watch(selectedDeviceMac, (mac) => {
    persistSelectedDevice(mac);
    void handleSelectedDeviceChange(mac);
  });

  onMounted(() => {
    activeConsumers += 1;
    if (activeConsumers === 1) {
      startWorkspaceRuntime(sessionUser.value);
    } else if (selectedDeviceMac.value) {
      void startTrendRuntime();
    }
  });

  onUnmounted(() => {
    activeConsumers = Math.max(0, activeConsumers - 1);
    if (activeConsumers === 0) {
      stopWorkspaceRuntime();
    }
  });

  return {
    activeAlarms,
    community,
    dashboardLoadError,
    dashboardLoading,
    deviceStatuses,
    dismissSosAlarm,
    focusLatest,
    focusTrend,
    isAwaitingSelectedRealtime,
    lastSyncAt,
    latestByDevice,
    metrics,
    recentAlerts,
    refreshDashboardData,
    refreshTrend,
    relationTopology,
    scoreTrend,
    selectedDevice,
    selectedDeviceMac,
    selectedMonitorCurrentSample,
    selectedMonitorSamples,
    selectedStructured,
    setSelectedDeviceMac: persistSelectedDevice,
    sosAlarmQueue,
    summary,
    topRiskElders,
    trendStore,
    trendWindowMinutes,
  };
}
