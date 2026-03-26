<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api, type AlarmRecord, type SessionUser } from "../../api/client";
import { focusCommunityWorkspaceDevice } from "../../composables/useCommunityWorkspace";
import type { PageKey } from "../../composables/useHashRouting";
import CommunitySosOverlay from "./CommunitySosOverlay.vue";
import GlobalHeader from "./GlobalHeader.vue";
import PrimaryNav from "./PrimaryNav.vue";
import ToolEntryMenu from "./ToolEntryMenu.vue";

const props = defineProps<{
  sessionUser: SessionUser;
  activePage: PageKey;
  allowedPages: PageKey[];
  canAccessDebug: boolean;
}>();

const emit = defineEmits<{
  logout: [];
  navigate: [page: PageKey];
}>();

const activeAlarmCount = ref(0);
const activeRealtimeAlarms = ref<AlarmRecord[]>([]);
const acknowledgingSos = ref(false);
const isCommunityWorkspace = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);
const activeSosAlarms = computed(() =>
  activeRealtimeAlarms.value
    .filter((alarm) => !alarm.acknowledged && isRealSosAlarm(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()),
);
const primarySosAlarm = computed(() => activeSosAlarms.value[0] ?? null);
const additionalSosCount = computed(() => Math.max(0, activeSosAlarms.value.length - 1));

let refreshTimer: number | null = null;
let alarmChannel: WebSocket | null = null;
let lastPresentedSosAlarmId = "";

function isRealSosAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "sos" && !alarm.acknowledged && Boolean(alarm.metadata?.is_real_device);
}

function syncAlarmState(alarms: AlarmRecord[]) {
  activeRealtimeAlarms.value = alarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  activeAlarmCount.value = activeRealtimeAlarms.value.length;
  presentPrimarySos();
}

function upsertAlarm(alarm: AlarmRecord) {
  const next = [...activeRealtimeAlarms.value];
  const index = next.findIndex((item) => item.id === alarm.id);
  if (alarm.acknowledged) {
    if (index >= 0) next.splice(index, 1);
  } else if (index >= 0) {
    next.splice(index, 1, alarm);
  } else {
    next.push(alarm);
  }
  syncAlarmState(next);
}

function presentPrimarySos() {
  if (!isCommunityWorkspace.value || !primarySosAlarm.value) return;
  if (lastPresentedSosAlarmId === primarySosAlarm.value.id && props.activePage === "overview") return;
  lastPresentedSosAlarmId = primarySosAlarm.value.id;
  focusCommunityWorkspaceDevice(primarySosAlarm.value.device_mac);
  emit("navigate", "overview");
}

function stopAlarmRuntime() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  alarmChannel?.close();
  alarmChannel = null;
}

async function refreshAlarmState() {
  const alarms = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  syncAlarmState(alarms);
}

function connectAlarmSocket() {
  alarmChannel?.close();
  alarmChannel = null;
  if (!isCommunityWorkspace.value) return;

  alarmChannel = api.alarmSocket();
  alarmChannel.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AlarmRecord | { type?: string; queue?: Array<{ alarm?: AlarmRecord }> };
      if ("type" in payload && payload.type === "alarm_queue") {
        const alarms = Array.isArray(payload.queue)
          ? payload.queue
              .map((item) => item.alarm)
              .filter((item): item is AlarmRecord => Boolean(item))
          : [];
        syncAlarmState(alarms);
        return;
      }
      upsertAlarm(payload as AlarmRecord);
    } catch {
      // ignore malformed websocket payloads
    }
  };
  alarmChannel.onclose = () => {
    alarmChannel = null;
  };
}

function startAlarmRuntime() {
  stopAlarmRuntime();
  void refreshAlarmState();
  connectAlarmSocket();
  refreshTimer = window.setInterval(() => {
    void refreshAlarmState();
  }, 15000);
}

watch(() => props.sessionUser.id, () => {
  startAlarmRuntime();
});

onMounted(() => {
  startAlarmRuntime();
});

onUnmounted(() => {
  stopAlarmRuntime();
});

async function acknowledgePrimarySos() {
  if (!primarySosAlarm.value) return;
  acknowledgingSos.value = true;
  try {
    await api.ackAlarm(primarySosAlarm.value.id);
    const remaining = activeRealtimeAlarms.value.filter((alarm) => alarm.id !== primarySosAlarm.value?.id);
    syncAlarmState(remaining);
    lastPresentedSosAlarmId = "";
  } finally {
    acknowledgingSos.value = false;
  }
}
</script>

<template>
  <main class="app-shell" :class="{ 'app-shell--workspace': isCommunityWorkspace }">
    <aside v-if="isCommunityWorkspace" class="workspace-sidebar">
      <div class="workspace-sidebar__brand">
        <p class="section-eyebrow">Community Workspace</p>
        <h2>社区工作台</h2>
        <p class="subtle-copy">监护、拓扑、成员设备与智能体分区协作。</p>
      </div>

      <PrimaryNav
        v-if="allowedPages.length"
        :active-page="activePage"
        :allowed-pages="allowedPages"
        @navigate="emit('navigate', $event)"
      />

      <div class="workspace-sidebar__footer">
        <ToolEntryMenu
          v-if="canAccessDebug"
          :active-page="activePage"
          :can-access-debug="canAccessDebug"
          @navigate="emit('navigate', $event)"
        />
      </div>
    </aside>

    <div class="workspace-stage">
      <GlobalHeader
        :session-user="sessionUser"
        :active-alarm-count="activeAlarmCount"
        @logout="emit('logout')"
      />

      <div
        v-if="!isCommunityWorkspace && allowedPages.length"
        class="app-shell__controls"
      >
        <PrimaryNav
          :active-page="activePage"
          :allowed-pages="allowedPages"
          @navigate="emit('navigate', $event)"
        />
        <ToolEntryMenu
          v-if="canAccessDebug"
          :active-page="activePage"
          :can-access-debug="canAccessDebug"
          @navigate="emit('navigate', $event)"
        />
      </div>

      <div class="app-shell__content">
        <slot />
      </div>
    </div>

    <CommunitySosOverlay
      v-if="isCommunityWorkspace"
      :alarm="primarySosAlarm"
      :additional-count="additionalSosCount"
      :acknowledging="acknowledgingSos"
      @acknowledge="acknowledgePrimarySos"
    />
  </main>
</template>
