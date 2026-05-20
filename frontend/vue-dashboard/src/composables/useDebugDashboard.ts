import { computed, onMounted, onUnmounted, ref } from "vue";
import {
  api,
  type CameraPoseDetectionConfigResponse,
  type CameraPoseDetectionLatestResponse,
  type CameraPoseDetectionStatusResponse,
  type DeviceRecord,
  type HealthSample,
} from "../api/client";
import { mergeHealthSample } from "../domain/healthSampleMerge";

export function useDebugDashboard(pollIntervalMs = 5000) {
  const devices = ref<DeviceRecord[]>([]);
  const latest = ref<Record<string, HealthSample>>({});
  const poseStatus = ref<CameraPoseDetectionStatusResponse | null>(null);
  const poseLatest = ref<CameraPoseDetectionLatestResponse | null>(null);
  const poseConfig = ref<CameraPoseDetectionConfigResponse | null>(null);
  const dashboardLoading = ref(false);
  const poseSavePending = ref(false);
  const poseSaveMessage = ref("");
  const dashboardLoadError = ref("");
  const lastSyncAt = ref<Date | null>(null);

  const debugRows = computed(() =>
    devices.value.map((device) => ({
      mac: device.mac_address,
      deviceName: device.device_name,
      status: device.status,
      sample: latest.value[device.mac_address] ?? null,
    })),
  );

  let refreshTimer: number | null = null;

  function stopPolling() {
    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  async function refreshDebugData() {
    dashboardLoading.value = true;
    dashboardLoadError.value = "";

    devices.value = await api.listDevices().catch(() => [] as DeviceRecord[]);
    const samples = await Promise.all(devices.value.map((device) => api.getRealtime(device.mac_address).catch(() => null)));
    const nextLatest = { ...latest.value };
    samples.forEach((sample) => {
      if (sample) {
        nextLatest[sample.device_mac] = mergeHealthSample(nextLatest[sample.device_mac], sample) ?? sample;
      }
    });
    latest.value = nextLatest;

    poseStatus.value = await api.getCameraPoseDetectionStatus().catch(() => null);
    poseLatest.value = await api.getCameraPoseDetectionLatest().catch(() => null);
    poseConfig.value = await api.getCameraPoseDetectionConfig().catch(() => poseConfig.value);

    lastSyncAt.value = new Date();
    dashboardLoading.value = false;
  }

  async function savePoseConfig(payload: {
    pose_detection_enabled: boolean;
    pose_detection_profile: string;
    pose_detection_process_every_override: number;
    pose_detection_pose_conf_threshold: number;
    pose_detection_analysis_width: number;
    pose_detection_floor_roi_rect: string;
  }) {
    poseSavePending.value = true;
    poseSaveMessage.value = "";
    try {
      const response = await api.updateCameraPoseDetectionConfig(payload);
      poseConfig.value = response.config;
      poseSaveMessage.value = response.restarted ? "姿态配置已保存，服务已自动重启。" : "姿态配置已保存。";
      await refreshDebugData();
    } catch (error) {
      poseSaveMessage.value = error instanceof Error ? `保存失败：${error.message}` : "保存失败：未知错误";
    } finally {
      poseSavePending.value = false;
    }
  }

  async function startPolling() {
    stopPolling();
    await refreshDebugData();
    refreshTimer = window.setInterval(() => {
      void refreshDebugData();
    }, pollIntervalMs);
  }

  onMounted(() => {
    void startPolling();
  });

  onUnmounted(() => {
    stopPolling();
  });

  return {
    dashboardLoadError,
    dashboardLoading,
    debugRows,
    devices,
    lastSyncAt,
    latest,
    poseConfig,
    poseLatest,
    poseSaveMessage,
    poseSavePending,
    poseStatus,
    refreshDebugData,
    savePoseConfig,
    stopPolling,
  };
}
