<script setup lang="ts">
import { computed } from "vue";
import type { CommunityDashboardDeviceItem } from "../api/client";

const props = defineProps<{
  device: CommunityDashboardDeviceItem | null;
}>();

const structured = computed(() => props.device?.structured_health ?? null);

const scoreBreakdown = computed(() => [
  {
    label: "最终分",
    value: structured.value?.health_score?.toFixed(1) ?? (props.device?.latest_health_score?.toString() ?? "--"),
  },
  {
    label: "规则分",
    value: structured.value?.rule_health_score?.toFixed(1) ?? "--",
  },
  {
    label: "模型分",
    value: structured.value?.model_health_score?.toFixed(1) ?? "--",
  },
  {
    label: "推荐动作",
    value: structured.value?.recommendation_code ?? "PENDING",
  },
]);

const triggerReasons = computed(() =>
  structured.value?.trigger_reasons?.length ? structured.value.trigger_reasons : props.device?.risk_reasons ?? [],
);

const sosSummary = computed(() => {
  if (!props.device?.sos_active) return null;
  return props.device.active_sos_trigger === "long_press" ? "长按 SOS 求助" : "双击 SOS 求助";
});

const deviceSummary = computed(() => {
  if (!props.device) {
    return {
      title: "尚未选择设备",
      subtitle: "从上方设备轨道中选择一个设备后，这里会显示评分详情和当前解释。",
    };
  }

  if (props.device.device_status === "pending") {
    return {
      title: props.device.elder_name ? `${props.device.elder_name} / ${props.device.device_name}` : `${props.device.device_name} / 未归属`,
      subtitle: props.device.elder_name
        ? "设备已注册，等待串口采集器收到首个 T10 实时包。"
        : "设备已登记到台账，当前暂未绑定成员，等待串口采集器收到首个 T10 实时包。",
    };
  }

  return {
    title: props.device.elder_name ? `${props.device.elder_name} / ${props.device.device_name}` : `${props.device.device_name} / 未归属`,
    subtitle: props.device.elder_name
      ? `${props.device.device_mac} · ${props.device.apartment ?? "未分配房间"} · ${props.device.device_status}`
      : `${props.device.device_mac} · 当前暂未绑定成员 · ${props.device.device_status}`,
  };
});
</script>

<template>
  <article class="panel inspector-panel" :class="{ 'inspector-panel--sos': device?.sos_active }">
    <div class="inspector-panel__head">
      <div>
        <p class="section-eyebrow">Selected Device</p>
        <h2>{{ deviceSummary.title }}</h2>
        <p class="panel-subtitle">{{ deviceSummary.subtitle }}</p>
      </div>
      <span class="inspector-panel__score">
        {{ structured?.health_score?.toFixed(1) ?? device?.latest_health_score ?? "--" }}
      </span>
    </div>

    <p v-if="sosSummary" class="inspector-panel__sos-banner">
      当前设备存在未确认的 SOS 求助：{{ sosSummary }}
    </p>

    <div class="inspector-panel__scores">
      <article v-for="item in scoreBreakdown" :key="item.label" class="score-breakdown-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <p v-if="structured?.score_adjustment_reason" class="inspector-panel__note">
      {{ structured.score_adjustment_reason }}
    </p>

    <div class="inspector-panel__tags">
      <span v-if="sosSummary" class="signal-chip signal-chip--sos">
        {{ sosSummary }}
      </span>
      <span v-for="tag in structured?.abnormal_tags ?? []" :key="tag" class="signal-chip">
        {{ tag }}
      </span>
      <span v-if="!(structured?.abnormal_tags?.length) && !sosSummary" class="signal-chip muted">
        {{ device?.device_status === "pending" ? "等待首包激活" : "当前没有持续异常标签" }}
      </span>
    </div>

    <ul class="reason-list">
      <li v-if="sosSummary">已触发真实设备 SOS 联动，请优先联系对应老人并核查现场。</li>
      <li v-for="item in triggerReasons" :key="item">{{ item }}</li>
      <li v-if="!triggerReasons.length && !sosSummary">
        {{ device?.device_status === "pending" ? "当前设备还未收到首个串口实时包。" : "当前还没有明确的触发原因。" }}
      </li>
    </ul>
  </article>
</template>

<style scoped>
.inspector-panel {
  display: grid;
  gap: 14px;
}

.inspector-panel--sos {
  border-color: rgba(248, 113, 122, 0.30);
  box-shadow: 0 18px 44px rgba(200, 30, 40, 0.18);
}

.inspector-panel__head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.inspector-panel__head h2 {
  margin: 0;
  font-family: var(--font-display);
  color: #e2f0ff;
}

.panel-subtitle {
  margin: 8px 0 0;
  color: #6ea8c8;
  line-height: 1.6;
}

.inspector-panel__score {
  min-width: 82px;
  padding: 12px 14px;
  border-radius: 18px;
  background: rgba(34, 211, 238, 0.10);
  color: #22d3ee;
  text-align: center;
  font-size: 1.18rem;
  font-weight: 700;
  border: 1px solid rgba(34, 211, 238, 0.20);
}

.inspector-panel__sos-banner {
  margin: 0;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 113, 122, 0.10);
  border: 1px solid rgba(248, 113, 122, 0.24);
  color: #f87171;
  font-weight: 700;
}

.inspector-panel__scores {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.score-breakdown-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(13, 20, 38, 0.96);
  border: 1px solid rgba(56, 189, 248, 0.10);
}

.score-breakdown-card span {
  color: #4d7a94;
  font-size: 0.85rem;
  font-weight: 600;
}

.score-breakdown-card strong {
  color: #c8e0f4;
  font-size: 1.1rem;
  font-weight: 700;
}

.inspector-panel__note {
  margin: 0;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(34, 211, 238, 0.06);
  color: #6ea8c8;
  line-height: 1.7;
  border: 1px solid rgba(34, 211, 238, 0.10);
}

.inspector-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.signal-chip {
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.10);
  color: #22d3ee;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid rgba(34, 211, 238, 0.18);
}

.signal-chip--sos {
  background: rgba(248, 113, 122, 0.12);
  color: #f87171;
  border-color: rgba(248, 113, 122, 0.24);
}

.signal-chip.muted {
  background: rgba(255, 255, 255, 0.04);
  color: #4d7a94;
  border-color: rgba(56, 189, 248, 0.08);
}

.reason-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 10px;
  color: #c8e0f4;
  line-height: 1.7;
}

@media (max-width: 760px) {
  .inspector-panel__head {
    flex-direction: column;
  }

  .inspector-panel__scores {
    grid-template-columns: 1fr;
  }
}
</style>
