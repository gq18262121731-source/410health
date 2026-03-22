<script setup lang="ts">
import type { HealthSample } from "../api/client";
import { riskLabel, type RiskLevel } from "../domain/careModel";
import CommunityAssistantPanel from "../components/CommunityAssistantPanel.vue";

interface ElderRow {
  id: string;
  name: string;
  apartment: string;
  deviceMac: string;
  familyNames: string;
  risk: RiskLevel;
  sample: HealthSample | null;
}

defineProps<{
  communityName: string;
  devicesCount: number;
  activeAlarmCount: number;
  eldersCount: number;
  familyCount: number;
  highRiskCount: number;
  elderRows: ElderRow[];
  selectedDeviceMac: string;
  communityFocusNames: string[];
  communityAgentDeviceMacs: string[];
}>();

const emit = defineEmits<{
  "update:selectedDeviceMac": [value: string];
}>();

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}
</script>

<template>
  <section class="panel-grid community-grid">
    <article class="panel metric-panel dashboard-hero-panel">
      <div class="dashboard-hero-head">
        <div class="dashboard-title-block">
          <p class="section-eyebrow">Community Console</p>
          <h2>社区风险总览</h2>
          <p class="subtle-copy">社区页负责承接全局总览、重点对象和社区智能体建议，不再混入家属态的解释链路。</p>
        </div>
        <div class="dashboard-chip-row">
          <span class="meta-pill">社区 {{ communityName || "—" }}</span>
          <span class="meta-pill">在线概览 {{ devicesCount }} 台设备</span>
          <span class="meta-pill">活跃告警 {{ activeAlarmCount }}</span>
        </div>
      </div>
      <div class="metric-row metric-row--dashboard">
        <div class="metric-card">
          <span>TODAY · 老人总数</span>
          <strong>{{ eldersCount }}</strong>
        </div>
        <div class="metric-card">
          <span>家属覆盖数</span>
          <strong>{{ familyCount }}</strong>
        </div>
        <div class="metric-card" :class="{ 'metric-card--critical': highRiskCount > 0 }">
          <span>高风险对象</span>
          <strong>{{ highRiskCount }}</strong>
        </div>
        <div class="metric-card" :class="{ 'metric-card--warning': activeAlarmCount > 0 }">
          <span>活跃告警</span>
          <strong>{{ activeAlarmCount }}</strong>
        </div>
        <div class="metric-card">
          <span>当前重点对象</span>
          <strong class="metric-card-title">{{ elderRows[0]?.name ?? "—" }}</strong>
        </div>
      </div>
    </article>

    <article class="panel table-panel dashboard-section-panel">
      <div class="dashboard-section-head">
        <div>
          <p class="section-eyebrow">Priority List</p>
          <h2>待处理对象</h2>
        </div>
        <span class="meta-pill">优先展示前 10 位</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>老人</th><th>家属</th><th>风险</th><th>心率</th><th>血氧</th><th>健康分</th></tr></thead>
          <tbody>
            <tr
              v-for="row in elderRows.slice(0, 10)"
              :key="row.id"
              :class="{ current: row.deviceMac === selectedDeviceMac }"
              @click="emit('update:selectedDeviceMac', row.deviceMac)"
            >
              <td><strong>{{ row.name }}</strong><small>{{ row.apartment }}</small></td>
              <td>{{ row.familyNames || "-" }}</td>
              <td><span class="risk-pill" :class="riskClass(row.risk)">{{ riskLabel(row.risk) }}</span></td>
              <td>{{ row.sample?.heart_rate ?? "-" }}</td>
              <td>{{ row.sample?.blood_oxygen ?? "-" }}</td>
              <td>{{ row.sample?.health_score ?? "-" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <CommunityAssistantPanel
      class="dispatch-panel"
      :elder-count="eldersCount"
      :device-count="devicesCount"
      :high-risk-count="highRiskCount"
      :active-alarm-count="activeAlarmCount"
      :focus-names="communityFocusNames"
      :device-macs="communityAgentDeviceMacs"
    />
  </section>
</template>
