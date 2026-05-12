<script setup lang="ts">
import { computed, ref, toRef, watch } from "vue";
import { LogOut, ShieldCheck } from "lucide-vue-next";
import type {
  HealthSample,
  SessionUser,
} from "../api/client";
import CameraMonitorCard from "../components/CameraMonitorCard.vue";
import CameraRegistrationPanel from "../components/CameraRegistrationPanel.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCareDirectoryDashboard } from "../composables/useCareDirectoryDashboard";
import { useDeviceTrend } from "../composables/useDeviceTrend";
import { evaluateRisk, riskLabel, type RiskLevel } from "../domain/careModel";

type DemoTone = "neutral" | "stable" | "warning" | "critical";

interface ElderRow {
  id: string;
  name: string;
  apartment: string;
  deviceMac: string;
  familyNames: string;
  risk: RiskLevel;
  sample: HealthSample | null;
}

interface SnapshotMetric {
  id: string;
  shortLabel: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  tone: DemoTone;
}

const props = defineProps<{
  sessionUser: SessionUser;
}>();

const sessionUser = toRef(props, "sessionUser");
const {
  alarms,
  allFamilies: allFamiliesRaw,
  dashboardLoadError,
  dashboardLoading,
  devices,
  elders,
  latest,
} = useCareDirectoryDashboard(sessionUser);

const selectedFamilyId = ref("");
const selectedDeviceMac = ref("");
const cameraCardKey = ref(0);

const { focusLatest, focusTrend } = useDeviceTrend({
  selectedDeviceMac,
  latest,
  pollIntervalMs: 15000,
});

function handleCameraSourceChange() {
  cameraCardKey.value += 1;
}

const families = computed(() =>
  sessionUser.value.role === "family"
    ? allFamiliesRaw.value.filter((family) => family.id === sessionUser.value.family_id)
    : allFamiliesRaw.value,
);

const selectedFamily = computed(() =>
  families.value.find((family) => family.id === selectedFamilyId.value) ?? families.value[0] ?? null,
);

const elderRows = computed<ElderRow[]>(() =>
  elders.value.map((elder) => {
    const rawDeviceMac = elder.device_macs?.[0] ?? elder.device_mac ?? "";
    const deviceRecord = rawDeviceMac
      ? devices.value.find((device) => device.mac_address === rawDeviceMac) ?? null
      : null;
    const exposeDevice =
      deviceRecord != null
        ? deviceRecord.ingest_mode === "mock" || deviceRecord.bind_status === "bound"
        : false;
    const deviceMac = exposeDevice ? rawDeviceMac : "";
    const sample = deviceMac ? latest.value[deviceMac] ?? null : null;
    const risk = evaluateRisk(sample, deviceMac ? (deviceRecord?.status ?? "unknown") : "unbound");
    const familyNames = elder.family_ids
      .map((id) => allFamiliesRaw.value.find((family) => family.id === id)?.name)
      .filter(Boolean)
      .join(" / ");
    return { id: elder.id, name: elder.name, apartment: elder.apartment, deviceMac, familyNames, risk, sample };
  }),
);

const visibleRows = computed(() =>
  sessionUser.value.role === "family" && selectedFamily.value
    ? elderRows.value.filter((row) => new Set(selectedFamily.value.elder_ids ?? []).has(row.id))
    : elderRows.value,
);

const focusRow = computed(
  () =>
    visibleRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? elderRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? null,
);

const focusAlarm = computed(
  () => alarms.value.find((alarm) => !alarm.acknowledged && alarm.device_mac === selectedDeviceMac.value) ?? null,
);

const hasBoundDevice = computed(() => visibleRows.value.some((row) => Boolean(row.deviceMac)));
const boundSubjectCount = computed(() => visibleRows.value.filter((row) => row.deviceMac).length);
const unboundSubjectCount = computed(() => visibleRows.value.filter((row) => !row.deviceMac).length);
const highRiskCount = computed(() => visibleRows.value.filter((row) => row.risk === "high").length);

const focusRiskLabel = computed(() => (focusRow.value ? riskLabel(focusRow.value.risk) : "未选择对象"));
const focusTone = computed<DemoTone>(() => {
  if (!hasBoundDevice.value) return "neutral";
  if (focusAlarm.value) return "critical";
  if (focusRow.value?.risk === "high" || focusRow.value?.risk === "medium") return "warning";
  if (focusRow.value?.risk === "low") return "stable";
  return "neutral";
});

