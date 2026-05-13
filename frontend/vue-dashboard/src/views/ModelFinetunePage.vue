<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
  Video,
} from "lucide-vue-next";
import { API_BASE } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";

const props = defineProps<{
  refreshKey?: number;
}>();

type StatusPayload = Record<string, unknown>;

const defaultTuningUrl = "http://127.0.0.1:7860";
const rawTuningUrl =
  (import.meta.env.VITE_MODEL_TUNING_URL ?? defaultTuningUrl).trim();
const tuningUrl = rawTuningUrl.replace(/\/$/, "") || defaultTuningUrl;

const iframeVersion = ref(0);
const loading = ref(false);
const error = ref("");
const workbenchLoading = ref(true);
const workbenchReachable = ref(false);
const workbenchError = ref("");
const workbenchCheckedAt = ref<number | null>(null);
const detectionStatus = ref<StatusPayload | null>(null);
const cameraHealth = ref<StatusPayload | null>(null);
const targetStatus = ref<StatusPayload | null>(null);

let workbenchProbeController: AbortController | null = null;

const iframeSrc = computed(
  () => `${tuningUrl}/?embedded=health-console&v=${iframeVersion.value}`,
);
const displayUrl = computed(() => tuningUrl.replace(/^https?:\/\//, ""));
const workbenchLastCheckedLabel = computed(() => {
  if (!workbenchCheckedAt.value) return "未检测";
  return new Date(workbenchCheckedAt.value).toLocaleTimeString("zh-CN", {
    hour12: false,
  });
});
const asPayload = (value: unknown): StatusPayload =>
  value && typeof value === "object" ? (value as StatusPayload) : {};

const fall = computed(() => asPayload(detectionStatus.value?.fall_detection));
const pose = computed(() => asPayload(detectionStatus.value?.pose_detection));
const frameWorker = computed(() =>
  asPayload(detectionStatus.value?.frame_analysis),
);
const faceModel = computed(() => asPayload(targetStatus.value?.face_model));

const statusCards = computed(() => [
  {
    label: "跌倒检测模型",
    value: fall.value.model_root_exists ? "模型目录已就绪" : "模型目录缺失",
    detail: fall.value.enabled ? "实时检测已启用" : "实时检测未启用",
    ok: Boolean(fall.value.model_root_exists),
    icon: ShieldCheck,
  },
  {
    label: "姿态检测模型",
    value: pose.value.model_root_exists ? "模型目录已就绪" : "模型目录缺失",
    detail: pose.value.enabled ? "姿态检测已启用" : "姿态检测未启用",
    ok: Boolean(pose.value.model_root_exists),
    icon: Activity,
  },
  {
    label: "摄像头桥接",
    value: cameraHealth.value?.has_frame ? "已有实时画面" : "暂无可用画面",
    detail: String(
      cameraHealth.value?.last_error ??
        cameraHealth.value?.bridge_status ??
        "等待检测",
    ),
    ok: Boolean(cameraHealth.value?.has_frame),
    icon: Video,
  },
  {
    label: "目标人物模型",
    value: faceModel.value.sface_available ? "人脸模型可用" : "人脸模型未就绪",
    detail: `目标用户 ${targetStatus.value?.user_count ?? 0} 人`,
    ok: Boolean(faceModel.value.sface_available),
    icon: CheckCircle2,
  },
  {
    label: "单帧分析进程",
    value: frameWorker.value.enabled ? "接口已启用" : "接口未启用",
    detail: frameWorker.value.running
      ? "后台进程运行中"
      : "按需启动或空闲",
    ok: Boolean(frameWorker.value.enabled),
    icon: FlaskConical,
  },
  {
    label: "嵌入工作台",
    value: workbenchReachable.value ? "工作台可访问" : "工作台未就绪",
    detail: workbenchReachable.value
      ? `最近检测 ${workbenchLastCheckedLabel.value}`
      : workbenchError.value || "当前无法连接本地 7860 服务",
    ok: workbenchReachable.value,
    icon: ExternalLink,
  },
]);

async function fetchJson(path: string) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`${path} ${response.status}`);
  }
  return response.json();
}

