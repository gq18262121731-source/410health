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
  imageWidth: number;
  imageHeight: number;
  bbox?: number[] | null;
  labelMode?: "index" | "name";
  highlightParts?: string[];
  highlightPointIndices?: number[];
}>();

const lines = computed(() =>
  (props.connections ?? []).map((connection) => {
    const start = props.points.find((point) => point.index === connection.from);
    const end = props.points.find((point) => point.index === connection.to);
    return {
      ...connection,
      start,
      end,
    };
  }).filter((item) => item.start && item.end && item.start.score >= 0.18 && item.end.score >= 0.18),
);

function lineHighlight(part: string) {
  return (props.highlightParts ?? []).includes(part);
}

function pointHighlight(index: number) {
  return (props.highlightPointIndices ?? []).includes(index);
}
</script>

<template>
  <svg
    v-if="imageWidth > 0 && imageHeight > 0"
    class="target-pose-overlay"
    :viewBox="`0 0 ${imageWidth} ${imageHeight}`"
    aria-hidden="true"
  >
    <rect
      v-if="bbox && bbox.length === 4"
      :x="bbox[0]"
      :y="bbox[1]"
      :width="bbox[2] - bbox[0]"
      :height="bbox[3] - bbox[1]"
      class="target-pose-overlay__bbox"
    />
    <line
      v-for="line in lines"
      :key="`${line.from}-${line.to}`"
      :x1="line.start!.x"
      :y1="line.start!.y"
      :x2="line.end!.x"
      :y2="line.end!.y"
      class="target-pose-overlay__line"
      :class="[`part-${line.part}`, { 'is-highlighted': lineHighlight(line.part) }]"
    />
    <g v-for="point in points" :key="point.index">
      <circle
        v-if="point.score >= 0.12"
        :cx="point.x"
        :cy="point.y"
        r="5"
        class="target-pose-overlay__point"
        :class="{
          'is-tracked': point.tracked,
          'is-estimated': point.estimated,
          'is-highlighted': pointHighlight(point.index),
        }"
      />
      <text
        v-if="point.score >= 0.32"
        :x="point.x + 7"
        :y="point.y - 7"
        class="target-pose-overlay__label"
      >
        {{ props.labelMode === "name" ? point.name : point.index }}
      </text>
    </g>
  </svg>
</template>

<style scoped>
.target-pose-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.target-pose-overlay__bbox {
  fill: rgba(59, 130, 246, 0.08);
  stroke: rgba(248, 113, 113, 0.95);
  stroke-width: 3;
  rx: 10;
}

.target-pose-overlay__line {
  stroke-linecap: round;
  stroke-width: 4;
  opacity: 0.95;
}

.target-pose-overlay__line.part-head {
  stroke: #fbbf24;
}

.target-pose-overlay__line.part-torso {
  stroke: #60a5fa;
}

.target-pose-overlay__line.part-left_arm,
.target-pose-overlay__line.part-right_arm {
  stroke: #34d399;
}

.target-pose-overlay__line.part-left_leg,
.target-pose-overlay__line.part-right_leg {
  stroke: #f87171;
}

.target-pose-overlay__line.is-highlighted {
  stroke-width: 6;
  filter: drop-shadow(0 0 6px rgba(255, 255, 255, 0.4));
}

.target-pose-overlay__point {
  fill: #ffffff;
  stroke: rgba(15, 23, 42, 0.92);
  stroke-width: 1.5;
}

.target-pose-overlay__point.is-tracked {
  fill: #22c55e;
}

.target-pose-overlay__point.is-estimated {
  fill: #f59e0b;
}

.target-pose-overlay__point.is-highlighted {
  fill: #f43f5e;
  stroke: #ffffff;
  stroke-width: 2.5;
  filter: drop-shadow(0 0 8px rgba(244, 63, 94, 0.4));
}

.target-pose-overlay__label {
  fill: rgba(255, 255, 255, 0.92);
  font-size: 10px;
  font-weight: 700;
}
</style>
