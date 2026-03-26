<script setup lang="ts">
import { LineChart, type LineSeriesOption } from "echarts/charts";
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  type GraphicComponentOption,
  type GridComponentOption,
  type LegendComponentOption,
  type TooltipComponentOption,
} from "echarts/components";
import { type ComposeOption, init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { CommunityDashboardDeviceItem, HealthSample } from "../api/client";
import { riskLevelToChinese } from "../utils/riskLevel";

use([CanvasRenderer, GraphicComponent, GridComponent, LegendComponent, LineChart, TooltipComponent]);

type RealtimeOption = ComposeOption<
  GridComponentOption | LegendComponentOption | TooltipComponentOption | GraphicComponentOption | LineSeriesOption
>;

const props = defineProps<{
  device: CommunityDashboardDeviceItem | null;
  samples: HealthSample[];
  currentSample?: HealthSample | null;
  awaitingRealtime?: boolean;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

function parseBloodPressure(value?: string | null) {
  if (!value) return { sbp: null, dbp: null };
  const [sbpRaw, dbpRaw] = value.split("/", 2);
  const sbp = Number.parseInt(sbpRaw ?? "", 10);
  const dbp = Number.parseInt(dbpRaw ?? "", 10);
  return {
    sbp: Number.isFinite(sbp) ? sbp : null,
    dbp: Number.isFinite(dbp) ? dbp : null,
  };
}

const hasSamples = computed(() => props.samples.length > 0);
const isPending = computed(() => props.device?.device_status === "pending");
const isAwaitingRealtime = computed(() => !!props.awaitingRealtime && props.device?.ingest_mode === "serial");
const currentSample = computed(() => props.currentSample ?? props.samples[props.samples.length - 1] ?? null);
const currentPressure = computed(() => parseBloodPressure(currentSample.value?.blood_pressure));
const showPointSymbols = computed(() => props.samples.length <= 2);
const chartSeries = computed(() => {
  const labels = props.samples.map((sample) =>
    new Date(sample.timestamp).toLocaleTimeString("zh-CN", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
  );
  const pressure = props.samples.map((sample) => parseBloodPressure(sample.blood_pressure));
  return {
    labels,
    heartRate: props.samples.map((sample) => sample.heart_rate),
    spo2: props.samples.map((sample) => sample.blood_oxygen),
    sbp: pressure.map((item) => item.sbp),
    dbp: pressure.map((item) => item.dbp),
    temperature: props.samples.map((sample) => sample.temperature),
  };
});

const temperatureAxisRange = computed(() => {
  const values = chartSeries.value.temperature.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!values.length) {
    return { min: 34, max: 42 };
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const min = Math.max(20, Math.floor(minValue) - 1);
  const max = Math.min(45, Math.max(min + 4, Math.ceil(maxValue) + 1));
  return { min, max };
});

const metricCards = computed(() => [
  {
    label: "心率",
    value: currentSample.value ? `${currentSample.value.heart_rate} bpm` : "--",
    tone: "heart",
  },
  {
    label: "血氧",
    value: currentSample.value ? `${currentSample.value.blood_oxygen}%` : "--",
    tone: "spo2",
  },
  {
    label: "血压",
    value:
      currentPressure.value.sbp !== null && currentPressure.value.dbp !== null
        ? `${currentPressure.value.sbp}/${currentPressure.value.dbp} mmHg`
        : "--",
    tone: "pressure",
  },
  {
    label: "体温",
    value: currentSample.value ? `${currentSample.value.temperature.toFixed(1)} °C` : "--",
    tone: "temp",
  },
  {
    label: "步数",
    value: currentSample.value?.steps != null ? `${currentSample.value.steps} steps` : "--",
    tone: "steps",
  },
]);

const structuredSummary = computed(() => props.device?.structured_health ?? null);
const structuredTags = computed(() => structuredSummary.value?.abnormal_tags ?? []);
const deviceMeta = computed(() => {
  if (!props.device) {
    return {
      title: "请选择一个设备",
      subtitle: "从设备轨道中选择一个设备后，这里会显示实时四参数变化。",
      badge: "未选择设备",
    };
  }

  if (props.device.device_status === "pending") {
    return {
      title: props.device.elder_name ? `${props.device.elder_name} / ${props.device.device_name}` : `${props.device.device_name} / 未归属`,
      subtitle: props.device.elder_name
        ? "设备已注册，等待串口采集器收到首个 T10 实时包。"
        : "设备已登记到台账，当前暂未绑定成员，等待串口采集器收到首个 T10 实时包。",
      badge: "待激活",
    };
  }

  if (isAwaitingRealtime.value) {
    return {
      title: props.device.elder_name ? `${props.device.elder_name} / ${props.device.device_name}` : `${props.device.device_name} / 未归属`,
      subtitle: `${props.device.device_mac} · 正在切换采集目标，等待新的实时串口数据`,
      badge: "接入中",
    };
  }

  return {
    title: props.device.elder_name ? `${props.device.elder_name} / ${props.device.device_name}` : `${props.device.device_name} / 未归属`,
    subtitle: props.device.elder_name
      ? `${props.device.device_mac} · ${props.device.apartment ?? "未分配房间"} · ${props.device.device_status}`
      : `${props.device.device_mac} · 当前暂未绑定成员 · ${props.device.device_status}`,
    badge: riskLevelToChinese(structuredSummary.value?.risk_level ?? props.device.risk_level),
  };
});

function buildChartOption(): RealtimeOption {
  return {
    backgroundColor: "transparent",
    animation: false,
    animationDuration: 0,
    animationDurationUpdate: 0,
    legend: {
      top: 8,
      left: 10,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: "#7eb8d4", fontSize: 13, fontWeight: 600 },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(8, 16, 30, 0.96)",
      borderColor: "rgba(34, 211, 238, 0.24)",
      textStyle: { color: "#e2f0ff" },
    },
    grid: [
      { left: "5%", top: 58, width: "41%", height: "29%" },
      { left: "55%", top: 58, width: "40%", height: "29%" },
      { left: "5%", top: "58%", width: "41%", height: "29%" },
      { left: "55%", top: "58%", width: "40%", height: "29%" },
    ],
    xAxis: Array.from({ length: 4 }, (_, index) => ({
      type: "category",
      gridIndex: index,
      boundaryGap: false,
      data: chartSeries.value.labels,
      axisLabel: { color: "#4d7a94", fontSize: 12, margin: 12 },
      axisLine: { lineStyle: { color: "rgba(56, 189, 248, 0.12)" } },
    })),
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        min: 40,
        max: 180,
        splitLine: { lineStyle: { color: "rgba(56, 189, 248, 0.08)" } },
        axisLabel: { color: "#4d7a94", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 1,
        min: 80,
        max: 100,
        splitLine: { lineStyle: { color: "rgba(56, 189, 248, 0.08)" } },
        axisLabel: { color: "#4d7a94", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 2,
        min: 40,
        max: 200,
        splitLine: { lineStyle: { color: "rgba(56, 189, 248, 0.08)" } },
        axisLabel: { color: "#4d7a94", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 3,
        min: temperatureAxisRange.value.min,
        max: temperatureAxisRange.value.max,
        splitLine: { lineStyle: { color: "rgba(56, 189, 248, 0.08)" } },
        axisLabel: { color: "#4d7a94", fontSize: 12 },
      },
    ],
    series: [
      {
        name: "心率",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.heartRate,
        lineStyle: { width: 3, color: "#ff6b57" },
        areaStyle: { color: "rgba(255, 107, 87, 0.10)" },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "rgba(255, 107, 87, 0.35)", type: "dashed", width: 1 },
          data: [
            { yAxis: 60, label: { formatter: "60", color: "#ff6b57", fontSize: 11 } },
            { yAxis: 100, label: { formatter: "100", color: "#ff6b57", fontSize: 11 } },
          ],
        },
      },
      {
        name: "血氧",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.spo2,
        lineStyle: { width: 3, color: "#17bebb" },
        areaStyle: { color: "rgba(23, 190, 187, 0.10)" },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "rgba(23, 190, 187, 0.35)", type: "dashed", width: 1 },
          data: [
            { yAxis: 95, label: { formatter: "95%", color: "#17bebb", fontSize: 11 } },
          ],
        },
      },
      {
        name: "收缩压",
        type: "line",
        xAxisIndex: 2,
        yAxisIndex: 2,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.sbp,
        lineStyle: { width: 2.5, color: "#9b5de5" },
      },
      {
        name: "舒张压",
        type: "line",
        xAxisIndex: 2,
        yAxisIndex: 2,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.dbp,
        lineStyle: { width: 2.5, color: "#5a189a" },
      },
      {
        name: "体温",
        type: "line",
        xAxisIndex: 3,
        yAxisIndex: 3,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.temperature,
        lineStyle: { width: 3, color: "#ff9f1c" },
        areaStyle: { color: "rgba(255, 159, 28, 0.10)" },
      },
    ],
    graphic: [
      { type: "text", left: "23%", top: 24, style: { text: "心率", fill: "#22d3ee", fontWeight: 700, fontSize: 20, align: "center" } },
      { type: "text", left: "73%", top: 24, style: { text: "血氧", fill: "#22d3ee", fontWeight: 700, fontSize: 20, align: "center" } },
      { type: "text", left: "23%", top: "52%", style: { text: "血压", fill: "#22d3ee", fontWeight: 700, fontSize: 20, align: "center" } },
      { type: "text", left: "73%", top: "52%", style: { text: "体温", fill: "#22d3ee", fontWeight: 700, fontSize: 20, align: "center" } },
    ],
  };
}