async function refreshStatus() {
  loading.value = true;
  error.value = "";
  try {
    const [models, camera, target] = await Promise.all([
      fetchJson("/camera/detection-models/status"),
      fetchJson("/target-users/external-camera/health"),
      fetchJson("/target-users/status"),
    ]);
    detectionStatus.value = models;
    cameraHealth.value = camera;
    targetStatus.value = target;
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    loading.value = false;
  }
}

function refreshWorkbench() {
  iframeVersion.value += 1;
  void probeWorkbench();
}

function openWorkbench() {
  window.open(tuningUrl, "_blank", "noopener,noreferrer");
}

async function probeWorkbench() {
  workbenchProbeController?.abort();
  const controller = new AbortController();
  workbenchProbeController = controller;
  workbenchLoading.value = true;
  workbenchError.value = "";
  try {
    await fetch(`${tuningUrl}/`, {
      method: "GET",
      mode: "no-cors",
      signal: controller.signal,
    });
    workbenchReachable.value = true;
  } catch (exc) {
    if ((exc as Error)?.name === "AbortError") return;
    workbenchReachable.value = false;
    workbenchError.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    if (workbenchProbeController === controller) {
      workbenchLoading.value = false;
      workbenchCheckedAt.value = Date.now();
      workbenchProbeController = null;
    }
  }
}

function handleWorkbenchLoaded() {
  workbenchReachable.value = true;
  workbenchLoading.value = false;
  workbenchError.value = "";
  workbenchCheckedAt.value = Date.now();
}

function handleWorkbenchErrored() {
  workbenchReachable.value = false;
  workbenchLoading.value = false;
  workbenchError.value = "本地模型微调服务当前不可用或未启动。";
  workbenchCheckedAt.value = Date.now();
}

watch(
  () => props.refreshKey,
  (key, previous) => {
    if (key == null || previous == null) return;
    void refreshStatus();
    refreshWorkbench();
  },
);

onMounted(() => {
  void refreshStatus();
  void probeWorkbench();
});

onUnmounted(() => {
  workbenchProbeController?.abort();
});
</script>

<template>
  <section class="model-page">
    <PageHeader
      eyebrow="Model Operations"
      title="模型训练与跌倒检测展示"
      description="统一查看跌倒检测、姿态识别、目标人物和摄像头桥接状态，并进入本地模型微调工作台。"
      :meta="['社区与管理员可用', '本地服务嵌入', '展示脚本独立运行']"
    >
      <template #actions>
        <button
          type="button"
          class="model-btn model-btn--ghost"
          :disabled="loading"
          @click="refreshStatus"
        >
          <RefreshCw :size="16" />
          刷新状态
        </button>
        <button
          type="button"
          class="model-btn model-btn--primary"
          @click="openWorkbench"
        >
          <ExternalLink :size="16" />
          打开工作台
        </button>
      </template>
    </PageHeader>

    <div v-if="error" class="model-alert">
      <AlertTriangle :size="18" />
      <span>{{ error }}</span>
    </div>

    <section class="model-status-grid" aria-label="模型状态">
      <article
        v-for="card in statusCards"
        :key="card.label"
        class="model-status-card"
      >
        <div
          class="model-status-card__icon"
          :class="{ 'model-status-card__icon--ok': card.ok }"
        >
          <component :is="card.icon" :size="20" />
        </div>
        <div class="model-status-card__copy">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="model-command-panel" aria-label="展示命令">
      <div>
        <span class="model-command-panel__eyebrow">Showcase</span>
        <h2>跌倒检测展示脚本</h2>
      </div>
      <pre><code>conda run -n helth python scripts/showcase_fall_detection_module.py --max-frames 160</code></pre>
      <pre><code>conda run -n helth python scripts/run_fall_media_demo.py tmp_detect_frame.jpg --json data/fall_showcase/demo-summary.json</code></pre>
    </section>

    <section class="model-workbench" aria-label="模型微调工作台">
      <div class="model-workbench__bar">
        <div>
          <p class="model-workbench__eyebrow">Embedded Console</p>
          <h2>本地模型微调工作台</h2>
          <p class="model-workbench__subtle">
            这里优先嵌入本地 7860 端口上的训练/微调控制台；如果服务没启动，页面会自动显示降级说明和重试入口，不再只剩一个空白拒绝连接框。
          </p>
        </div>
        <div class="model-workbench__guard">
          <ShieldCheck :size="15" />
          <span>服务地址 {{ displayUrl }}</span>
        </div>
      </div>

      <div class="model-workbench__frame">
        <div v-if="!workbenchReachable" class="model-workbench__fallback">
          <div class="model-workbench__fallback-icon">
            <ExternalLink :size="22" />
          </div>
          <strong>{{
            workbenchLoading ? "正在检测本地工作台..." : "本地模型微调工作台未启动"
          }}</strong>
          <p>
            {{
              workbenchLoading
                ? "页面正在尝试连接 127.0.0.1:7860。"
                : "当前没有检测到可嵌入的本地微调服务。你可以先启动对应控制台，或者先使用上方状态卡片和展示命令完成模型检查。"
            }}
          </p>
          <div class="model-workbench__fallback-actions">
            <button
              type="button"
              class="model-btn model-btn--ghost"
              @click="probeWorkbench"
            >
              <RefreshCw :size="16" />
              重新检测
            </button>
            <button
              type="button"
              class="model-btn model-btn--primary"
              @click="openWorkbench"
            >
              <ExternalLink :size="16" />
              新窗口尝试打开
            </button>
          </div>
          <div class="model-workbench__fallback-meta">
            <span>最近检测 {{ workbenchLastCheckedLabel }}</span>
            <span v-if="workbenchError">{{ workbenchError }}</span>
          </div>
        </div>
        <iframe
          v-else
          :key="iframeVersion"
          :src="iframeSrc"
          title="模型微调工作台"
          loading="eager"
          referrerpolicy="no-referrer"
          @load="handleWorkbenchLoaded"
          @error="handleWorkbenchErrored"
        />
      </div>
    </section>
  </section>
