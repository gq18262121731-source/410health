<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { AlertTriangle, CheckCircle2, RefreshCw, Video, WifiOff } from "lucide-vue-next";
import { api, type VideoBridgeAnalysisRecord, type VideoBridgeStatusResponse } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";

const status = ref<VideoBridgeStatusResponse | null>(null);
const loading = ref(false);
const error = ref("");

const latest = computed(() => status.value?.latest ?? null);
const cameras = computed(() => status.value?.cameras ?? []);
const pageMeta = computed(() => [
  `adapter ${status.value?.adapter_version ?? "video_adapter.v1"}`,
  `cameras ${status.value?.camera_count ?? 0}`,
  `state ${status.value?.bridge_state ?? "unknown"}`,
]);

const stateTone = computed(() => {
  const state = status.value?.bridge_state ?? "unknown";
  if (state === "running") return "good";
  if (state === "mock" || state === "unknown" || state === "stopped") return "idle";
  return "warn";
});

function formatTimestamp(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatNumber(value?: number | null, digits = 1) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

function targetLabel(record: VideoBridgeAnalysisRecord) {
  const target = record.target;
  if (!target) return "reserved";
  if (typeof target === "string") return target;
  const label = typeof target.label === "string" ? target.label : "";
  const id = typeof target.target_id === "string" ? target.target_id : "";
  return label || id || "reserved";
}

async function refreshStatus() {
  loading.value = true;
  error.value = "";
  try {
    status.value = await api.getVideoBridgeStatus();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "视频接入口状态读取失败";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void refreshStatus();
});
</script>

<template>
  <section class="page-stack video-bridge-page">
    <PageHeader
      eyebrow="Video Bridge / Reserved"
      title="视频接入口预埋"
      description="主系统侧预留独立视频分析服务推送入口。当前只展示状态占位与最近分析字段，不连接 RTSP，也不改动现有视频链路。"
      :meta="pageMeta"
    >
      <template #actions>
        <button type="button" class="ghost-btn" :disabled="loading" @click="refreshStatus">
          <RefreshCw :size="16" />
          刷新状态
        </button>
      </template>
    </PageHeader>

    <p v-if="error" class="feedback-banner feedback-error">{{ error }}</p>

    <section class="video-bridge-layout">
      <article class="panel video-bridge-hero">
        <div class="video-bridge-hero__copy">
          <p class="section-eyebrow">Main System Adapter</p>
          <h2>等待独立视频服务接入</h2>
          <p class="subtle-copy">
            这里保留 camera_id、帧龄、FPS、目标框、跌倒概率、风险等级和快照链接等主系统字段。真实服务接入后，只需要推送结构化分析结果。
          </p>
        </div>

        <div class="video-bridge-stage" aria-label="视频分析占位展示">
          <div class="video-bridge-stage__frame">
            <Video :size="42" />
            <span>Analysis Placeholder</span>
          </div>
          <div
            v-if="latest?.bbox"
            class="video-bridge-stage__bbox"
            :class="`video-bridge-stage__bbox--${latest.risk}`"
          >
            <span>{{ latest.track_id ?? "track pending" }}</span>
          </div>
        </div>
      </article>

      <article class="panel video-bridge-status">
        <div class="video-bridge-status__heading">
          <component
            :is="stateTone === 'good' ? CheckCircle2 : stateTone === 'warn' ? AlertTriangle : WifiOff"
            :size="20"
          />
          <div>
            <p class="section-eyebrow">Bridge State</p>
            <h2>{{ status?.bridge_state ?? "unknown" }}</h2>
          </div>
        </div>

        <div class="video-bridge-metrics">
          <span><strong>{{ formatNumber(latest?.frame_age_ms, 0) }}</strong><small>frame_age_ms</small></span>
          <span><strong>{{ formatNumber(latest?.video_fps) }}</strong><small>video_fps</small></span>
          <span><strong>{{ formatNumber(latest?.overlay_fps) }}</strong><small>overlay_fps</small></span>
          <span><strong>{{ formatNumber(latest?.ws_fps) }}</strong><small>ws_fps</small></span>
        </div>

        <dl class="video-bridge-fields">
          <div><dt>camera_id</dt><dd>{{ latest?.camera_id ?? "-" }}</dd></div>
          <div><dt>stream_name</dt><dd>{{ latest?.stream_name ?? "-" }}</dd></div>
          <div><dt>target</dt><dd>{{ latest ? targetLabel(latest) : "-" }}</dd></div>
          <div><dt>fall_state</dt><dd>{{ latest?.fall_state ?? "-" }}</dd></div>
          <div><dt>risk</dt><dd>{{ latest?.risk ?? "-" }}</dd></div>
          <div><dt>fall_prob</dt><dd>{{ formatNumber(latest?.fall_prob, 2) }}</dd></div>
          <div><dt>camera_lost</dt><dd>{{ latest?.camera_lost ? "true" : "false" }}</dd></div>
          <div><dt>capture_stale</dt><dd>{{ latest?.capture_stale ? "true" : "false" }}</dd></div>
          <div><dt>timestamp</dt><dd>{{ formatTimestamp(latest?.timestamp) }}</dd></div>
        </dl>
      </article>
    </section>

    <section class="panel video-bridge-table">
      <div class="video-bridge-table__header">
        <div>
          <p class="section-eyebrow">Reserved Cameras</p>
          <h2>最近视频分析推送</h2>
        </div>
        <span class="meta-pill">{{ cameras.length }} 路</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>camera_id</th>
              <th>stream</th>
              <th>state</th>
              <th>fps</th>
              <th>track</th>
              <th>risk</th>
              <th>fall_prob</th>
              <th>received_at</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in cameras" :key="`${item.camera_id}:${item.stream_name}`">
              <td><strong>{{ item.camera_id }}</strong></td>
              <td>{{ item.stream_name }}</td>
              <td>{{ item.service_state }}</td>
              <td>{{ formatNumber(item.video_fps) }} / {{ formatNumber(item.overlay_fps) }}</td>
              <td>{{ item.track_id ?? "-" }}</td>
              <td>{{ item.risk }}</td>
              <td>{{ formatNumber(item.fall_prob, 2) }}</td>
              <td>{{ formatTimestamp(item.received_at) }}</td>
            </tr>
            <tr v-if="!cameras.length">
              <td colspan="8">暂无视频分析推送，等待独立视频服务接入。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.video-bridge-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 18px;
  align-items: stretch;
}

