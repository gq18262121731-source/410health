<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  ApiError,
  api,
  type AgentDeviceHealthReport,
  type AlarmRecord,
  type CareAccessProfile,
  type CareDirectory,
  type CareHealthEvaluationSummary,
  type CareHealthReportSummary,
  type DeviceBindLogRecord,
  type DeviceRecord,
  type HealthSample,
  type SessionUser,
} from "./api/client";
import { useHashRouting } from "./composables/useHashRouting";
import { useRelationActions } from "./composables/useRelationActions";
import { useSessionAuth } from "./composables/useSessionAuth";
import { evaluateRisk, riskLabel, riskWeight, type RiskLevel } from "./domain/careModel";
import AccessDeniedPage from "./views/AccessDeniedPage.vue";
import CommunityPage from "./views/CommunityPage.vue";
import DebugPage from "./views/DebugPage.vue";
import FamilyPage from "./views/FamilyPage.vue";
import LoginPage from "./views/LoginPage.vue";
import MemberDevicePage from "./views/MemberDevicePage.vue";

interface ElderRow {
  id: string;
  name: string;
  apartment: string;
  deviceMac: string;
  familyNames: string;
  risk: RiskLevel;
  sample: HealthSample | null;
  score: number;
}

interface DebugRow {
  mac: string;
  deviceName: string;
  status: string;
  sample: HealthSample | null;
}

type DemoTone = "neutral" | "stable" | "warning" | "critical";

interface SnapshotMetric {
  id: string;
  shortLabel: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  tone: DemoTone;
}

const {
  authAccounts,
  authError,
  authLoading,
  fillMockAccount,
  isLoggedIn,
  loadMockAccounts,
  login,
  loginHelperAccount,
  loginPassword,
  loginUsername,
  logoutSession,
  restoreSession,
  sessionUser,
} = useSessionAuth();

const {
  activePage,
  allowedPages,
  canAccessDebug,
  disposeHashRouting,
  initHashRouting,
  resetToDefaultPage,
  routeTo,
} = useHashRouting(sessionUser);

const directory = ref<CareDirectory | null>(null);
const devices = ref<DeviceRecord[]>([]);
const latest = ref<Record<string, HealthSample>>({});
const alarms = ref<AlarmRecord[]>([]);
const trendStore = ref<Record<string, HealthSample[]>>({});
const selectedFamilyId = ref("");
const selectedDeviceMac = ref("");
const trendWindowMinutes = ref(180);
const lastSyncAt = ref<Date | null>(null);
const accessProfile = ref<CareAccessProfile | null>(null);
const dashboardLoading = ref(false);
const dashboardLoadError = ref("");
const deviceHistoryMac = ref("");
const bindHistory = ref<DeviceBindLogRecord[]>([]);
const bindHistoryLoading = ref(false);
const bindHistoryError = ref("");
const deletingMac = ref("");
const lastDeletedDeviceMac = ref("");
const generatedHealthReport = ref<AgentDeviceHealthReport | null>(null);
const reportLoading = ref(false);
const reportError = ref("");

const deviceModes = ["register", "bind", "rebind", "unbind"] as const;

let refreshTimer: number | null = null;
let healthSocket: WebSocket | null = null;