</template>

<style scoped>
.model-page {
  display: grid;
  gap: 20px;
  align-content: start;
  padding-bottom: 14px;
  max-width: 100%;
  overflow-x: hidden;
}

.model-btn {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid transparent;
}

.model-btn--ghost {
  background: #ffffff;
  color: #0f172a;
  border-color: #cbd5e1;
}

.model-btn--primary {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}

.model-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
  font-size: 0.9rem;
}

.model-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.model-status-card {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
  min-height: 116px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.model-status-card__icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
}

.model-status-card__icon--ok {
  background: #dcfce7;
  color: #15803d;
}

.model-status-card__copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.model-status-card__copy span {
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 700;
}

.model-status-card__copy strong {
  color: #0f172a;
  font-size: 1rem;
}

.model-status-card__copy small {
  color: #64748b;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.model-command-panel,
.model-workbench {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 18px;
}

.model-command-panel {
  display: grid;
  gap: 12px;
}

.model-command-panel__eyebrow,
.model-workbench__eyebrow {
  margin: 0 0 4px 0;
  color: #2563eb;
  font-size: 0.75rem;
  font-weight: 800;
  text-transform: uppercase;
}

.model-command-panel h2,
.model-workbench h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.1rem;
}

.model-workbench__subtle {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 0.9rem;
  line-height: 1.55;
  max-width: 72ch;
}

.model-command-panel pre {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  overflow-x: auto;
}

.model-workbench {
  display: grid;
  gap: 16px;
}

.model-workbench__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.model-workbench__guard {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  font-size: 0.82rem;
}

.model-workbench__frame {
  height: min(68vh, 760px);
  min-height: 520px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}

.model-workbench__frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
}

.model-workbench__fallback {
  height: 100%;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 14px;
  padding: 28px;
  text-align: center;
  background:
    radial-gradient(circle at top, rgba(37, 99, 235, 0.08), transparent 36%),
    linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
}

.model-workbench__fallback-icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: #1d4ed8;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(37, 99, 235, 0.14);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.1);
}

.model-workbench__fallback strong {
  color: #0f172a;
  font-size: 1.12rem;
}

.model-workbench__fallback p {
  margin: 0;
  color: #475569;
  max-width: 62ch;
  line-height: 1.65;
}

.model-workbench__fallback-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.model-workbench__fallback-meta {
  display: grid;
  gap: 6px;
  color: #64748b;
  font-size: 0.82rem;
}

@media (max-width: 1180px) {
  .model-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .model-status-grid {
    grid-template-columns: 1fr;
  }

  .model-workbench__bar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
