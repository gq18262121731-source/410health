<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import type {
  CameraPoseDetectionConfigResponse,
  CameraPoseDetectionLatestResponse,
  CameraPoseDetectionStatusResponse,
} from "../api/client";

const props = defineProps<{
  loading: boolean;
  savePending: boolean;
  saveMessage: string;
  poseStatus: CameraPoseDetectionStatusResponse | null;
  poseLatest: CameraPoseDetectionLatestResponse | null;
  poseConfig: CameraPoseDetectionConfigResponse | null;
  rawStreamUrl: string;
  detectionStreamUrl: string;
  poseStreamUrl: string;
}>();

const emit = defineEmits<{
  saveConfig: [payload: {
    pose_detection_enabled: boolean;
    pose_detection_profile: string;
    pose_detection_process_every_override: number;
    pose_detection_pose_conf_threshold: number;
    pose_detection_analysis_width: number;
    pose_detection_floor_roi_rect: string;
  }];
  reload: [];
}>();

const form = reactive({
  pose_detection_enabled: false,
  pose_detection_profile: "default",
  pose_detection_process_every_override: 0,
  pose_detection_pose_conf_threshold: 0.25,
  pose_detection_analysis_width: 960,
  pose_detection_floor_roi_rect: "",
});

watch(
  () => props.poseConfig,
  (config) => {
    if (!config) return;
    form.pose_detection_enabled = config.enabled;
    form.pose_detection_profile = config.profile;
    form.pose_detection_process_every_override = config.process_every_override;
    form.pose_detection_pose_conf_threshold = config.pose_conf_threshold;
    form.pose_detection_analysis_width = config.analysis_width;
    form.pose_detection_floor_roi_rect = config.floor_roi_rect;
  },
  { immediate: true },
);

const trackCount = computed(() => props.poseLatest?.tracks?.length ?? 0);
const topTrack = computed(() => props.poseLatest?.tracks?.[0] ?? null);

function save() {
  emit("saveConfig", {
    pose_detection_enabled: form.pose_detection_enabled,
    pose_detection_profile: form.pose_detection_profile.trim() || "default",
    pose_detection_process_every_override: Math.max(0, Number(form.pose_detection_process_every_override) || 0),
    pose_detection_pose_conf_threshold: Math.max(0, Math.min(1, Number(form.pose_detection_pose_conf_threshold) || 0)),
    pose_detection_analysis_width: Math.max(0, Number(form.pose_detection_analysis_width) || 0),
    pose_detection_floor_roi_rect: form.pose_detection_floor_roi_rect.trim(),
  });
}
</script>