const community = computed(() => directory.value?.community ?? null);
const elders = computed(() => directory.value?.elders ?? []);
const allFamilies = computed(() => directory.value?.families ?? []);
const families = computed(() =>
  sessionUser.value?.role === "family"
    ? allFamilies.value.filter((family) => family.id === sessionUser.value?.family_id)
    : allFamilies.value,
);
const selectedFamily = computed(() =>
  families.value.find((family) => family.id === selectedFamilyId.value) ?? families.value[0] ?? null,
);
const elderRows = computed<ElderRow[]>(() =>
  elders.value
    .map((elder) => {
      const deviceMac = elder.device_macs?.[0] ?? elder.device_mac ?? "";
      const sample = deviceMac ? latest.value[deviceMac] ?? null : null;
      const risk = evaluateRisk(
        sample,
        deviceMac ? (devices.value.find((device) => device.mac_address === deviceMac)?.status ?? "unknown") : "unbound",
      );
      const familyNames = elder.family_ids
        .map((id) => allFamilies.value.find((family) => family.id === id)?.name)
        .filter(Boolean)
        .join(" / ");
      const score = riskWeight(risk) * 100 + (sample ? Math.max(0, 100 - Math.round(sample.health_score ?? 80)) : 12);
      return { id: elder.id, name: elder.name, apartment: elder.apartment, deviceMac, familyNames, risk, sample, score };
    })
    .sort((left, right) => right.score - left.score),
);
const visibleRows = computed(() =>
  sessionUser.value?.role === "family" && selectedFamily.value
    ? elderRows.value.filter((row) => new Set(selectedFamily.value.elder_ids ?? []).has(row.id))
    : elderRows.value,
);
const focusRow = computed(
  () =>
    visibleRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? elderRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? null,
);
const focusTrend = computed(() => trendStore.value[selectedDeviceMac.value] ?? []);
const focusLatest = computed(() => (selectedDeviceMac.value ? latest.value[selectedDeviceMac.value] ?? null : null));
const focusAlarm = computed(
  () => alarms.value.find((alarm) => !alarm.acknowledged && alarm.device_mac === selectedDeviceMac.value) ?? null,
);
const debugRows = computed<DebugRow[]>(() =>
  devices.value.map((device) => ({
    mac: device.mac_address,
    deviceName: device.device_name,
    status: device.status,
    sample: latest.value[device.mac_address] ?? null,
  })),
);
const syncLabel = computed(() =>
  lastSyncAt.value ? lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false }) : "等待同步",
);
const highRiskCount = computed(() => elderRows.value.filter((row) => row.risk === "high").length);
const activeAlarmCount = computed(() => alarms.value.filter((alarm) => !alarm.acknowledged).length);
const communityAgentDeviceMacs = computed(() => elderRows.value.slice(0, 8).map((row) => row.deviceMac).filter(Boolean));
const communityFocusNames = computed(() => elderRows.value.slice(0, 3).map((row) => row.name));
const focusRiskLabel = computed(() => (focusRow.value ? riskLabel(focusRow.value.risk) : "等待选择"));
const selectedHistoryDevice = computed(
  () => devices.value.find((device) => device.mac_address === deviceHistoryMac.value) ?? null,
);
const currentHealthEvaluation = computed<CareHealthEvaluationSummary | null>(() => {
  if (!selectedDeviceMac.value || !accessProfile.value) return null;
  return accessProfile.value.health_evaluations.find((item) => item.device_mac === selectedDeviceMac.value) ?? null;
});
const currentHealthReportSummary = computed<CareHealthReportSummary | null>(() => {
  if (!selectedDeviceMac.value || !accessProfile.value) return null;
  return accessProfile.value.health_reports.find((item) => item.device_mac === selectedDeviceMac.value) ?? null;
});
const hasBoundDevice = computed(() => {
  if (sessionUser.value?.role === "family" && accessProfile.value) {
    return accessProfile.value.binding_state === "bound" && accessProfile.value.capabilities.device_metrics;
  }
  return Boolean(focusRow.value?.deviceMac);
});
const focusTone = computed<DemoTone>(() => {
  if (!hasBoundDevice.value) return "neutral";
  if (focusAlarm.value) return "critical";
  if (focusRow.value?.risk === "high" || focusRow.value?.risk === "medium") return "warning";
  if (focusRow.value?.risk === "low") return "stable";
  return "neutral";
});
const focusUpdatedLabel = computed(() =>
  focusLatest.value
    ? new Date(focusLatest.value.timestamp).toLocaleString("zh-CN", { hour12: false })
    : "等待实时同步",
);
const focusSummaryTitle = computed(() => {
  if (!hasBoundDevice.value) return "等待绑定设备";
  if (focusAlarm.value) return "已进入告警处理阶段";
  if (focusRow.value?.risk === "high") return "当前处于高风险关注";
  if (focusRow.value?.risk === "medium") return "当前有波动，需要继续观察";
  if (focusRow.value?.risk === "low") return "当前状态整体平稳";
  return "等待更多健康数据";
});
const focusSummaryCopy = computed(() => {
  if (!hasBoundDevice.value) {
    return accessProfile.value?.basic_advice
      || "当前账号下的老人还没有绑定设备。建议先完成设备绑定，再查看实时体征、趋势和报告。";
  }
  if (!focusLatest.value) {
    return "设备已绑定，正在等待最新体征数据。同步完成后，这里会给出当前摘要、指标和风险链路。";
  }

  const metrics = [
    `心率 ${focusLatest.value.heart_rate} bpm`,
    `血氧 ${focusLatest.value.blood_oxygen}%`,
    `体温 ${focusLatest.value.temperature.toFixed(1)}°C`,
  ].join("，");

  if (focusAlarm.value) {
    return `${focusAlarm.value.message}。当前最新样本为 ${metrics}，建议先看异常阶段，再决定后续联系和处置动作。`;
  }
  if (focusRow.value?.risk === "high") {
    return `当前综合风险偏高，最新样本为 ${metrics}。建议优先结合 24 小时报告、关键发现和建议动作完成复核。`;
  }
  if (focusRow.value?.risk === "medium") {
    return `当前存在轻到中度波动，最新样本为 ${metrics}。建议持续观察近几次样本，并根据报告建议安排跟进。`;
  }
  return `当前体征整体平稳，最新样本为 ${metrics}。可继续按趋势和报告建议进行日常关注。`;
});
const familyTrendPreview = computed(() => focusTrend.value.slice(-4).reverse());
const familyTrendHeadline = computed(() => {
  if (!familyTrendPreview.value.length) {
    return "当前还没有近阶段样本摘要，请等待设备继续同步。";
  }

  const latestPoint = familyTrendPreview.value[0];
  const oldestPoint = familyTrendPreview.value[familyTrendPreview.value.length - 1];
  const latestScore = latestPoint.health_score ?? null;
  const oldestScore = oldestPoint.health_score ?? null;

  if (latestScore !== null && oldestScore !== null) {
    if (latestScore - oldestScore >= 5) return "近阶段健康分有回升趋势，可继续保持观察。";
    if (oldestScore - latestScore >= 5) return "近阶段健康分有下降趋势，建议优先查看报告与异常链路。";
  }
  return "近阶段样本已同步，可结合单次指标和报告结论继续判断。";
});
const familySnapshotCards = computed<SnapshotMetric[]>(() => {
  const sample = focusLatest.value;
  return [
    {
      id: "heart-rate",
      shortLabel: "HR",
      label: "心率",
      value: sample ? String(sample.heart_rate) : "--",
      unit: "bpm",
      note: sample
        ? sample.heart_rate >= 110 || sample.heart_rate <= 45
          ? "已超出重点关注区间"
          : "当前在常规观察区间"
        : "等待实时样本",
      tone: sample && (sample.heart_rate >= 110 || sample.heart_rate <= 45) ? "warning" : "stable",
    },
    {
      id: "blood-oxygen",
      shortLabel: "SpO2",
      label: "血氧",
      value: sample ? String(sample.blood_oxygen) : "--",
      unit: "%",
      note: sample ? (sample.blood_oxygen < 93 ? "低于常规阈值" : "当前供氧表现稳定") : "等待实时样本",
      tone: sample && sample.blood_oxygen < 93 ? "critical" : "stable",
    },
    {
      id: "temperature",
      shortLabel: "TEMP",
      label: "体温",
      value: sample ? sample.temperature.toFixed(1) : "--",
      unit: "°C",
      note: sample ? (sample.temperature >= 37.8 ? "需关注发热波动" : "体温暂时平稳") : "等待实时样本",
      tone: sample && sample.temperature >= 37.8 ? "warning" : "stable",
    },
    {
      id: "battery",
      shortLabel: "BAT",
      label: "设备电量",
      value: sample?.battery !== null && sample?.battery !== undefined ? String(sample.battery) : "--",
      unit: "%",
      note:
        sample?.battery !== null && sample?.battery !== undefined
          ? sample.battery <= 20
            ? "建议尽快充电"
            : "设备续航正常"
          : "等待设备状态",
      tone:
        sample?.battery !== null && sample?.battery !== undefined
          ? sample.battery <= 20
            ? "warning"
            : "stable"
          : "neutral",
    },
    {
      id: "health-score",
      shortLabel: "SCORE",
      label: "健康评分",
      value:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? String(Math.round(sample.health_score))
          : "--",
      unit: "分",
      note:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? sample.health_score < 60
            ? "建议优先看报告建议"
            : "可继续结合趋势观察"
          : "等待系统评估",
      tone:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? sample.health_score < 60
            ? "warning"
            : "stable"
          : "neutral",
    },
    {
      id: "alarm-stage",
      shortLabel: "ALERT",
      label: "告警状态",
      value: focusAlarm.value ? "已触发" : "未触发",
      unit: "",
      note: focusAlarm.value?.message ?? "当前没有活跃告警，继续关注后续样本变化。",
      tone: focusAlarm.value ? "critical" : "stable",
    },
  ];
});

