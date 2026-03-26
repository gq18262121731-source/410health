<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

type ChartAttachment = {
  id: string;
  title: string;
  summary?: string;
  echarts_option?: Record<string, unknown>;
};

const props = defineProps<{
  chart: ChartAttachment;
  height?: number;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const resolvedHeight = computed(() => props.height ?? 320);

// Deep-merge dark theme overrides into any echarts option coming from backend
function applyDarkTheme(option: Record<string, unknown>): Record<string, unknown> {
  const axisStyle = {
    axisLine: { lineStyle: { color: "rgba(56,189,248,0.18)" } },
    splitLine: { lineStyle: { color: "rgba(56,189,248,0.07)", type: "dashed" } },
    axisLabel: { color: "#4d7a94", fontSize: 12 },
    nameTextStyle: { color: "#6ea8c8" },
  };

  const applyAxis = (axes: unknown) => {
    if (!axes) return axes;
    const arr = Array.isArray(axes) ? axes : [axes];
    return arr.map((ax: Record<string, unknown>) => ({ ...axisStyle, ...ax,
      axisLine: { ...(axisStyle.axisLine), ...((ax.axisLine as object) ?? {}) },
      splitLine: { ...(axisStyle.splitLine), ...((ax.splitLine as object) ?? {}) },
      axisLabel: { ...(axisStyle.axisLabel), ...((ax.axisLabel as object) ?? {}) },
    }));
  };

  // Upgrade series: thicker lines, glowing area, bigger symbols
  const PALETTE = ["#22d3ee", "#f97316", "#a78bfa", "#34d399", "#fb923c", "#60a5fa", "#f472b6"];
  const series = Array.isArray(option.series)
    ? (option.series as Record<string, unknown>[]).map((s, i) => ({
        smooth: true,
        showSymbol: false,
        symbolSize: 6,
        ...s,
        lineStyle: { width: 2.5, color: PALETTE[i % PALETTE.length], ...(s.lineStyle as object ?? {}) },
        areaStyle: s.type === "line" ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: (PALETTE[i % PALETTE.length] + "44") },
            { offset: 1, color: (PALETTE[i % PALETTE.length] + "05") },
          ]),
          ...(s.areaStyle as object ?? {}),
        } : s.areaStyle,
        itemStyle: { color: PALETTE[i % PALETTE.length], ...(s.itemStyle as object ?? {}) },
      }))
    : option.series;

  return {
    ...option,
    backgroundColor: "transparent",
    textStyle: { color: "#7eb8d4", fontFamily: "'Manrope','Noto Sans SC',sans-serif" },
    legend: {
      top: 8,
      textStyle: { color: "#6ea8c8", fontSize: 13 },
      inactiveColor: "#2d4a5a",
      ...((option.legend as object) ?? {}),
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(8,16,30,0.96)",
      borderColor: "rgba(34,211,238,0.20)",
      borderWidth: 1,
      textStyle: { color: "#e2f0ff", fontSize: 13 },
      axisPointer: {
        lineStyle: { color: "rgba(34,211,238,0.30)", width: 1.5, type: "dashed" },
      },
      ...((option.tooltip as object) ?? {}),
    },
    grid: option.grid ?? { left: "4%", right: "3%", top: 48, bottom: 32, containLabel: true },
    xAxis: applyAxis(option.xAxis),
    yAxis: applyAxis(option.yAxis),
    series,
  };
}

function renderChart() {
  if (!chartRef.value) return;
  chartInstance ??= echarts.init(chartRef.value, undefined, { renderer: "canvas" });
  const base = (props.chart.echarts_option ?? {}) as Record<string, unknown>;
  chartInstance.setOption(applyDarkTheme(base) as echarts.EChartsCoreOption, true);
  chartInstance.resize();
}

function handleResize() {
  chartInstance?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener("resize", handleResize);
});

watch(() => props.chart, renderChart, { deep: true });

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});
</script>

<template>
  <article class="agent-chart-card">
    <header class="agent-chart-card__head">
      <div>
        <h4>{{ chart.title }}</h4>
        <p v-if="chart.summary">{{ chart.summary }}</p>
      </div>
      <span class="agent-chart-card__badge">CHART</span>
    </header>
    <div ref="chartRef" class="agent-chart-card__canvas" :style="{ height: `${resolvedHeight}px` }"></div>
  </article>
</template>

<style scoped>
.agent-chart-card {
  display: grid;
  gap: 14px;
  padding: 20px;
  border-radius: 24px;
  background:
    linear-gradient(160deg, rgba(14, 22, 42, 0.98) 0%, rgba(9, 14, 28, 0.99) 100%),
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.06), transparent 50%);
  border: 1px solid rgba(56, 189, 248, 0.14);
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.32), inset 0 1px 0 rgba(56, 189, 248, 0.06);
  position: relative;
  overflow: hidden;
}

.agent-chart-card::before {
  content: '';
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, #22d3ee 0%, #38bdf8 40%, transparent 100%);
  border-radius: 24px 24px 0 0;
  opacity: 0.6;
}

.agent-chart-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.agent-chart-card__head h4 {
  margin: 0;
  color: #e2f0ff;
  font-size: 1.02rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.agent-chart-card__head p {
  margin: 6px 0 0;
  color: #6ea8c8;
  line-height: 1.65;
  font-size: 0.84rem;
}

.agent-chart-card__badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.10);
  color: #22d3ee;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  border: 1px solid rgba(34, 211, 238, 0.18);
  flex-shrink: 0;
  margin-top: 2px;
}

.agent-chart-card__canvas {
  width: 100%;
  min-height: 220px;
  border-radius: 16px;
  background: rgba(7, 12, 22, 0.60);
  border: 1px solid rgba(56, 189, 248, 0.08);
}
</style>
