<script setup lang="ts">
import { computed, ref } from "vue";
import type { DeviceRecord, HealthSample } from "../api/client";

const props = defineProps<{
  devices: DeviceRecord[];
  latest: Record<string, HealthSample>;
  selectedMac: string;
}>();

defineEmits<{
  (event: "select", mac: string): void;
}>();

const search = ref("");
const filter = ref("all");

function riskTone(sample?: HealthSample) {
  if (!sample) return "idle";
  if (sample.sos_flag || sample.blood_oxygen < 90 || sample.heart_rate > 180 || sample.heart_rate < 40) {
    return "high";
  }
  if (sample.temperature > 38 || sample.heart_rate > 110 || sample.blood_oxygen < 93) {
    return "medium";
  }
  return "low";
}

function riskLabel(sample?: HealthSample) {
  return {
    idle: "待同步",
    low: "平稳",
    medium: "关注",
    high: "高风险",
  }[riskTone(sample)];
}

function statusLabel(status: string) {
  if (status === "warning") return "告警";
  if (status === "offline") return "离线";
  return "在线";
}

const filteredDevices = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  return props.devices.filter((device) => {
    const sample = props.latest[device.mac_address];
    const tone = riskTone(sample);
    const matchesKeyword = !keyword || device.device_name.toLowerCase().includes(keyword) || device.mac_address.toLowerCase().includes(keyword);
    const matchesFilter =
      filter.value === "all" ||
      (filter.value === "high" && tone === "high") ||
      (filter.value === "attention" && tone === "medium") ||
      (filter.value === "sos" && Boolean(sample?.sos_flag));
    return matchesKeyword && matchesFilter;
  });
});
</script>

<template>
  <section class="panel device-panel">
    <div class="panel-head">
      <div>
        <h2>设备矩阵</h2>
        <p class="panel-subtitle">多设备实时总览，快速定位高风险对象与当前主视角设备。</p>
      </div>
      <span>{{ filteredDevices.length }} / {{ devices.length }} 台</span>
    </div>
    <div class="toolbar-stack">
      <input v-model="search" class="search-input" placeholder="搜索设备名或 MAC" />
      <div class="filter-row">
        <button class="filter-chip" :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
        <button class="filter-chip" :class="{ active: filter === 'high' }" @click="filter = 'high'">高风险</button>
        <button class="filter-chip" :class="{ active: filter === 'attention' }" @click="filter = 'attention'">需关注</button>
        <button class="filter-chip" :class="{ active: filter === 'sos' }" @click="filter = 'sos'">SOS</button>
      </div>
    </div>
    <div class="device-list">
      <button
        v-for="device in filteredDevices"
        :key="device.mac_address"
        class="device-card"
        :class="[
          { active: selectedMac === device.mac_address },
          `tone-${riskTone(latest[device.mac_address])}`,
        ]"
        @click="$emit('select', device.mac_address)"
      >
        <div class="device-card-top">
          <div>
            <p>{{ device.device_name }}</p>
            <strong>{{ device.mac_address }}</strong>
          </div>
          <span class="status-pill">{{ statusLabel(device.status) }}</span>
        </div>
        <div v-if="latest[device.mac_address]" class="metrics">
          <span>HR {{ latest[device.mac_address].heart_rate }}</span>
          <span>T {{ latest[device.mac_address].temperature.toFixed(1) }}℃</span>
          <span>SpO2 {{ latest[device.mac_address].blood_oxygen }}%</span>
          <span>分 {{ latest[device.mac_address].health_score ?? '--' }}</span>
        </div>
        <p v-else class="empty-copy">等待实时数据接入</p>
        <div class="device-card-footer">
          <span class="risk-chip" :class="`risk-${riskTone(latest[device.mac_address])}`">
            {{ riskLabel(latest[device.mac_address]) }}
          </span>
          <span v-if="latest[device.mac_address]?.sos_flag" class="sos-chip">SOS</span>
        </div>
      </button>
      <p v-if="!filteredDevices.length" class="empty-copy">当前筛选条件下没有匹配设备。</p>
    </div>
  </section>
</template>
