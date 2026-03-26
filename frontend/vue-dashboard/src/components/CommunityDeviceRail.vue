<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import type { CommunityDashboardDeviceItem } from "../api/client";
import { riskLevelToChinese } from "../utils/riskLevel";

const props = defineProps<{
  devices: CommunityDashboardDeviceItem[];
  selectedDeviceMac: string;
}>();

const emit = defineEmits<{
  select: [mac: string];
}>();

type DeviceTone = "sos" | "pending" | "risk-high" | "risk-medium" | "risk-low";

const railGridRef = ref<HTMLElement | null>(null);

function deviceTone(device: CommunityDashboardDeviceItem): DeviceTone {
  if (device.sos_active) return "sos";
  if (device.device_status === "pending") return "pending";
  if (device.structured_health?.risk_level === "critical" || device.risk_level === "high") return "risk-high";
  if (
    device.structured_health?.risk_level === "warning"
    || device.structured_health?.risk_level === "attention"
    || device.risk_level === "medium"
  ) {
    return "risk-medium";
  }
  return "risk-low";
}

function deviceLabel(device: CommunityDashboardDeviceItem): string {
  if (device.sos_active) return "SOS";
  if (device.device_status === "pending") return "待激活";
  if (device.device_status === "warning") return "告警中";
  if (device.device_status === "offline") return "离线";
  return "在线";
}

function deviceTitle(device: CommunityDashboardDeviceItem): string {
  return device.elder_name ? `${device.elder_name} / ${device.device_name}` : `${device.device_name} / 未归属`;
}

function deviceMeta(device: CommunityDashboardDeviceItem): string {
  if (device.sos_active) {
    return `紧急求助 · ${device.active_sos_trigger === "long_press" ? "长按求助" : "双击求助"}`;
  }
  if (device.activation_state === "pending") return "等待首包";
  const risk = riskLevelToChinese(device.structured_health?.risk_level ?? device.risk_level);
  if (device.elder_name) return `风险 ${risk}`;
  return `未归属设备 · ${risk}`;
}

const pendingCount = computed(() => props.devices.filter((device) => device.device_status === "pending").length);

async function scrollSelectedIntoView() {
  if (!props.selectedDeviceMac) return;
  await nextTick();
  const target = railGridRef.value?.querySelector<HTMLElement>(`[data-device-mac="${props.selectedDeviceMac}"]`);
  target?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
}

watch(() => props.selectedDeviceMac, () => {
  void scrollSelectedIntoView();
});

onMounted(() => {
  void scrollSelectedIntoView();
});
</script>

<template>
  <section class="device-rail">
    <div class="device-rail__head">
      <div>
        <p class="section-eyebrow">Device Rail</p>
        <h2>设备轨道</h2>
      </div>
      <small>已注册设备会先进入轨道，收到首个实时包后自动切换到在线监护。</small>
    </div>

    <div class="device-rail__meta">
      <span class="summary-badge">当前设备 {{ devices.length }}</span>
      <span class="summary-badge">待激活 {{ pendingCount }}</span>
    </div>

    <div ref="railGridRef" class="device-rail__grid">
      <button
        v-for="device in devices"
        :key="device.device_mac"
        type="button"
        class="device-pill"
        :data-device-mac="device.device_mac"
        :class="[deviceTone(device), { 'device-pill--active': selectedDeviceMac === device.device_mac }]"
        @click="emit('select', device.device_mac)"
      >
        <div class="device-pill__top">
          <strong>{{ deviceTitle(device) }}</strong>
          <span class="device-pill__state">{{ deviceLabel(device) }}</span>
        </div>
        <small>{{ device.device_mac }}</small>
        <span class="device-pill__meta">
          {{ deviceMeta(device) }}
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.device-rail {
  display: grid;
  gap: 12px;
}

.device-rail__head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-end;
}

.device-rail__head h2 {
  margin: 0;
  color: #e2f0ff;
  font-family: var(--font-display);
}

.device-rail__head small,
.device-pill small,
.device-pill__meta {
  color: #4d7a94;
  font-size: 0.82rem;
}

.device-rail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.device-rail__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.device-pill {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid rgba(56, 189, 248, 0.12);
  background: rgba(13, 20, 38, 0.96);
  text-align: left;
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.device-pill:hover,
.device-pill--active {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.28);
}

.device-pill--active {
  border-color: rgba(34, 211, 238, 0.40);
  background: rgba(18, 28, 52, 0.98);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.14), 0 14px 28px rgba(0, 0, 0, 0.28);
}

.device-pill__top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.device-pill strong {
  color: #c8e0f4;
  font-size: 0.96rem;
}

.device-pill__state {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
  flex-shrink: 0;
}

.pending {
  border-color: rgba(251, 191, 36, 0.22);
  background: rgba(20, 16, 8, 0.96);
}

.pending .device-pill__state {
  background: rgba(251, 191, 36, 0.14);
  color: #fbbf24;
}

.sos {
  border-color: rgba(248, 113, 122, 0.50);
  background: rgba(28, 10, 12, 0.98);
  box-shadow: 0 0 0 1px rgba(248, 113, 122, 0.14), 0 12px 28px rgba(0, 0, 0, 0.36);
}

.sos .device-pill__state {
  background: rgba(248, 113, 122, 0.16);
  color: #f87171;
}

.risk-high {
  border-color: rgba(248, 113, 122, 0.24);
  background: rgba(22, 10, 12, 0.96);
}

.risk-high .device-pill__state {
  background: rgba(248, 113, 122, 0.14);
  color: #f87171;
}

.risk-medium {
  border-color: rgba(251, 146, 60, 0.24);
  background: rgba(20, 14, 8, 0.96);
}

.risk-medium .device-pill__state {
  background: rgba(251, 146, 60, 0.14);
  color: #fb923c;
}

.risk-low {
  border-color: rgba(52, 211, 153, 0.18);
  background: rgba(8, 18, 14, 0.96);
}

.risk-low .device-pill__state {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
}

@media (max-width: 760px) {
  .device-rail__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .device-rail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