const displayFocusLatest = computed(() => focusLatest.value ?? focusRow.value?.sample ?? null);

const focusUpdatedLabel = computed(() =>
  displayFocusLatest.value ? new Date(displayFocusLatest.value.timestamp).toLocaleString("zh-CN", { hour12: false }) : "尚未同步",
);

const focusSummaryTitle = computed(() => {
  if (!hasBoundDevice.value) return "当前家属还没有可用的绑定设备";
  if (focusAlarm.value) return "当前对象存在需要优先关注的活动告警";
  if (focusRow.value?.risk === "high") return "当前对象风险偏高，建议尽快查看";
  if (focusRow.value?.risk === "medium") return "近期信号有波动，建议继续观察";
  if (focusRow.value?.risk === "low") return "当前对象整体状态稳定";
  return "等待更多同步数据";
});

const focusSummaryCopy = computed(() => {
  if (!hasBoundDevice.value) {
    return "当前家属名下还没有已接入手环的监护对象。社区端完成设备绑定后，这里会自动显示实时状态、摄像头入口和健康报告。";
  }
  if (!displayFocusLatest.value) {
    return "照护关系已经建立，但设备还没有稳定的实时样本。你可以先等待下一轮同步，或者先打开摄像头确认现场情况。";
  }

  const sample = displayFocusLatest.value;
  const metrics = `心率 ${sample.heart_rate} bpm，血氧 ${sample.blood_oxygen}% ，体温 ${sample.temperature.toFixed(1)}°C`;

  if (focusAlarm.value) {
    return `${focusAlarm.value.message}。当前关键读数为 ${metrics}。建议先看告警升级建议，再决定是否联系社区人员处理。`;
  }
  if (focusRow.value?.risk === "high") {
    return `当前对象风险偏高，最新读数为 ${metrics}。建议先看摄像头和最近趋势，再安排进一步观察。`;
  }
  if (focusRow.value?.risk === "medium") {
    return `当前对象存在中度波动，最新读数为 ${metrics}。建议结合最近趋势持续关注。`;
  }
  return `当前对象整体稳定，最新读数为 ${metrics}。可以继续日常关注，并定期回看摄像头和趋势。`;
});

const familyTrendPreview = computed(() => focusTrend.value.slice(-4).reverse());

const familyTrendHeadline = computed(() => {
  if (!familyTrendPreview.value.length) {
    return "设备同步更多样本后，这里会展示最近一段时间的趋势变化。";
  }
  const latestPoint = familyTrendPreview.value[0];
  const oldestPoint = familyTrendPreview.value[familyTrendPreview.value.length - 1];
  const latestScore = latestPoint.health_score ?? null;
  const oldestScore = oldestPoint.health_score ?? null;

  if (latestScore !== null && oldestScore !== null) {
    if (latestScore - oldestScore >= 5) return "最近几次采样的健康分在回升，短期状态有改善。";
    if (oldestScore - latestScore >= 5) return "最近几次采样的健康分在下降，建议重点关注。";
  }

  return "最近一段时间读数相对平稳，适合和摄像头画面一起看。";
});