watch(families, (list) => {
  if (list.length && !list.some((item) => item.id === selectedFamilyId.value)) {
    selectedFamilyId.value = list[0].id;
  }
});
watch(visibleRows, (list) => {
  if (list.length && !list.some((item) => item.deviceMac === selectedDeviceMac.value)) {
    selectedDeviceMac.value = list.find((item) => item.deviceMac)?.deviceMac ?? "";
  }
});
watch(devices, (list) => {
  if (!list.length) {
    deviceHistoryMac.value = "";
    bindHistory.value = [];
    bindHistoryError.value = "";
    return;
  }
  if (!list.some((item) => item.mac_address === deviceHistoryMac.value)) {
    deviceHistoryMac.value = list[0].mac_address;
    return;
  }
  if (deviceHistoryMac.value) void refreshBindHistory(deviceHistoryMac.value);
});
watch(selectedDeviceMac, () => {
  generatedHealthReport.value = null;
  reportError.value = "";
});
watch(authAccounts, (list) => {
  if (!list.length) {
    loginHelperAccount.value = "";
    return;
  }
  if (!list.some((item) => item.username === loginHelperAccount.value)) {
    loginHelperAccount.value = list[0].username;
  }
}, { immediate: true });

function sessionToken() {
  return localStorage.getItem("ai_health_demo_session_token") ?? "";
}

