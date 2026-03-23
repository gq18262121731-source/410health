<script setup lang="ts">
import { computed, ref, toRef, watch } from "vue";
import type { HealthSample, SessionUser } from "../api/client";
import CommunityAssistantPanel from "../components/CommunityAssistantPanel.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCareDirectoryDashboard } from "../composables/useCareDirectoryDashboard";
import { evaluateRisk, riskLabel, riskWeight, type RiskLevel } from "../domain/careModel";

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

const props = defineProps<{
  sessionUser: SessionUser;
}>();

const sessionUser = toRef(props, "sessionUser");
const {
  alarms,
  allFamilies,
  community,
  dashboardLoadError,
  dashboardLoading,
  devices,
  elders,
  lastSyncAt,
  latest,
} = useCareDirectoryDashboard(sessionUser);

const selectedDeviceMac = ref("");

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

const activeAlarmCount = computed(() => alarms.value.filter((alarm) => !alarm.acknowledged).length);
const highRiskCount = computed(() => elderRows.value.filter((row) => row.risk === "high").length);
const communityFocusNames = computed(() => elderRows.value.slice(0, 3).map((row) => row.name));
const communityAgentDeviceMacs = computed(() => elderRows.value.slice(0, 8).map((row) => row.deviceMac).filter(Boolean));
const syncLabel = computed(() =>
  lastSyncAt.value ? lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false }) : "尚未同步",
);
const pageMeta = computed(() => [
  `社区 ${community.value?.name || "未分配"}`,
  `设备 ${devices.value.length}`,
  `活跃告警 ${activeAlarmCount.value}`,
  `同步 ${syncLabel.value}`,
]);

watch(
  elderRows,
  (rows) => {
    if (!rows.length) {
      selectedDeviceMac.value = "";
      return;
    }
    if (!rows.some((row) => row.deviceMac === selectedDeviceMac.value)) {
      selectedDeviceMac.value = rows.find((row) => row.deviceMac)?.deviceMac ?? "";
    }
  },
  { immediate: true },
);

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Community Overview"
      title="社区总览"
      description="页面级头部展示社区态势、同步状态与关键统计，具体关注对象和派单分析都留在页面内部呈现。"
      :meta="pageMeta"
    />

    <p v-if="dashboardLoadError" class="feedback-banner feedback-error">{{ dashboardLoadError }}</p>

    <div v-else-if="dashboardLoading && !elderRows.length" class="state-block state-loading">
      <strong>正在加载社区数据</strong>
      <p>社区总览会在数据到位后展示优先级列表、重点对象和社区助手摘要。</p>
    </div>

    <section v-else class="panel-grid community-grid">
      <article class="panel metric-panel dashboard-hero-panel">
        <div class="dashboard-hero-head">
          <div class="dashboard-title-block">
            <p class="section-eyebrow">Community Console</p>
            <h2>社区运行概览</h2>
            <p class="subtle-copy">
              面向社区值守人员展示当前社区的设备覆盖、老人规模、告警压力和高风险对象排序，便于快速定位需要优先跟进的成员。
            </p>
          </div>
          <div class="dashboard-chip-row">
            <span class="meta-pill">社区 {{ community?.name || "未分配" }}</span>
            <span class="meta-pill">设备 {{ devices.length }}</span>
            <span class="meta-pill">活跃告警 {{ activeAlarmCount }}</span>
          </div>
        </div>
        <div class="metric-row metric-row--dashboard">
          <div class="metric-card">
            <span>老人总数</span>
            <strong>{{ elders.length }}</strong>
          </div>
          <div class="metric-card">
            <span>家属总数</span>
            <strong>{{ allFamilies.length }}</strong>
          </div>
          <div class="metric-card" :class="{ 'metric-card--critical': highRiskCount > 0 }">
            <span>高风险对象</span>
            <strong>{{ highRiskCount }}</strong>
          </div>
          <div class="metric-card" :class="{ 'metric-card--warning': activeAlarmCount > 0 }">
            <span>待处理告警</span>
            <strong>{{ activeAlarmCount }}</strong>
          </div>
          <div class="metric-card">
            <span>当前重点关注</span>
            <strong class="metric-card-title">{{ elderRows[0]?.name ?? "暂无" }}</strong>
          </div>
        </div>
      </article>

      <article class="panel table-panel dashboard-section-panel">
        <div class="dashboard-section-head">
          <div>
            <p class="section-eyebrow">Priority List</p>
            <h2>重点跟进列表</h2>
          </div>
          <span class="meta-pill">按风险与健康分排序，最多展示 10 人</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>老人</th>
                <th>家属</th>
                <th>风险级别</th>
                <th>心率</th>
                <th>血氧</th>
                <th>健康分</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in elderRows.slice(0, 10)"
                :key="row.id"
                :class="{ current: row.deviceMac === selectedDeviceMac }"
                @click="selectedDeviceMac = row.deviceMac"
              >
                <td>
                  <strong>{{ row.name }}</strong>
                  <small>{{ row.apartment }}</small>
                </td>
                <td>{{ row.familyNames || "-" }}</td>
                <td><span class="risk-pill" :class="riskClass(row.risk)">{{ riskLabel(row.risk) }}</span></td>
                <td>{{ row.sample?.heart_rate ?? "-" }}</td>
                <td>{{ row.sample?.blood_oxygen ?? "-" }}</td>
                <td>{{ row.sample?.health_score ?? "-" }}</td>
              </tr>
              <tr v-if="!elderRows.length">
                <td colspan="6">当前社区还没有可展示的成员数据。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <CommunityAssistantPanel
        class="dispatch-panel"
        :elder-count="elders.length"
        :device-count="devices.length"
        :high-risk-count="highRiskCount"
        :active-alarm-count="activeAlarmCount"
        :focus-names="communityFocusNames"
        :device-macs="communityAgentDeviceMacs"
      />
    </section>
  </section>
</template>