const familySnapshotCards = computed<SnapshotMetric[]>(() => {
  const sample = displayFocusLatest.value;
  return [
    {
      id: "heart-rate",
      shortLabel: "HR",
      label: "心率",
      value: sample ? String(sample.heart_rate) : "--",
      unit: "bpm",
      note: sample
        ? sample.heart_rate >= 110 || sample.heart_rate <= 45
          ? "心率超出建议的稳态区间。"
          : "心率处于可接受范围。"
        : "等待实时同步。",
      tone: sample && (sample.heart_rate >= 110 || sample.heart_rate <= 45) ? "warning" : "stable",
    },
    {
      id: "blood-oxygen",
      shortLabel: "SpO2",
      label: "血氧",
      value: sample ? String(sample.blood_oxygen) : "--",
      unit: "%",
      note: sample ? (sample.blood_oxygen < 93 ? "血氧偏低，建议结合趋势和摄像头查看。" : "血氧状态相对稳定。") : "等待实时同步。",
      tone: sample && sample.blood_oxygen < 93 ? "critical" : "stable",
    },
    {
      id: "temperature",
      shortLabel: "TEMP",
      label: "体温",
      value: sample ? sample.temperature.toFixed(1) : "--",
      unit: "°C",
      note: sample ? (sample.temperature >= 37.8 ? "体温偏高，建议继续观察。" : "体温状态稳定。") : "等待实时同步。",
      tone: sample && sample.temperature >= 37.8 ? "warning" : "stable",
    },
    {
      id: "battery",
      shortLabel: "BAT",
      label: "电量",
      value: sample?.battery !== null && sample?.battery !== undefined ? String(sample.battery) : "--",
      unit: "%",
      note:
        sample?.battery !== null && sample?.battery !== undefined
          ? sample.battery <= 20
            ? "设备电量偏低，建议尽快充电。"
            : "设备电量正常。"
          : "暂无电量数据。",
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
      label: "健康分",
      value:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? String(Math.round(sample.health_score))
          : "--",
      unit: "分",
      note:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? sample.health_score < 60
            ? "健康分偏低，建议重点关注。"
            : "健康分处于可观察区间。"
          : "等待健康分同步。",
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
      value: focusAlarm.value ? "有活动告警" : "暂无活动告警",
      unit: "",
      note: focusAlarm.value?.message ?? "当前没有活动告警，但仍建议持续关注。",
      tone: focusAlarm.value ? "critical" : "stable",
    },
  ];
});

const pageMeta = computed(() => [
  `家属 ${selectedFamily.value?.name || "未选择"}`,
  `对象 ${focusRow.value?.name || "未选择"}`,
  `已绑定 ${boundSubjectCount.value}`,
  `待绑定 ${unboundSubjectCount.value}`,
  `高风险 ${highRiskCount.value}`,
]);

watch(
  families,
  (list) => {
    if (!list.length) {
      selectedFamilyId.value = "";
      return;
    }
    if (!list.some((item) => item.id === selectedFamilyId.value)) {
      selectedFamilyId.value = list[0].id;
    }
  },
  { immediate: true },
);

watch(
  visibleRows,
  (list) => {
    if (!list.length) {
      selectedDeviceMac.value = "";
      return;
    }
    if (!list.some((item) => item.deviceMac === selectedDeviceMac.value)) {
      selectedDeviceMac.value = list.find((item) => item.deviceMac)?.deviceMac ?? "";
    }
  },
  { immediate: true },
);

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}

function updateFamilyId(event: Event) {
  selectedFamilyId.value = (event.target as HTMLSelectElement).value;
}

function logoutCurrentPage() {
  localStorage.removeItem("ai_health_demo_session_token");
  window.location.reload();
}
</script>