function updateChart() {
  if (!chartRef.value) return;
  chart ??= init(chartRef.value);
  chart.setOption(buildChartOption(), { notMerge: false });
}

function handleResize() {
  chart?.resize();
}

onMounted(() => {
  updateChart();
  window.addEventListener("resize", handleResize);
});

watch(() => [props.samples.length, props.device?.device_status, props.device?.ingest_mode], updateChart);
watch([chartSeries, showPointSymbols, temperatureAxisRange], updateChart);

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <section class="panel realtime-monitor-panel">
    <div class="monitor-hero">
      <div>
        <p class="section-eyebrow">Realtime Device Monitor</p>
        <h2>{{ deviceMeta.title }}</h2>
        <p class="monitor-subtitle">{{ deviceMeta.subtitle }}</p>
      </div>
      <div class="monitor-badges">
        <span class="monitor-badge">{{ deviceMeta.badge }}</span>
        <span class="monitor-badge subtle">
          模型评分 {{ structuredSummary?.health_score?.toFixed(1) ?? device?.latest_health_score ?? "--" }}
        </span>
      </div>
    </div>

    <div class="monitor-metrics">
      <article v-for="item in metricCards" :key="item.label" class="metric-plate" :data-tone="item.tone">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="monitor-context">
      <div class="monitor-chip-row">
        <span v-for="tag in structuredTags" :key="tag" class="signal-chip">{{ tag }}</span>
        <span v-if="!structuredTags.length" class="signal-chip muted">
          {{ isPending ? "等待首包激活" : isAwaitingRealtime ? "正在等待实时串口样本" : "当前没有持续异常标签" }}
        </span>
      </div>
      <p class="monitor-note">
        {{
          structuredSummary?.trigger_reasons?.[0]
            ?? (isPending
              ? "已注册，等待串口采集器收到首个 T10 实时包后自动开始监护。"
              : isAwaitingRealtime
                ? "当前已切换到这台真实设备，正在等待切换后的首个实时串口包。"
                : "实时曲线默认启用窗口稳定化，短时轻微波动不会立即触发正式异常事件。")
        }}
      </p>
    </div>

    <div class="monitor-chart-shell">
      <div ref="chartRef" class="monitor-chart"></div>
      <div v-if="!hasSamples" class="monitor-empty">
        <strong>{{ isPending ? "设备待激活" : isAwaitingRealtime ? "正在接入实时数据" : "暂未收到实时数据" }}</strong>
        <p>
          {{
            isPending
              ? "请确认采集器已连接并开始扫描，首个回应包到达后这里会自动切换为实时四参数曲线。"
              : isAwaitingRealtime
                ? "串口采集目标已切换，新的响应包到达后这里会立刻刷新。"
                : "选择一个在线设备，或等待下一次采样进入。"
          }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.realtime-monitor-panel {
  display: grid;
  width: 100%;
  gap: 18px;
  min-height: calc(100vh - 220px);
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 34%),
    linear-gradient(180deg, rgba(10, 16, 30, 0.99), rgba(7, 12, 22, 0.99));
}

