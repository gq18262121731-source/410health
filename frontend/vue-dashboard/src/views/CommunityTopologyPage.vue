<script setup lang="ts">
import { computed, toRef } from "vue";
import type { SessionUser } from "../api/client";
import CommunityDeviceInspector from "../components/CommunityDeviceInspector.vue";
import CommunityDeviceRail from "../components/CommunityDeviceRail.vue";
import CommunityRelationTopology from "../components/CommunityRelationTopology.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCommunityWorkspace } from "../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
}>();

const workspace = useCommunityWorkspace(toRef(props, "sessionUser"));

const pageMeta = computed(() => [
  `Lane ${workspace.relationTopology.value?.lanes.length ?? 0}`,
  `未归属设备 ${workspace.relationTopology.value?.unassigned_devices.length ?? 0}`,
  `当前设备 ${workspace.selectedDevice.value?.device_mac ?? "未选择"}`,
]);
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Topology"
      title="设备拓扑"
      description="单独查看社区、老人、家属和设备的归属关系，便于现场解释设备绑定和用户关系。"
      :meta="pageMeta"
    />

    <CommunityDeviceRail
      :devices="workspace.deviceStatuses.value"
      :selected-device-mac="workspace.selectedDeviceMac.value"
      @select="workspace.setSelectedDeviceMac"
    />

    <div class="topology-layout">
      <CommunityRelationTopology
        :topology="workspace.relationTopology.value ?? null"
        :selected-device-mac="workspace.selectedDeviceMac.value"
        @select-device="workspace.setSelectedDeviceMac"
      />
      <CommunityDeviceInspector :device="workspace.selectedDevice.value" />
    </div>
  </section>
</template>

<style scoped>
.topology-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.82fr);
  align-items: start;
}

@media (max-width: 1180px) {
  .topology-layout {
    grid-template-columns: 1fr;
  }
}
</style>