<template>
  <section class="page-stack family-mobile-desktop-page">
    <PageHeader
      eyebrow="家属关护"
      title="家人守护"
      description="这个 PC 家属端参照移动端家属首页重构，优先展示监护对象、实时摘要、摄像头入口和健康报告。"
      :meta="pageMeta"
    >
      <template #actions>
        <div class="family-header-actions">
          <div class="family-user-card">
            <span class="family-user-card__name">{{ sessionUser.name }}</span>
            <span class="family-user-card__role">
              <ShieldCheck :size="14" />
              家属查看
            </span>
          </div>
          <button type="button" class="family-header-logout" @click="logoutCurrentPage">
            <LogOut :size="16" />
            <span>退出</span>
          </button>
        </div>
      </template>
    </PageHeader>

    <p v-if="dashboardLoadError" class="feedback-banner feedback-error">{{ dashboardLoadError }}</p>

    <div v-else-if="dashboardLoading && !visibleRows.length" class="state-block state-loading">
      <strong>正在加载家属工作台</strong>
      <p>数据就绪后，这里会展示已关联对象、实时状态、摄像头入口和健康摘要。</p>
    </div>

    <section v-else class="panel-grid family-grid family-grid--flutter">
      <article class="panel family-header family-mobile-hero">
        <div class="family-mobile-hero__top">
          <div>
            <p class="section-eyebrow">家属首页</p>
            <h2>当前关护对象</h2>
            <p class="subtle-copy">
              和移动端一样，这里优先回答三个问题：你在关心谁、谁当前在线、谁需要先关注。有设备的对象会直接给出实时摘要，未绑定的对象会明确标记出来。
            </p>
          </div>
          <label class="form-field family-select-field">
            <span>当前家属账号</span>
            <select :value="selectedFamilyId" class="inline-select" @change="updateFamilyId">
              <option v-for="family in families" :key="family.id" :value="family.id">
                {{ family.name }} / {{ family.relationship }}
              </option>
            </select>
          </label>
        </div>

        <div class="family-mobile-summary">
          <article class="family-mobile-summary__card">
            <span>已绑定对象</span>
            <strong>{{ boundSubjectCount }}</strong>
            <small>已接入手环，可查看实时状态</small>
          </article>
          <article class="family-mobile-summary__card">
            <span>待绑定对象</span>
            <strong>{{ unboundSubjectCount }}</strong>
            <small>已建立关系，但尚未接入设备</small>
          </article>
          <article class="family-mobile-summary__card">
            <span>高风险关注</span>
            <strong>{{ highRiskCount }}</strong>
            <small>建议优先查看的对象数量</small>
          </article>
        </div>

        <div class="family-cards family-cards--flutter">
          <button
            v-for="row in visibleRows"
            :key="row.id"
            type="button"
            class="family-elder-card family-elder-card--flutter"
            :class="[riskClass(row.risk), { active: row.deviceMac === selectedDeviceMac }]"
            @click="selectedDeviceMac = row.deviceMac"
          >
            <div class="family-card-head">
              <div>
                <strong>{{ row.name }}</strong>
                <small>{{ row.apartment }}</small>
              </div>
              <span class="risk-pill" :class="riskClass(row.risk)">
                {{ row.deviceMac ? riskLabel(row.risk) : "未绑定" }}
              </span>
            </div>
            <p>{{ row.familyNames || "当前暂无更多家属关系说明" }}</p>
            <div class="family-kpis">
              <span>{{ row.deviceMac ? `HR ${row.sample?.heart_rate ?? "-"}` : "待绑定设备" }}</span>
              <span>{{ row.deviceMac ? `SpO2 ${row.sample?.blood_oxygen ?? "-"}` : "暂无实时指标" }}</span>
              <span>{{ row.deviceMac ? `健康分 ${row.sample?.health_score ?? "-"}` : "完成绑定后可查看" }}</span>
            </div>
          </button>
        </div>
      </article>

      <article class="panel family-detail family-main-panel family-main-panel--flutter">
        <header class="panel-head family-main-head">
          <div>
            <p class="section-eyebrow">关护摘要</p>
            <h2>{{ focusRow?.name ?? "请选择一个关护对象" }}</h2>
            <p class="subtle-copy">这里是家属最常用的主视区：一句话摘要、摄像头入口、关键读数和趋势预览。</p>
          </div>
          <span class="meta-pill">{{ hasBoundDevice ? focusRiskLabel : "等待设备绑定" }}</span>
        </header>

        <div v-if="hasBoundDevice" class="family-overview-stack">
          <section class="family-summary-banner" :class="`tone-${focusTone}`">
            <div class="family-summary-copy">
              <p class="section-eyebrow">摘要</p>
              <h3>{{ focusSummaryTitle }}</h3>
              <p class="summary-body">{{ focusSummaryCopy }}</p>
              <div class="summary-meta">
                <span class="status-tag tone-info">房间 {{ focusRow?.apartment ?? "--" }}</span>
                <span class="status-tag tone-neutral">设备 {{ selectedDeviceMac || "未选择" }}</span>
                <span class="status-tag tone-neutral">同步 {{ focusUpdatedLabel }}</span>
              </div>
            </div>
            <div class="family-summary-score">
              <span>当前风险</span>
              <strong>{{ focusRiskLabel }}</strong>
              <p>
                {{ focusAlarm ? "建议先看活动告警和摄像头，再决定是否联系社区人员处理。" : "当前没有活动告警，维持日常关注即可。" }}
              </p>
            </div>
          </section>

          <CameraRegistrationPanel @source-change="handleCameraSourceChange" />
          <CameraMonitorCard :key="cameraCardKey" />

          <div class="family-health-grid family-health-grid--flutter">
            <article
              v-for="card in familySnapshotCards"
              :key="card.id"
              class="family-health-card family-health-card--demo"
              :class="`tone-${card.tone}`"
            >
              <div class="family-health-card-top">
                <span class="metric-badge">{{ card.shortLabel }}</span>
                <small>{{ card.label }}</small>
              </div>
              <div class="family-health-card-value">
                <strong>{{ card.value }}</strong>
                <span>{{ card.unit }}</span>
              </div>
              <p>{{ card.note }}</p>
            </article>
          </div>

          <article class="family-trend-panel family-trend-panel--flutter">
            <div class="panel-head">
              <div>
                <p class="section-eyebrow">最近趋势</p>
                <h3>最近趋势预览</h3>
                <p class="panel-subtitle">{{ familyTrendHeadline }}</p>
              </div>
              <span class="meta-pill">样本 {{ familyTrendPreview.length }}</span>
            </div>

            <div v-if="familyTrendPreview.length" class="trend-list trend-list--compact">
              <article v-for="point in familyTrendPreview" :key="point.timestamp" class="trend-item trend-item--demo">
                <div class="trend-item-head">
                  <strong>{{ new Date(point.timestamp).toLocaleString("zh-CN", { hour12: false }) }}</strong>
                  <span>健康分 {{ point.health_score ?? "--" }}</span>
                </div>
                <div class="trend-kpi-row">
                  <span>HR {{ point.heart_rate }}</span>
                  <span>SpO2 {{ point.blood_oxygen }}%</span>
                  <span>体温 {{ point.temperature.toFixed(1) }}°C</span>
                </div>
              </article>
            </div>
            <div v-else class="state-block state-empty">
              <strong>暂无最近趋势样本</strong>
              <p>设备继续上报后，这里会自动出现最近一段时间的趋势变化。</p>
            </div>
          </article>
        </div>

        <div v-else class="state-block state-empty state-large">
          <strong>当前还没有可用的绑定设备</strong>
          <p>社区端完成设备绑定后，这里会像移动端家属首页一样，优先展示实时摘要、摄像头入口和健康状态。</p>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.family-mobile-desktop-page {
  gap: 20px;
}