.monitor-hero,
.monitor-badges,
.monitor-metrics,
.monitor-chip-row {
  display: flex;
  gap: 12px;
}

.monitor-hero {
  justify-content: space-between;
  align-items: flex-start;
}

.monitor-hero h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(2.15rem, 2.8vw, 3rem);
  color: #e2f0ff;
}

.monitor-subtitle,
.monitor-note {
  margin: 8px 0 0;
  color: rgba(110, 168, 200, 0.85);
  line-height: 1.7;
  font-size: 1rem;
}

.monitor-badges {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.monitor-badge {
  padding: 12px 16px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.15);
  color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.24);
  font-size: 0.94rem;
  font-weight: 600;
}

.monitor-badge.subtle {
  background: rgba(255, 255, 255, 0.06);
  color: #a8d8f0;
  border: 1px solid rgba(56, 189, 248, 0.16);
}

.monitor-metrics {
  flex-wrap: wrap;
}

.metric-plate {
  flex: 1 1 180px;
  min-width: 0;
  padding: 22px 20px;
  border-radius: 20px;
  background: rgba(13, 20, 38, 0.96);
  border: 1px solid rgba(56, 189, 248, 0.14);
  display: grid;
  gap: 6px;
  text-align: center;
  justify-items: center;
}

.metric-plate span {
  color: rgba(110, 168, 200, 0.95);
  font-size: 1.2rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
}