function formatUiError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

async function refreshTrend(mac: string, minutes = 180) {
  const trend = await api.getTrend(mac, minutes, 120).catch(() => []);
  trendStore.value = { ...trendStore.value, [mac]: trend };
}

async function refreshAccessProfile() {
  if (!sessionUser.value) {
    accessProfile.value = null;
    return;
  }
  if (sessionUser.value.role !== "family" && sessionUser.value.role !== "elder") {
    accessProfile.value = null;
    return;
  }
  accessProfile.value = await api.getCareAccessProfile(sessionToken()).catch(() => null);
}

async function loadDirectoryForCurrentUser(user: SessionUser) {
  return user.role === "family" && user.family_id
    ? api.getFamilyCareDirectory(user.family_id)
    : api.getCareDirectory();
}

async function refreshDashboardData() {
  if (!sessionUser.value) return;
  dashboardLoading.value = true;
  dashboardLoadError.value = "";

  const data = await loadDirectoryForCurrentUser(sessionUser.value).catch(() => null);
  if (!data) {
    dashboardLoadError.value = "基础数据加载失败，请稍后重试。";
    dashboardLoading.value = false;
    return;
  }

  directory.value = data;
  const allDevices = await api.listDevices().catch(() => [] as DeviceRecord[]);
  const visibleDeviceMacs = new Set(
    data.elders.flatMap((elder) => (elder.device_macs?.length ? elder.device_macs : elder.device_mac ? [elder.device_mac] : [])),
  );
  devices.value =
    activePage.value === "relation" && sessionUser.value.role !== "family"
      ? allDevices
      : allDevices.filter((device) => visibleDeviceMacs.has(device.mac_address));

  const snapshots = await Promise.all(devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)));
  const nextLatest = { ...latest.value };
  snapshots.forEach((sample) => {
    if (sample) nextLatest[sample.device_mac] = sample;
  });
  latest.value = nextLatest;

  alarms.value = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  lastSyncAt.value = new Date();
  dashboardLoading.value = false;
}

async function refreshDebugData() {
  dashboardLoading.value = true;
  dashboardLoadError.value = "";
  devices.value = await api.listDevices().catch(() => [] as DeviceRecord[]);
  const samples = await Promise.all(devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)));
  const nextLatest = { ...latest.value };
  samples.forEach((sample) => {
    if (sample) nextLatest[sample.device_mac] = sample;
  });
  latest.value = nextLatest;
  alarms.value = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  lastSyncAt.value = new Date();
  dashboardLoading.value = false;
}

