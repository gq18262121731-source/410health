<script setup lang="ts">
import { computed } from "vue";

type PosePoint = {
  index: number;
  name: string;
  x: number;
  y: number;
  score: number;
  tracked?: boolean;
  estimated?: boolean;
};

type PoseConnection = {
  from: number;
  to: number;
  part: string;
};

const props = defineProps<{
  points: PosePoint[];
  connections: PoseConnection[];
  bbox?: number[] | null;
  title?: string;
  labelMode?: "index" | "name";
  highlightParts?: string[];
  highlightPointIndices?: number[];
  selectedPointIndex?: number | null;
}>();

const emit = defineEmits<{
  selectPoint: [point: PosePoint];
}>();

const viewport = computed(() => {
  const points = props.points ?? [];
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  if (!xs.length || !ys.length) {
    return { minX: 0, minY: 0, width: 100, height: 160 };
  }
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = Math.max(120, maxX - minX + 80);
  const height = Math.max(180, maxY - minY + 100);
  return {
    minX: minX - 40,
    minY: minY - 40,
    width,
    height,
  };
});

const lines = computed(() =>
  (props.connections ?? []).map((connection) => {
    const start = props.points.find((point) => point.index === connection.from);
    const end = props.points.find((point) => point.index === connection.to);
    return {
      ...connection,
      start,
      end,
    };
  }).filter((item) => item.start && item.end && (item.start.score >= 0.18) && (item.end.score >= 0.18)),
);

function pointTone(point: PosePoint) {
  if (point.estimated) return "is-estimated";
  if (point.tracked) return "is-tracked";
  return "is-direct";
}

function lineHighlight(part: string) {
  return (props.highlightParts ?? []).includes(part);
}

function pointHighlight(index: number) {
  return (props.highlightPointIndices ?? []).includes(index);
}

function pointSelected(index: number) {
  return props.selectedPointIndex === index;
}
</script>

<template>
  <figure class="target-pose-skeleton">
    <figcaption>{{ title ?? "目标人物骨架" }}</figcaption>
    <div class="target-pose-skeleton__frame">
      <svg
        v-if="points.length"
        class="target-pose-skeleton__svg"
        :viewBox="`${viewport.minX} ${viewport.minY} ${viewport.width} ${viewport.height}`"
        role="img"
        aria-label="目标人物火柴人骨架"
      >
        <rect
          v-if="bbox && bbox.length === 4"
          :x="bbox[0]"
          :y="bbox[1]"
          :width="bbox[2] - bbox[0]"
          :height="bbox[3] - bbox[1]"
          class="target-pose-skeleton__bbox"
        />
        <line
          v-for="line in lines"
          :key="`${line.from}-${line.to}`"
          :x1="line.start!.x"
          :y1="line.start!.y"
          :x2="line.end!.x"
          :y2="line.end!.y"
          class="target-pose-skeleton__line"
          :class="[`part-${line.part}`, { 'is-highlighted': lineHighlight(line.part) }]"
        />
        <g v-for="point in points" :key="point.index">
          <circle
            v-if="point.score >= 0.12"
            :cx="point.x"
            :cy="point.y"
            r="5.5"
            class="target-pose-skeleton__point"
            :class="[pointTone(point), { 'is-highlighted': pointHighlight(point.index), 'is-selected': pointSelected(point.index) }]"
            @click="emit('selectPoint', point)"
          />
          <text
            v-if="point.score >= 0.32"
            :x="point.x + 7"
            :y="point.y - 7"
            class="target-pose-skeleton__label"
          >
            {{ props.labelMode === "name" ? point.name : point.index }}
          </text>
        </g>
      </svg>
      <div v-else class="target-pose-skeleton__empty">
        <strong>暂无骨架</strong>
        <p>执行目标姿态分析后，这里会展示火柴人骨架和 ROI。</p>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.target-pose-skeleton {
  display: grid;
  gap: 10px;
  margin: 0;
}

.target-pose-skeleton figcaption {
  font-size: 0.88rem;
  color: var(--text-sub);
  font-weight: 700;
}

.target-pose-skeleton__frame {
  min-height: 360px;
  border-radius: 22px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background:
    radial-gradient(circle at 15% 0%, rgba(59, 130, 246, 0.18), transparent 30%),
    linear-gradient(180deg, #08111f 0%, #0f172a 100%);
  overflow: hidden;
  position: relative;
}

.target-pose-skeleton__svg {
  width: 100%;
  height: 100%;
  display: block;
}

.target-pose-skeleton__bbox {
  fill: rgba(59, 130, 246, 0.08);
  stroke: rgba(96, 165, 250, 0.9);
  stroke-width: 2.5;
  rx: 10;
}

.target-pose-skeleton__line {
  stroke-linecap: round;
  stroke-width: 4;
  opacity: 0.95;
}

.target-pose-skeleton__line.part-head {
  stroke: #fbbf24;
}

.target-pose-skeleton__line.part-torso {
  stroke: #60a5fa;
}

.target-pose-skeleton__line.part-left_arm,
.target-pose-skeleton__line.part-right_arm {
  stroke: #34d399;
}

.target-pose-skeleton__line.part-left_leg,
.target-pose-skeleton__line.part-right_leg {
  stroke: #f87171;
}

.target-pose-skeleton__line.is-highlighted {
  stroke-width: 6;
  filter: drop-shadow(0 0 6px rgba(255, 255, 255, 0.42));
}

.target-pose-skeleton__point {
  stroke: rgba(15, 23, 42, 0.92);
  stroke-width: 1.5;
}

.target-pose-skeleton__point.is-direct {
  fill: #ffffff;
}

.target-pose-skeleton__point.is-tracked {
  fill: #22c55e;
}

.target-pose-skeleton__point.is-estimated {
  fill: #f59e0b;
}

.target-pose-skeleton__point.is-highlighted {
  r: 7;
  stroke: #ffffff;
  stroke-width: 2;
  filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.35));
}

.target-pose-skeleton__point.is-selected {
  fill: #f43f5e;
  stroke: #ffffff;
  stroke-width: 2.5;
  filter: drop-shadow(0 0 10px rgba(244, 63, 94, 0.45));
}

.target-pose-skeleton__label {
  fill: rgba(255, 255, 255, 0.88);
  font-size: 8px;
  font-weight: 700;
}

.target-pose-skeleton__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.9);
  text-align: center;
  padding: 24px;
}

.target-pose-skeleton__empty p {
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
}
</style>