<template>
  <section class="pose-debug-stack">
    <article class="panel pose-debug-overview">
      <div class="pose-debug-overview__head">
        <div>
          <p class="section-eyebrow">Pose Demo</p>
          <h2>火柴人骨架演示台</h2>
          <p class="subtle-copy">
            当前演示目标聚焦人体检测、关键点提取和骨架绘制，辅以轻量状态和调试指标。
          </p>
        </div>
        <div class="dashboard-chip-row">
          <span class="meta-pill">Tracks {{ trackCount }}</span>
          <span class="meta-pill">Backend {{ poseLatest?.backend ?? "-" }}</span>
          <span class="meta-pill">Profile {{ poseStatus?.profile ?? poseConfig?.profile ?? "-" }}</span>
        </div>
      </div>

      <div class="pose-stream-grid">
        <figure class="pose-stream-card">
          <figcaption>原始画面</figcaption>
          <img :src="rawStreamUrl" alt="原始视频流" loading="lazy" />
        </figure>
        <figure class="pose-stream-card">
          <figcaption>跌倒叠加流</figcaption>
          <img :src="detectionStreamUrl" alt="跌倒检测视频流" loading="lazy" />
        </figure>
        <figure class="pose-stream-card">
          <figcaption>骨架演示流</figcaption>
          <img :src="poseStreamUrl" alt="姿态检测视频流" loading="lazy" />
        </figure>
      </div>
    </article>

    <section class="panel-grid relation-grid pose-debug-grid">
      <article class="panel pose-config-panel">
        <h2>地面区域与运行参数</h2>
        <p class="helper-copy">Floor ROI 使用 `x1,y1,x2,y2` 格式，支持像素坐标或 `0-1` 归一化坐标。</p>

        <div class="form-grid">
          <label class="form-field checkbox-field relation-span-2">
            <input v-model="form.pose_detection_enabled" type="checkbox" />
            <span>启用姿态检测</span>
          </label>

          <label class="form-field">
            <span>Profile</span>
            <input v-model="form.pose_detection_profile" class="text-input" placeholder="default" />
          </label>

          <label class="form-field">
            <span>Process Every</span>
            <input v-model="form.pose_detection_process_every_override" class="text-input" type="number" min="0" step="1" />
          </label>

          <label class="form-field">
            <span>Pose Conf Threshold</span>
            <input v-model="form.pose_detection_pose_conf_threshold" class="text-input" type="number" min="0" max="1" step="0.01" />
          </label>

          <label class="form-field">
            <span>Analysis Width</span>
            <input v-model="form.pose_detection_analysis_width" class="text-input" type="number" min="0" step="32" />
          </label>

          <label class="form-field relation-span-2">
            <span>Floor ROI</span>
            <input
              v-model="form.pose_detection_floor_roi_rect"
              class="text-input"
              placeholder="0.00,0.55,1.00,1.00 或 0,700,1920,1080"
            />
          </label>
        </div>

        <div class="pose-config-actions">
          <button type="button" class="ghost-btn" :disabled="savePending" @click="save">
            {{ savePending ? "保存中..." : "保存并重启姿态服务" }}
          </button>
          <button type="button" class="ghost-btn" @click="emit('reload')">刷新状态</button>
        </div>

        <p v-if="saveMessage" class="status-banner" :class="saveMessage.includes('失败') ? 'status-error' : 'status-success'">
          {{ saveMessage }}
        </p>
      </article>

      <article class="panel pose-status-panel">
        <h2>运行状态</h2>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr><th>Enabled</th><td>{{ poseStatus?.enabled ? "true" : "false" }}</td></tr>
              <tr><th>Running</th><td>{{ poseStatus?.running ? "true" : "false" }}</td></tr>
              <tr><th>Process Running</th><td>{{ poseStatus?.process_running ? "true" : "false" }}</td></tr>
              <tr><th>PID</th><td>{{ poseStatus?.pid ?? "-" }}</td></tr>
              <tr><th>Source</th><td>{{ poseStatus?.source_url ?? "-" }}</td></tr>
              <tr><th>Conf</th><td>{{ poseStatus?.pose_conf_threshold ?? "-" }}</td></tr>
              <tr><th>Analysis Width</th><td>{{ poseStatus?.analysis_width ?? "-" }}</td></tr>
              <tr><th>Last Error</th><td>{{ poseStatus?.last_error ?? "-" }}</td></tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel pose-latest-panel">
        <h2>轻量状态</h2>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr><th>Frame Index</th><td>{{ poseLatest?.frame_idx ?? "-" }}</td></tr>
              <tr><th>Timestamp</th><td>{{ poseLatest?.timestamp_s ?? "-" }}</td></tr>
              <tr><th>Track Count</th><td>{{ trackCount }}</td></tr>
              <tr><th>Top Track</th><td>{{ topTrack?.track_id ?? "-" }}</td></tr>
              <tr><th>Top State</th><td>{{ topTrack?.state_label ?? "-" }}</td></tr>
              <tr><th>Top Score</th><td>{{ topTrack?.state_score ?? "-" }}</td></tr>
              <tr><th>Observed At</th><td>{{ poseLatest?._observed_at ?? "-" }}</td></tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel pose-track-panel">
        <h2>扩展调试信息</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Track ID</th>
                <th>State</th>
                <th>State Score</th>
                <th>Pose Score</th>
                <th>Features</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="track in poseLatest?.tracks ?? []" :key="track.track_id">
                <td>{{ track.track_id }}</td>
                <td>{{ track.state_label }}</td>
                <td>{{ track.state_score }}</td>
                <td>{{ track.pose_score }}</td>
                <td>{{ track.features ? JSON.stringify(track.features) : "-" }}</td>
              </tr>
              <tr v-if="!(poseLatest?.tracks?.length)">
                <td colspan="5">{{ loading ? "正在加载姿态结果..." : "当前没有姿态轨迹。" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>