async function refreshBindHistory(mac: string) {
  bindHistoryLoading.value = true;
  bindHistoryError.value = "";
  try {
    bindHistory.value = await api.listDeviceBindLogs(mac);
  } catch (error) {
    bindHistory.value = [];
    bindHistoryError.value = formatUiError(error, "绑定历史加载失败，请稍后重试。");
  } finally {
    bindHistoryLoading.value = false;
  }
}

async function generateHealthReport() {
  if (!selectedDeviceMac.value) {
    reportError.value = "请先选择一台设备后再生成报告。";
    return;
  }

  reportLoading.value = true;
  reportError.value = "";
  generatedHealthReport.value = null;

  try {
    const endAt = new Date();
    const startAt = new Date(endAt.getTime() - 24 * 60 * 60 * 1000);
    generatedHealthReport.value = await api.generateDeviceHealthReport({
      device_mac: selectedDeviceMac.value,
      start_at: startAt.toISOString(),
      end_at: endAt.toISOString(),
      role: "family",
      mode: "local",
    });
  } catch (error) {
    reportError.value = formatUiError(error, "健康报告生成失败，请稍后重试。");
  } finally {
    reportLoading.value = false;
  }
}

const {
  deviceForm,
  elderForm,
  familyForm,
  relationBusy,
  relationError,
  relationForm,
  relationStatus,
  submitDeviceAction,
  submitElderRegistration,
  submitFamilyRegistration,
  submitRelationBinding,
} = useRelationActions({
  sessionUser,
  refreshDashboardData,
  getToken: sessionToken,
});

watch(elders, (list) => {
  if (!list.length) return;
  if (!relationForm.value.elderUserId) relationForm.value.elderUserId = list[0].id;
  if (!deviceForm.value.targetUserId) deviceForm.value.targetUserId = list[0].id;
});
watch(allFamilies, (list) => {
  if (list.length && !relationForm.value.familyUserId) relationForm.value.familyUserId = list[0].id;
});
watch(deviceHistoryMac, (mac) => {
  if (!mac) {
    bindHistory.value = [];
    bindHistoryError.value = "";
    return;
  }
  void refreshBindHistory(mac);
});

function connectHealthSocket(mac: string) {
  healthSocket?.close();
  healthSocket = null;
  if (!mac || activePage.value === "debug") return;

  healthSocket = api.healthSocket(mac);
  healthSocket.onmessage = (event) => {
    try {
      const sample = JSON.parse(event.data) as HealthSample;
      latest.value = { ...latest.value, [sample.device_mac]: sample };
      lastSyncAt.value = new Date();
    } catch {
      // keep UI stable
    }
  };
}

watch(selectedDeviceMac, (mac) => {
  connectHealthSocket(mac);
  if (mac) void refreshTrend(mac, trendWindowMinutes.value);
});
watch(trendWindowMinutes, (minutes) => {
  if (selectedDeviceMac.value) void refreshTrend(selectedDeviceMac.value, minutes);
});
watch(canAccessDebug, (allowed) => {
  if (!allowed && activePage.value === "debug") routeTo(allowedPages.value[0] ?? "community");
});

function stopRuntime() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  healthSocket?.close();
  healthSocket = null;
}

async function loadDashboard() {
  if (!sessionUser.value) return;
  stopRuntime();
  await refreshAccessProfile();
  await refreshDashboardData();
  if (selectedDeviceMac.value) await refreshTrend(selectedDeviceMac.value, trendWindowMinutes.value);
  refreshTimer = window.setInterval(() => {
    void refreshDashboardData();
    if (selectedDeviceMac.value) void refreshTrend(selectedDeviceMac.value, trendWindowMinutes.value);
  }, 15000);
}

async function loadDebugDashboard() {
  stopRuntime();
  await refreshDebugData();
  if (selectedDeviceMac.value) await refreshTrend(selectedDeviceMac.value, trendWindowMinutes.value);
  refreshTimer = window.setInterval(() => {
    void refreshDebugData();
    if (selectedDeviceMac.value) void refreshTrend(selectedDeviceMac.value, trendWindowMinutes.value);
  }, 5000);
}

async function submitLogin() {
  const user = await login();
  if (user) routeTo(user.role === "family" ? "family" : "community");
}