.video-bridge-hero {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(320px, 1.15fr);
  gap: 22px;
  align-items: center;
}

.video-bridge-hero__copy h2,
.video-bridge-status h2,
.video-bridge-table h2 {
  margin: 0;
  color: var(--text-main);
}

.video-bridge-stage {
  position: relative;
  min-height: 320px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.06) 1px, transparent 1px),
    linear-gradient(0deg, rgba(15, 23, 42, 0.06) 1px, transparent 1px),
    linear-gradient(135deg, #eef6ff 0%, #f7fbf8 100%);
  background-size: 32px 32px, 32px 32px, auto;
  border: 1px solid var(--line-medium);
}

.video-bridge-stage__frame {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 10px;
  text-align: center;
  color: #2563eb;
  font-weight: 800;
}

.video-bridge-stage__bbox {
  position: absolute;
  left: 28%;
  top: 18%;
  width: 34%;
  height: 68%;
  border: 2px solid #2563eb;
  border-radius: 10px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}

.video-bridge-stage__bbox span {
  position: absolute;
  left: 8px;
  top: 8px;
  padding: 4px 8px;
  border-radius: 8px;
  background: #2563eb;
  color: #ffffff;
  font-size: 0.78rem;
  font-weight: 800;
}

.video-bridge-stage__bbox--high,
.video-bridge-stage__bbox--critical {
  border-color: var(--risk-high);
}

.video-bridge-stage__bbox--high span,
.video-bridge-stage__bbox--critical span {
  background: var(--risk-high);
}

.video-bridge-status {
  display: grid;
  gap: 18px;
}

.video-bridge-status__heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.video-bridge-status__heading > svg {
  color: #2563eb;
}

.video-bridge-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.video-bridge-metrics span {
  display: grid;
  gap: 4px;
  padding: 14px;
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  border: 1px solid var(--line);
}

.video-bridge-metrics strong {
  font-size: 1.35rem;
  color: var(--text-main);
}

.video-bridge-metrics small,
.video-bridge-fields dt {
  color: var(--text-sub);
  font-size: 0.78rem;
}

.video-bridge-fields {
  display: grid;
  gap: 10px;
  margin: 0;
}

.video-bridge-fields div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
}

.video-bridge-fields dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--text-main);
  font-weight: 700;
}

.video-bridge-table {
  display: grid;
  gap: 14px;
}

.video-bridge-table__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

@media (max-width: 1100px) {
  .video-bridge-layout,
  .video-bridge-hero {
    grid-template-columns: 1fr;
  }
}
</style>
