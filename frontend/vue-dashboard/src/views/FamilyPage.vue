<script setup lang="ts">
import type {
  AgentDeviceHealthReport,
  AlarmRecord,
  CareHealthEvaluationSummary,
  CareHealthReportSummary,
  FamilyProfile,
  HealthSample,
} from "../api/client";
import { riskLabel, type RiskLevel } from "../domain/careModel";
import AssistantPanel from "../components/AssistantPanel.vue";
import AlarmEscalationPanel from "../components/AlarmEscalationPanel.vue";
import HealthEvaluationPanel from "../components/HealthEvaluationPanel.vue";

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

defineProps<{
  families: FamilyProfile[];
  selectedFamilyId: string;
  visibleRows: ElderRow[];
  selectedDeviceMac: string;
  hasBoundDevice: boolean;
  focusRiskLabel: string;
  focusRow: ElderRow | null;
  focusTone: DemoTone;
  focusSummaryTitle: string;
  focusSummaryCopy: string;
  focusUpdatedLabel: string;
  familySnapshotCards: SnapshotMetric[];
  familyTrendHeadline: string;
  familyTrendPreview: HealthSample[];
  currentHealthEvaluation: CareHealthEvaluationSummary | null;
  currentHealthReportSummary: CareHealthReportSummary | null;
  generatedHealthReport: AgentDeviceHealthReport | null;
  reportLoading: boolean;
  reportError: string;
  focusLatest: HealthSample | null;
  focusTrend: HealthSample[];
  focusAlarm: AlarmRecord | null;
  basicAdvice: string;
}>();

const emit = defineEmits<{
  "update:selectedFamilyId": [value: string];
  "update:selectedDeviceMac": [value: string];
  generateReport: [];
}>();

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}

function updateFamilyId(event: Event) {
  emit("update:selectedFamilyId", (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <section class="panel-grid family-grid">
    <article class="panel family-header family-selector-panel">
      <div class="family-toolbar">
        <div>
          <p class="section-eyebrow">Family View</p>
          <h2>我关心的老人</h2>
          <p class="subtle-copy">家属页负责承接状态摘要、结构化报告、异常升级和家庭智能体，不再承担社区运维职责。</p>
        </div>
        <label class="form-field family-select-field">
          <span>当前家庭关系</span>
          <select :value="selectedFamilyId" class="inline-select" @change="updateFamilyId">
            <option v-for="family in families" :key="family.id" :value="family.id">{{ family.name }} / {{ family.relationship }}</option>
          </select>
        </label>
      </div>
      <div class="family-cards">
        <button
          v-for="row in visibleRows"
          :key="row.id"
          type="button"
          class="family-elder-card family-elder-card--demo"
          :class="[riskClass(row.risk), { active: row.deviceMac === selectedDeviceMac }]"
          @click="emit('update:selectedDeviceMac', row.deviceMac)"
        >
          <div class="family-card-head">
            <div>
              <strong>{{ row.name }}</strong>
              <small>{{ row.apartment }}</small>
            </div>
            <span class="risk-pill" :class="riskClass(row.risk)">{{ riskLabel(row.risk) }}</span>
          </div>
          <p>{{ row.familyNames || "当前暂无家属关系说明" }}</p>
          <div class="family-kpis">
            <span>HR {{ row.sample?.heart_rate ?? "-" }}</span>
            <span>SpO2 {{ row.sample?.blood_oxygen ?? "-" }}</span>
            <span>健康分 {{ row.sample?.health_score ?? "-" }}</span>
          </div>
        </button>
      </div>
    </article>

    <article class="panel family-detail family-main-panel">
      <header class="panel-head family-main-head">
        <div>
          <p class="section-eyebrow">Care Summary</p>
          <h2>{{ focusRow?.name ?? "当前状态面板" }}</h2>
          <p class="subtle-copy">先读摘要，再看结构化报告与异常链路，避免把家属端做成设备联调控制台。</p>
        </div>
        <span class="meta-pill">{{ hasBoundDevice ? focusRiskLabel : "未绑定设备" }}</span>
      </header>

      <div v-if="hasBoundDevice" class="family-overview-stack">
        <section class="family-summary-banner" :class="`tone-${focusTone}`">
          <div class="family-summary-copy">
            <p class="section-eyebrow">Summary</p>
            <h3>{{ focusSummaryTitle }}</h3>
            <p class="summary-body">{{ focusSummaryCopy }}</p>
            <div class="summary-meta">
              <span class="status-tag tone-info">房间 {{ focusRow?.apartment ?? "--" }}</span>
              <span class="status-tag tone-neutral">设备 {{ selectedDeviceMac || "未选择" }}</span>
              <span class="status-tag tone-neutral">更新时间 {{ focusUpdatedLabel }}</span>
            </div>
          </div>
          <div class="family-summary-score">
            <span>风险等级</span>
            <strong>{{ focusRiskLabel }}</strong>
            <p>{{ focusAlarm ? "已进入告警处理链路，请优先查看异常到报警流。" : "当前没有活跃告警，可继续结合报告与建议动作判断。" }}</p>
          </div>
        </section>

        <div class="family-health-grid family-health-grid--demo">
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

        <article class="family-trend-panel">
          <div class="panel-head">
            <div>
              <h3>近阶段样本摘要</h3>
              <p class="panel-subtitle">{{ familyTrendHeadline }}</p>
            </div>
            <span class="meta-pill">最近 {{ familyTrendPreview.length || 0 }} 次样本</span>
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
                <span>Temp {{ point.temperature.toFixed(1) }}°C</span>
              </div>
            </article>
          </div>
          <div v-else class="state-block state-empty">
            <strong>等待趋势数据</strong>
            <p>设备已绑定，但近阶段样本还没有同步到趋势区。稍后刷新后会显示最近几次样本摘要。</p>
          </div>
        </article>

        <div class="family-chain-grid">
          <HealthEvaluationPanel
            :is-bound="hasBoundDevice"
            :subject-name="focusRow?.name ?? '等待选择'"
            :device-mac="selectedDeviceMac"
            :evaluation="currentHealthEvaluation"
            :report-summary="currentHealthReportSummary"
            :generated-report="generatedHealthReport"
            :report-loading="reportLoading"
            :report-error="reportError"
            @generate-report="emit('generateReport')"
          />
          <AlarmEscalationPanel
            :sample="focusLatest"
            :trend="focusTrend"
            :focus-alarm="focusAlarm"
          />
        </div>
      </div>

      <div v-else class="state-block state-empty state-large">
        <strong>当前账号下的老人尚未绑定设备</strong>
        <p>{{ basicAdvice }}</p>
      </div>
    </article>

    <AssistantPanel
      v-if="hasBoundDevice"
      class="family-agent"
      :device-mac="selectedDeviceMac"
      :subject-name="focusRow?.name ?? '等待选择'"
      :sample="focusLatest"
      :risk-label="focusRiskLabel"
      :focus-alarm="focusAlarm"
      :trend-count="focusTrend.length"
    />
    <article v-else class="panel family-agent">
      <h2>家庭智能体</h2>
      <p class="subtle-copy">当前没有绑定设备，暂不发起设备级分析请求。绑定设备后，这里会显示基于实时数据和趋势的建议性解读。</p>
    </article>
  </section>
</template>