function applyRegistrationLoginPrefill(payload: { username: string; password: string }) {
  loginUsername.value = payload.username;
  loginPassword.value = payload.password;
  authError.value = "";
}

async function deleteDeviceRecord(mac: string) {
  deletingMac.value = mac;
  relationError.value = "";
  relationStatus.value = "";
  try {
    await api.deleteDevice(mac, sessionToken());
    lastDeletedDeviceMac.value = mac;
    relationStatus.value = `设备 ${mac} 已删除，如需再次绑定请先重新注册。`;
    await refreshDashboardData();
    if (deviceHistoryMac.value === mac) {
      deviceHistoryMac.value = "";
      bindHistory.value = [];
    }
  } catch (error) {
    relationError.value = formatUiError(error, "删除设备失败，请稍后重试。");
  } finally {
    deletingMac.value = "";
  }
}

function logout() {
  stopRuntime();
  sessionUser.value = null;
  accessProfile.value = null;
  dashboardLoading.value = false;
  dashboardLoadError.value = "";
  directory.value = null;
  devices.value = [];
  latest.value = {};
  alarms.value = [];
  bindHistory.value = [];
  bindHistoryError.value = "";
  lastDeletedDeviceMac.value = "";
  trendStore.value = {};
  logoutSession();
  resetToDefaultPage();
}

watch(sessionUser, (user) => {
  if (activePage.value === "none") {
    stopRuntime();
    return;
  }
  if (activePage.value === "debug") {
    if (canAccessDebug.value) void loadDebugDashboard();
    else stopRuntime();
    return;
  }
  if (user) void loadDashboard();
  else stopRuntime();
});

watch(activePage, (page) => {
  if (page === "none") {
    stopRuntime();
    return;
  }
  if (page === "debug") {
    if (canAccessDebug.value) void loadDebugDashboard();
    else stopRuntime();
    return;
  }
  if (sessionUser.value) void loadDashboard();
  else stopRuntime();
});

onMounted(async () => {
  await loadMockAccounts();
  await restoreSession();
  initHashRouting();
});

onUnmounted(() => {
  stopRuntime();
  disposeHashRouting();
});
</script>