.metric-plate strong {
  color: #e2f0ff;
  font-size: 2.2rem;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
}

.metric-plate[data-tone="heart"] strong {
  color: #ff6b7a;
}

.metric-plate[data-tone="spo2"] strong {
  color: #22d3ee;
}

.metric-plate[data-tone="pressure"] strong {
  color: #a78bfa;
}

.metric-plate[data-tone="temp"] strong {
  color: #fb923c;
}

.metric-plate[data-tone="steps"] strong {
  color: #60a5fa;
}

.monitor-context {
  display: grid;
  gap: 10px;
}

.monitor-chip-row {
  flex-wrap: wrap;
}

.signal-chip {
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.10);
  color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.20);
  font-size: 0.92rem;
  font-weight: 600;
}

.signal-chip.muted {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(110, 168, 200, 0.6);
  border: 1px solid rgba(56, 189, 248, 0.08);
}

.monitor-chart-shell {
  position: relative;
  width: 100%;
  min-width: 0;
}

.monitor-chart {
  height: min(74vh, 760px);
  min-height: 620px;
  width: 100%;
  display: block;
  border-radius: 28px;
  background: rgba(10, 16, 30, 0.96);
  border: 1px solid rgba(56, 189, 248, 0.12);
}

.monitor-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
  background: rgba(10, 16, 30, 0.94);
  border-radius: 28px;
}

.monitor-empty strong {
  color: #e2f0ff;
  font-size: 1.45rem;
}

.monitor-empty p {
  margin: 0;
  color: #6ea8c8;
  line-height: 1.7;
  font-size: 1rem;
  max-width: 520px;
}

@media (max-width: 960px) {
  .realtime-monitor-panel {
    min-height: auto;
  }

  .monitor-hero {
    flex-direction: column;
  }

  .monitor-badges {
    justify-content: flex-start;
  }

  .monitor-chart {
    height: 620px;
    min-height: 620px;
  }
}
</style>
