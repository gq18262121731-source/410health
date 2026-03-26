<script setup lang="ts">
import { computed } from "vue";
import type { CommunityRelationTopology } from "../api/client";

const props = defineProps<{
  topology: CommunityRelationTopology | null;
  selectedDeviceMac: string;
}>();

const emit = defineEmits<{
  (event: "select-device", mac: string): void;
}>();

const lanes = computed(() => props.topology?.lanes ?? []);
const unassignedDevices = computed(() => props.topology?.unassigned_devices ?? []);

function isSelectedDevice(id: string) {
  return id === props.selectedDeviceMac;
}
</script>

<template>
  <section class="panel topology-panel">
    <div class="topology-head">
      <div>
        <p class="section-eyebrow">Relation Topology</p>
        <h2>社区关系拓扑</h2>
        <p class="topology-subtitle">理清社区、老人、家属和手环之间的归属关系，并突出当前选中的实时监护设备。</p>
      </div>
      <div v-if="topology" class="topology-community">
        <span>Community Hub</span>
        <strong>{{ topology.community.label }}</strong>
        <small>{{ topology.community.subtitle }}</small>
      </div>
    </div>

    <div v-if="!lanes.length" class="topology-empty">
      当前还没有可展示的拓扑关系。请先注册老人、家属并完成设备绑定。
    </div>

    <div v-else class="lane-list">
      <article v-for="lane in lanes" :key="lane.elder.id" class="topology-lane">
        <div class="lane-column lane-families">
          <span class="lane-label">家属</span>
          <button
            v-for="family in lane.families"
            :key="family.id"
            type="button"
            class="node-chip node-chip--family"
          >
            <strong>{{ family.label }}</strong>
            <small>{{ family.subtitle }}</small>
          </button>
          <div v-if="!lane.families.length" class="node-chip node-chip--ghost">
            <strong>暂无家属</strong>
            <small>待建立关系</small>
          </div>
        </div>

        <div class="lane-column lane-elder">
          <span class="lane-label">老人</span>
          <div class="node-core" :data-risk="lane.elder.risk_level ?? 'low'">
            <strong>{{ lane.elder.label }}</strong>
            <small>{{ lane.elder.subtitle }}</small>
            <em>{{ lane.elder.status }}</em>
          </div>
        </div>

        <div class="lane-column lane-devices">
          <span class="lane-label">设备</span>
          <button
            v-for="device in lane.devices"
            :key="device.id"
            type="button"
            class="node-chip node-chip--device"
            :class="{ 'node-chip--selected': isSelectedDevice(device.id) }"
            :data-risk="device.risk_level ?? 'low'"
            @click="emit('select-device', device.id)"
          >
            <strong>{{ device.label }}</strong>
            <small>{{ device.subtitle }}</small>
            <em>{{ device.status }}</em>
          </button>
          <div v-if="!lane.devices.length" class="node-chip node-chip--ghost">
            <strong>暂无设备</strong>
            <small>待绑定手环</small>
          </div>
        </div>
      </article>
    </div>

    <div v-if="unassignedDevices.length" class="orphan-strip">
      <span class="lane-label">未归属设备</span>
      <div class="orphan-row">
        <button
          v-for="device in unassignedDevices"
          :key="device.id"
          type="button"
          class="node-chip node-chip--device"
          :class="{ 'node-chip--selected': isSelectedDevice(device.id) }"
          @click="emit('select-device', device.id)"
        >
          <strong>{{ device.label }}</strong>
          <small>{{ device.subtitle }}</small>
          <em>{{ device.status }}</em>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.topology-panel {
  display: grid;
  gap: 18px;
  background:
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.10), transparent 30%),
    linear-gradient(180deg, rgba(15, 22, 40, 0.98), rgba(11, 18, 32, 0.96));
}

.topology-head,
.lane-list,
.orphan-row {
  display: grid;
  gap: 16px;
}

.topology-head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.topology-head h2 {
  margin: 0;
  font-family: var(--font-display);
  color: var(--text-main);
}

.topology-subtitle {
  margin: 8px 0 0;
  color: var(--text-sub);
  line-height: 1.7;
}

.topology-community {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  min-width: 220px;
  border-radius: 24px;
  background: rgba(11, 42, 53, 0.94);
  color: #f4fbfa;
}

.topology-community span,
.lane-label {
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-sub);
}

.topology-community span {
  color: rgba(244, 251, 250, 0.62);
}

.topology-community strong {
  font-size: 1.1rem;
}

.lane-list {
  gap: 20px;
}

.topology-lane {
  display: grid;
  grid-template-columns: minmax(180px, 0.9fr) minmax(220px, 0.8fr) minmax(220px, 1.2fr);
  gap: 22px;
  align-items: center;
  padding: 20px;
  border-radius: 28px;
  background: rgba(13, 22, 38, 0.88);
  border: 1px solid rgba(56, 189, 248, 0.10);
  position: relative;
}

.topology-lane::before,
.topology-lane::after {
  content: "";
  position: absolute;
  top: 50%;
  height: 1px;
  background: linear-gradient(90deg, rgba(17, 138, 178, 0.24), rgba(17, 138, 178, 0.08));
}

.topology-lane::before {
  left: 30%;
  width: 10%;
}

.topology-lane::after {
  right: 30%;
  width: 10%;
}

.lane-column {
  display: grid;
  gap: 10px;
}

.lane-families,
.lane-devices {
  align-content: start;
}

.lane-elder {
  justify-items: center;
}

.node-core,
.node-chip {
  border-radius: 22px;
  border: 1px solid rgba(56, 189, 248, 0.12);
  background: rgba(16, 24, 44, 0.92);
  padding: 14px 16px;
  display: grid;
  gap: 4px;
  text-align: left;
}

.node-core {
  min-width: 220px;
  justify-items: center;
  text-align: center;
  background: rgba(34, 211, 238, 0.10);
}

.node-core[data-risk="high"] {
  background: rgba(248, 113, 113, 0.12);
}

.node-core[data-risk="medium"] {
  background: rgba(251, 146, 60, 0.14);
}

.node-chip {
  cursor: default;
}

.node-chip--device {
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.node-chip--device:hover,
.node-chip--selected {
  transform: translateY(-1px);
  border-color: rgba(17, 138, 178, 0.28);
  box-shadow: 0 12px 24px rgba(11, 42, 53, 0.08);
}

.node-chip strong,
.node-core strong {
  color: var(--text-main);
  font-size: 0.98rem;
}

.node-chip small,
.node-core small,
.node-chip em,
.node-core em {
  color: var(--text-sub);
  font-style: normal;
  font-size: 0.82rem;
}

.node-chip--ghost {
  background: rgba(255, 255, 255, 0.04);
}

.orphan-strip {
  display: grid;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(56, 189, 248, 0.10);
}

.orphan-row {
  display: flex;
  flex-wrap: wrap;
}

.topology-empty {
  padding: 20px;
  border-radius: 24px;
  background: rgba(13, 22, 38, 0.82);
  color: var(--text-sub);
}

@media (max-width: 1100px) {
  .topology-head,
  .topology-lane {
    grid-template-columns: 1fr;
  }

  .topology-lane::before,
  .topology-lane::after {
    display: none;
  }

  .lane-elder {
    justify-items: stretch;
  }

  .node-core {
    min-width: 0;
  }
}
</style>
