import { computed, onMounted, onUnmounted, ref, watch, type Ref } from "vue";
import { api, type HealthSample } from "../api/client";

export function useDeviceTrend(options: {
  selectedDeviceMac: Ref<string>;
  latest: Ref<Record<string, HealthSample>>;
  pollIntervalMs?: number;
  enableSocket?: boolean;
}) {
  const trendWindowMinutes = ref(180);
  const trendStore = ref<Record<string, HealthSample[]>>({});
  const focusLatest = computed(() =>
    options.selectedDeviceMac.value ? options.latest.value[options.selectedDeviceMac.value] ?? null : null,
  );
  const focusTrend = computed(() => trendStore.value[options.selectedDeviceMac.value] ?? []);

  let refreshTimer: number | null = null;
  let healthSocket: WebSocket | null = null;

  async function refreshTrend(mac = options.selectedDeviceMac.value, minutes = trendWindowMinutes.value) {
    if (!mac) return;
    const trend = await api.getTrend(mac, minutes, 120).catch(() => []);
    trendStore.value = { ...trendStore.value, [mac]: trend };
  }

  function stopRuntime() {
    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer);
      refreshTimer = null;
    }
    healthSocket?.close();
    healthSocket = null;
  }

  function connectHealthSocket(mac: string) {
    healthSocket?.close();
    healthSocket = null;

    if (!mac || options.enableSocket === false) return;

    healthSocket = api.healthSocket(mac);
    healthSocket.onmessage = (event) => {
      try {
        const sample = JSON.parse(event.data) as HealthSample;
        options.latest.value = { ...options.latest.value, [sample.device_mac]: sample };
        const previous = trendStore.value[sample.device_mac] ?? [];
        const merged = [...previous, sample]
          .sort((left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime())
          .filter((item, index, array) => {
            if (index === 0) return true;
            return item.timestamp !== array[index - 1].timestamp;
          });
        trendStore.value = { ...trendStore.value, [sample.device_mac]: merged.slice(-240) };
      } catch {
        // Keep page state stable if socket data is malformed.
      }
    };
  }

  function startRuntime() {
    stopRuntime();
    if (!options.selectedDeviceMac.value) return;

    void refreshTrend();
    connectHealthSocket(options.selectedDeviceMac.value);

    const pollIntervalMs = options.pollIntervalMs ?? 15000;
    refreshTimer = window.setInterval(() => {
      void refreshTrend();
    }, pollIntervalMs);
  }

  watch([options.selectedDeviceMac, trendWindowMinutes], () => {
    startRuntime();
  });

  onMounted(() => {
    startRuntime();
  });

  onUnmounted(() => {
    stopRuntime();
  });

  return {
    focusLatest,
    focusTrend,
    refreshTrend,
    stopRuntime,
    trendStore,
    trendWindowMinutes,
  };
}
