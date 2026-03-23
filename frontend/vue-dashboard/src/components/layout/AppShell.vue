<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api, type AlarmRecord, type SessionUser } from "../../api/client";
import type { PageKey } from "../../composables/useHashRouting";
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
const showControlRow = computed(() => props.allowedPages.length > 0 || props.canAccessDebug);

let refreshTimer: number | null = null;

function stopAlarmPolling() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

async function refreshAlarmCount() {
  const alarms = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  activeAlarmCount.value = alarms.filter((alarm) => !alarm.acknowledged).length;
}

function startAlarmPolling() {
  stopAlarmPolling();
  void refreshAlarmCount();
  refreshTimer = window.setInterval(() => {
    void refreshAlarmCount();
  }, 15000);
}

watch(() => props.sessionUser.id, () => {
  startAlarmPolling();
});

onMounted(() => {
  startAlarmPolling();
});

onUnmounted(() => {
  stopAlarmPolling();
});
</script>

<template>
  <main class="app-shell app-shell--layout">
    <GlobalHeader
      :session-user="sessionUser"
      :active-alarm-count="activeAlarmCount"
      @logout="emit('logout')"
    />

    <div v-if="showControlRow" class="app-shell__controls">
      <PrimaryNav
        v-if="allowedPages.length"
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
  </main>
</template>