.family-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.family-user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.family-user-card__name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.family-user-card__role {
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

.family-header-logout {
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
  cursor: pointer;
  transition: all 180ms ease;
}

.family-header-logout:hover {
  color: #ffffff;
  background: #ef4444;
  border-color: #ef4444;
}

.family-grid--flutter .family-header,
.family-grid--flutter .family-detail {
  grid-column: span 12;
}

.family-mobile-hero,
.family-mobile-hero__top,
.family-mobile-summary,
.family-cards--flutter,
.family-main-panel--flutter {
  display: grid;
  gap: 18px;
}

.family-mobile-hero {
  padding: 28px;
  border-radius: 28px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid rgba(37, 99, 235, 0.14);
}

.family-mobile-hero__top {
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  align-items: start;
}

.family-mobile-summary {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.family-mobile-summary__card {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 22px;
  background: #ffffff;
  border: 1px solid var(--line-medium);
}

.family-mobile-summary__card span {
  color: var(--text-sub);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.family-mobile-summary__card strong {
  color: var(--text-main);
  font-size: clamp(1.9rem, 2.8vw, 2.4rem);
  line-height: 1.05;
}

.family-mobile-summary__card small {
  color: var(--text-sub);
  line-height: 1.65;
}

.family-cards--flutter {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.family-elder-card--flutter {
  display: grid;
  gap: 12px;
  padding: 18px;
  border-radius: 24px;
  border: 1px solid var(--line-medium);
  background: #ffffff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.03);
}

.family-elder-card--flutter:hover,
.family-elder-card--flutter.active {
  border-color: var(--brand);
  background: #eff6ff;
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.08);
}

.family-health-grid--flutter {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.family-trend-panel--flutter {
  padding: 20px;
}

@media (max-width: 1280px) {
  .family-mobile-summary,
  .family-cards--flutter,
  .family-health-grid--flutter {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 960px) {
  .family-header-actions {
    justify-content: flex-start;
  }

  .family-mobile-hero__top,
  .family-mobile-summary,
  .family-cards--flutter,
  .family-health-grid--flutter {
    grid-template-columns: 1fr;
  }
}
</style>