<template>
  <LoginPage
    v-if="!isLoggedIn"
    :login-username="loginUsername"
    :login-password="loginPassword"
    :auth-loading="authLoading"
    :auth-error="authError"
    :auth-accounts="authAccounts"
    :login-helper-account="loginHelperAccount"
    @update:login-username="loginUsername = $event"
    @update:login-password="loginPassword = $event"
    @update:login-helper-account="loginHelperAccount = $event"
    @submit-login="void submitLogin()"
    @fill-mock-account="fillMockAccount"
    @prefill-login="applyRegistrationLoginPrefill"
  />

  <main v-else class="app-shell">
    <header class="masthead">
      <div class="brand-block">
        <div class="brand-icon">🏥</div>
        <div>
          <p class="kicker">AIoT Care Console</p>
          <h1>智慧养老健康监测平台</h1>
        </div>
      </div>
      <div class="meta-block">
        <span class="meta-pill">当前用户 {{ sessionUser?.name }}</span>
        <span class="meta-pill" style="background:rgba(34,197,94,0.12);border-color:rgba(34,197,94,0.3);color:#15803d">
          {{ sessionUser?.role === "community" ? "社区管理侧" : sessionUser?.role === "family" ? "家属侧" : sessionUser?.role }}
        </span>
        <span v-if="activeAlarmCount > 0" class="meta-pill risk-high" style="border-radius:999px;padding:6px 12px;font-size:0.8rem;font-weight:500">
          告警 {{ activeAlarmCount }}
        </span>
        <span class="meta-pill">最近同步 {{ syncLabel }}</span>
        <button v-if="canAccessDebug" type="button" class="ghost-btn" @click="routeTo('debug')">调试台</button>
        <button type="button" class="ghost-btn" @click="logout">退出</button>
      </div>
    </header>

    <nav class="page-switch">
      <button v-if="allowedPages.includes('community')" type="button" class="switch-btn" :class="{ active: activePage === 'community' }" @click="routeTo('community')">社区总览</button>
      <button v-if="allowedPages.includes('family')" type="button" class="switch-btn" :class="{ active: activePage === 'family' }" @click="routeTo('family')">家属页</button>
      <button v-if="allowedPages.includes('relation')" type="button" class="switch-btn" :class="{ active: activePage === 'relation' }" @click="routeTo('relation')">成员与设备</button>
    </nav>

    <DebugPage
      v-if="activePage === 'debug'"
      :devices-count="devices.length"
      :sync-label="syncLabel"
      :can-go-community="allowedPages.includes('community')"
      :debug-rows="debugRows"
      :selected-device-mac="selectedDeviceMac"
      :focus-latest="focusLatest"
      :focus-trend="focusTrend"
      :trend-window-minutes="trendWindowMinutes"
      @reload="void loadDebugDashboard()"
      @go-community="routeTo('community')"
      @update:selected-device-mac="selectedDeviceMac = $event"
      @update:trend-window-minutes="trendWindowMinutes = $event"
    />

    <CommunityPage
      v-else-if="activePage === 'community'"
      :community-name="community?.name ?? ''"
      :devices-count="devices.length"
      :active-alarm-count="activeAlarmCount"
      :elders-count="elders.length"
      :family-count="allFamilies.length"
      :high-risk-count="highRiskCount"
      :elder-rows="elderRows"
      :selected-device-mac="selectedDeviceMac"
      :community-focus-names="communityFocusNames"
      :community-agent-device-macs="communityAgentDeviceMacs"
      @update:selected-device-mac="selectedDeviceMac = $event"
    />

    <FamilyPage
      v-else-if="activePage === 'family'"
      :families="families"
      :selected-family-id="selectedFamilyId"
      :visible-rows="visibleRows"
      :selected-device-mac="selectedDeviceMac"
      :has-bound-device="hasBoundDevice"
      :focus-risk-label="focusRiskLabel"
      :focus-row="focusRow"
      :focus-tone="focusTone"
      :focus-summary-title="focusSummaryTitle"
      :focus-summary-copy="focusSummaryCopy"
      :focus-updated-label="focusUpdatedLabel"
      :family-snapshot-cards="familySnapshotCards"
      :family-trend-headline="familyTrendHeadline"
      :family-trend-preview="familyTrendPreview"
      :current-health-evaluation="currentHealthEvaluation"
      :current-health-report-summary="currentHealthReportSummary"
      :generated-health-report="generatedHealthReport"
      :report-loading="reportLoading"
      :report-error="reportError"
      :focus-latest="focusLatest"
      :focus-trend="focusTrend"
      :focus-alarm="focusAlarm"
      :basic-advice="accessProfile?.basic_advice || '建议先保持规律休息、补充水分、按日常节奏观察精神状态与饮食情况。完成设备绑定后，这里会显示实时指标、报告摘要和异常升级链路。'"
      @update:selected-family-id="selectedFamilyId = $event"
      @update:selected-device-mac="selectedDeviceMac = $event"
      @generate-report="void generateHealthReport()"
    />

    <MemberDevicePage
      v-else-if="activePage === 'relation'"
      :elders="elders"
      :families="allFamilies"
      :community-name="community?.name ?? ''"
      :devices="devices"
      :elder-form="elderForm"
      :family-form="familyForm"
      :relation-form="relationForm"
      :device-form="deviceForm"
      :relation-busy="relationBusy"
      :relation-status="relationStatus"
      :relation-error="relationError"
      :device-modes="deviceModes"
      :dashboard-loading="dashboardLoading"
      :dashboard-load-error="dashboardLoadError"
      :last-deleted-device-mac="lastDeletedDeviceMac"
      :device-history-mac="deviceHistoryMac"
      :selected-history-device="selectedHistoryDevice"
      :bind-history="bindHistory"
      :bind-history-loading="bindHistoryLoading"
      :bind-history-error="bindHistoryError"
      :deleting-mac="deletingMac"
      @submit-elder-registration="void submitElderRegistration()"
      @submit-family-registration="void submitFamilyRegistration()"
      @submit-relation-binding="void submitRelationBinding()"
      @submit-device-action="void submitDeviceAction()"
      @delete-device="void deleteDeviceRecord($event)"
      @update:device-history-mac="deviceHistoryMac = $event"
    />

    <AccessDeniedPage v-else />
  </main>
</template>
