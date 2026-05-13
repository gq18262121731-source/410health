<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type {
  CameraFallDetectionStatusResponse,
  CameraPoseDetectionConfigResponse,
  ExternalCameraFallDetectResponse,
  ExternalCameraHealthResponse,
  SessionUser,
  TargetUserRecord,
} from "../api/client";
import { ApiError, api } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";

defineProps<{
  sessionUser: SessionUser;
}>();

const users = ref<TargetUserRecord[]>([]);
const usersLoading = ref(false);
const usersError = ref("");
const createBusy = ref(false);
const createMessage = ref("");
const createError = ref("");
const deleteBusyId = ref("");
const externalHealth = ref<ExternalCameraHealthResponse | null>(null);
const externalHealthError = ref("");
const analyzeBusy = ref(false);
const analyzeResult = ref<ExternalCameraFallDetectResponse | null>(null);
const analyzeSource = ref<"external" | "local">("external");
const fallStatus = ref<CameraFallDetectionStatusResponse | null>(null);
const poseConfig = ref<CameraPoseDetectionConfigResponse | null>(null);
const poseToggleBusy = ref(false);
const livePreviewError = ref("");
const livePreviewVersion = ref(0);
const livePreviewMode = ref<"stream" | "snapshot">("stream");
const trendItems = ref<
  Array<{
    ts: number;
    posture: string;
    event: string;
    confidence: number;
    postureRaw: typeof analyzeResult.value;
  }>
>([]);

const form = ref({
  displayName: "",
  group: "default",
  note: "",
  files: [] as File[],
});

const pageMeta = computed(() => [
  `已注册 ${users.value.length}`,
  `摄像头 ${
    analyzeSource.value === "local"
      ? "本地电脑摄像头"
      : externalHealth.value?.running
        ? "已接通"
        : "待连接"
  }`,
  `流 ${
    analyzeSource.value === "local"
      ? "local-camera"
      : externalHealth.value?.stream ?? "unknown"
  }`,
]);

const selectedFileSummary = computed(() => {
  if (!form.value.files.length) return "未选择照片";
  if (form.value.files.length === 1) return form.value.files[0].name;
  return `${form.value.files.length} 张照片已选择`;
});

const posePosture = computed(
  () => analyzeResult.value?.target_pose?.pose?.posture ?? null,
);
const postureEvent = computed(
  () => analyzeResult.value?.posture_event ?? null,
);
const postureGuidance = computed(
  () => analyzeResult.value?.posture_guidance ?? null,
);
const multimodalReview = computed(
  () => fallStatus.value?.multimodal_review ?? null,
);

const snapshotUrl = computed(() => {
  const localSnapshot =
    analyzeSource.value === "local" ? api.getLocalCameraSnapshotUrl() : "";
  const base =
    analyzeResult.value?.camera_source?.snapshot_url ||
    localSnapshot ||
    externalHealth.value?.snapshot_url;
  if (!base) return "";
  return `${base}${base.includes("?") ? "&" : "?"}t=${Date.now()}`;
});

const rawPreviewUrl = computed(() => {
  const base =
    analyzeSource.value === "local"
      ? api.getCameraStreamUrl()
      : api.getActiveCameraStreamUrl();
  return `${base}${base.includes("?") ? "&" : "?"}raw=${livePreviewVersion.value}`;
});

const processedPreviewUrl = computed(() => {
  const base = api.getCameraDetectionStreamUrl();
  return `${base}${base.includes("?") ? "&" : "?"}fall=${livePreviewVersion.value}`;
});

const skeletonPreviewUrl = computed(() => {
  const base = api.getCameraPoseStreamUrl();
  return `${base}${base.includes("?") ? "&" : "?"}pose=${livePreviewVersion.value}`;
});

const eventTone = computed(() => {
  const level = postureEvent.value?.level ?? postureGuidance.value?.level ?? "";
  if (level === "critical" || level === "danger") return "tone-critical";
  if (level === "warning") return "tone-warning";
  if (level === "attention") return "tone-info";
  return "tone-neutral";
});

const multimodalTone = computed(() => {
  if (!multimodalReview.value?.enabled) return "tone-neutral";
  if (
    multimodalReview.value?.dashscope_configured ||
    multimodalReview.value?.siliconflow_configured
  ) {
    return "tone-stable";
  }
  return "tone-warning";
});

function formatError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  form.value.files = Array.from(input.files ?? []);
}

function handleLivePreviewLoaded() {
  livePreviewError.value = "";
}

function handleLivePreviewError() {
  livePreviewMode.value = "snapshot";
  livePreviewError.value = "实时预览暂时不可用，页面已自动降级到快照模式。";
}

function retryLivePreview() {
  livePreviewMode.value = "stream";
  livePreviewVersion.value += 1;
  livePreviewError.value = "";
}

async function refreshFallStatus() {
  try {
    fallStatus.value = await api.getCameraFallDetectionStatus();
  } catch {
    fallStatus.value = null;
  }
}

async function refreshPoseConfig() {
  try {
    poseConfig.value = await api.getCameraPoseDetectionConfig();
  } catch {
    poseConfig.value = null;
  }
}

async function refreshUsers() {
  usersLoading.value = true;
  usersError.value = "";
  try {
    users.value = await api.listTargetUsers();
  } catch (error) {
    users.value = [];
    usersError.value = formatError(error, "目标用户列表加载失败。");
  } finally {
    usersLoading.value = false;
  }
}

async function refreshExternalHealth() {
  externalHealthError.value = "";
  try {
    externalHealth.value = await api.getExternalCameraHealth();
  } catch (error) {
    externalHealth.value = null;
    externalHealthError.value = formatError(error, "外部摄像头运行时未接通。");
  }
}

async function submitCreate() {
  createError.value = "";
  createMessage.value = "";
  const displayName = form.value.displayName.trim();
  if (!displayName) {
    createError.value = "请先填写目标用户姓名。";
    return;
  }
  if (!form.value.files.length) {
    createError.value = "请至少选择 1 张目标用户照片。";
    return;
  }

  createBusy.value = true;
  try {
    const created = await api.createTargetUser({
      display_name: displayName,
      group: form.value.group.trim() || "default",
      note: form.value.note.trim(),
      files: form.value.files,
    });
    form.value = {
      displayName: "",
      group: "default",
      note: "",
      files: [],
    };
    createMessage.value = created.warnings.length
      ? `创建完成，但有提示：${created.warnings.join("；")}`
      : "目标用户创建完成。";
    await refreshUsers();
  } catch (error) {
    createError.value = formatError(error, "目标用户创建失败。");
  } finally {
    createBusy.value = false;
  }
}

async function removeUser(userId: string) {
  deleteBusyId.value = userId;
  try {
    await api.deleteTargetUser(userId);
    await refreshUsers();
  } catch (error) {
    usersError.value = formatError(error, "目标用户删除失败。");
  } finally {
    deleteBusyId.value = "";
  }
}

async function runPoseAnalysis() {
  analyzeBusy.value = true;
  try {
    analyzeResult.value =
      analyzeSource.value === "local"
        ? await api.runLocalCameraPoseDetect({
            target_only: true,
            session_id: "target-pose-demo-page-local",
            mode: "metadata",
          })
        : await api.runExternalCameraFallDetect({
            target_only: true,
            session_id: "target-pose-demo-page",
            mode: "metadata",
          });
    trendItems.value = [
      ...trendItems.value.slice(-7),
      {
        ts: Date.now(),
        posture:
          analyzeResult.value?.target_pose?.pose?.posture?.label ?? "unknown",
        event: analyzeResult.value?.posture_event?.type ?? "normal",
        confidence: Number(
          analyzeResult.value?.posture_event?.confidence ??
            analyzeResult.value?.target_pose?.pose?.posture?.confidence ??
            0,
        ),
        postureRaw: analyzeResult.value,
      },
    ];
    livePreviewMode.value = "stream";
    livePreviewVersion.value += 1;
    livePreviewError.value = "";
    if (analyzeSource.value === "external") {
      await refreshExternalHealth();
    }
    await refreshFallStatus();
    await refreshPoseConfig();
  } catch (error) {
    externalHealthError.value = formatError(
      error,
      analyzeSource.value === "local"
        ? "本地摄像头姿态分析执行失败。"
        : "目标姿态分析执行失败。",
    );
  } finally {
    analyzeBusy.value = false;
  }
}

async function togglePoseDetection() {
  poseToggleBusy.value = true;
  try {
    const nextEnabled = !(poseConfig.value?.enabled === true);
    const result = await api.updateCameraPoseDetectionConfig({
      pose_detection_enabled: nextEnabled,
    });
    poseConfig.value = result.config;
  } catch (error) {
    externalHealthError.value = formatError(error, "姿态检测切换失败。");
  } finally {
    poseToggleBusy.value = false;
  }
}

onMounted(() => {
  void refreshUsers();
  void refreshExternalHealth();
  void refreshFallStatus();
  void refreshPoseConfig();
});
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Target Pose Demo"
      title="跌倒检测与骨架展示"
      description="基于社区摄像头统一展示原始视频、跌倒检测处理后画面与多点位姿态骨架流，作为现场演示与模型核验入口。"
      :meta="pageMeta"
    >
      <template #actions>
        <button type="button" class="ghost-btn" :disabled="analyzeBusy" @click="runPoseAnalysis">
          {{ analyzeBusy ? "分析中..." : analyzeSource === "local" ? "执行本地摄像头姿态分析" : "执行目标姿态分析" }}
        </button>
        <button type="button" class="ghost-btn" :disabled="poseToggleBusy" @click="togglePoseDetection">
          {{ poseToggleBusy ? "切换中..." : poseConfig?.enabled ? "关闭姿态检测" : "开启姿态检测" }}
        </button>
        <button type="button" class="ghost-btn" @click="analyzeSource = analyzeSource === 'local' ? 'external' : 'local'">
          {{ analyzeSource === "local" ? "切回外部摄像头" : "切到本地电脑摄像头" }}
        </button>
        <button type="button" class="ghost-btn" @click="refreshExternalHealth">刷新外部摄像头</button>
      </template>
    </PageHeader>

    <p v-if="externalHealthError" class="feedback-banner feedback-error">{{ externalHealthError }}</p>

    <section class="target-pose-grid">
      <article class="panel target-pose-hero">
        <div class="target-pose-hero__main">
          <div>
            <p class="section-eyebrow">Step 1</p>
            <h2>注册目标用户照片</h2>
            <p class="subtle-copy">
              先注册目标人物档案，后续摄像头姿态分析会基于该档案执行单目标识别与筛选。
            </p>
          </div>
          <div class="dashboard-chip-row">
            <span class="meta-pill">{{ analyzeSource === "local" ? "本地电脑摄像头模式" : `外部流 ${externalHealth?.stream ?? "unknown"}` }}</span>
            <span class="meta-pill">{{ analyzeSource === "local" ? "调用本地摄像头快照" : (externalHealth?.running ? "运行时在线" : "运行时未接通") }}</span>
            <span class="meta-pill">跌倒检测 {{ fallStatus?.process_running ? "常开运行中" : (fallStatus?.enabled ? "已启用" : "未启用") }}</span>
            <span class="meta-pill">姿态检测 {{ poseConfig?.enabled ? "已开启" : "已关闭" }}</span>
          </div>
        </div>

        <div class="target-user-form">
          <label class="form-field">
            <span>目标用户姓名</span>
            <input v-model="form.displayName" class="text-input" type="text" placeholder="例如：张奶奶" />
          </label>
          <label class="form-field">
            <span>分组</span>
            <input v-model="form.group" class="text-input" type="text" placeholder="default" />
          </label>
          <label class="form-field target-user-form__wide">
            <span>备注</span>
            <input v-model="form.note" class="text-input" type="text" placeholder="例如：演示区域主关注对象" />
          </label>
          <label class="form-field target-user-form__wide">
            <span>上传照片</span>
            <input class="text-input target-user-file" type="file" accept="image/*" multiple @change="onFileChange" />
            <small class="helper-copy">{{ selectedFileSummary }}</small>
          </label>
        </div>

        <div class="target-user-actions">
          <button type="button" class="primary-btn" :disabled="createBusy" @click="submitCreate">
            {{ createBusy ? "注册中..." : "创建目标用户" }}
          </button>
        </div>

        <p v-if="createMessage" class="feedback-banner feedback-success">{{ createMessage }}</p>
        <p v-if="createError" class="feedback-banner feedback-error">{{ createError }}</p>
      </article>

      <article class="panel target-user-list-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Registry</p>
            <h2>已注册目标用户</h2>
          </div>
          <button type="button" class="ghost-btn" :disabled="usersLoading" @click="refreshUsers">
            {{ usersLoading ? "刷新中..." : "刷新列表" }}
          </button>
        </div>

        <p v-if="usersError" class="feedback-banner feedback-error">{{ usersError }}</p>

        <div class="target-user-list">
          <article v-for="user in users" :key="user.id" class="target-user-card">
            <div class="target-user-card__head">
              <div>
                <strong>{{ user.display_name }}</strong>
                <small>{{ user.id }} / {{ user.group }}</small>
              </div>
              <span class="status-tag tone-neutral">{{ user.photo_count }} 张照片</span>
            </div>
            <div class="target-user-card__meta">
              <span>人脸特征 {{ user.face_embedding_count }}</span>
              <span>人体特征 {{ user.body_profile_count }}</span>
              <span>{{ new Date(user.updated_at).toLocaleString("zh-CN", { hour12: false }) }}</span>
            </div>
            <p class="helper-copy">{{ user.note || "暂无备注" }}</p>
            <div class="table-actions">
              <button
                type="button"
                class="ghost-btn"
                :disabled="deleteBusyId === user.id"
                @click="removeUser(user.id)"
              >
                {{ deleteBusyId === user.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </article>
          <div v-if="!usersLoading && !users.length" class="state-block state-empty">
            <strong>还没有目标用户档案</strong>
            <p>先上传一组目标人物照片，再执行姿态分析演示。</p>
          </div>
        </div>
      </article>

      <article class="panel target-pose-summary-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Analysis</p>
            <h2>姿态结论</h2>
          </div>
          <span class="status-tag" :class="analyzeResult?.ok ? 'tone-stable' : 'tone-warning'">
            {{ analyzeResult?.status ?? "未执行" }}
          </span>
        </div>

        <div class="target-user-check-grid">
          <article>
            <span>匹配结果</span>
            <strong>{{ analyzeResult?.target_match?.display_name ?? analyzeResult?.target_match?.decision ?? "未执行" }}</strong>
          </article>
          <article>
            <span>姿态 posture</span>
            <strong>{{ posePosture?.label ?? "-" }}</strong>
          </article>
          <article>
            <span>posture event</span>
            <strong>{{ postureEvent?.type ?? "-" }}</strong>
          </article>
          <article>
            <span>耗时</span>
            <strong>{{ analyzeResult?.bridge_latency_ms ?? "--" }} ms</strong>
          </article>
        </div>
      </article>

      <article class="panel target-pose-mm-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Multimodal Review</p>
            <h2>多模态快照复核能力</h2>
          </div>
          <span class="status-tag" :class="multimodalTone">
            {{ multimodalReview?.enabled ? "已启用" : "未启用" }}
          </span>
        </div>

        <div class="target-user-check-grid">
          <article>
            <span>Provider</span>
            <strong>{{ multimodalReview?.resolved_provider ?? "-" }}</strong>
          </article>
          <article>
            <span>Qwen Omni</span>
            <strong>{{ multimodalReview?.qwen_omni_model ?? "-" }}</strong>
          </article>
          <article>
            <span>Min Score</span>
            <strong>{{ multimodalReview?.min_score ?? "--" }}</strong>
          </article>
          <article>
            <span>Timeout</span>
            <strong>{{ multimodalReview?.timeout_seconds ?? "--" }} s</strong>
          </article>
        </div>

        <div class="target-pose-mm-panel__summary">
          <span class="status-tag" :class="multimodalReview?.dashscope_configured ? 'tone-stable' : 'tone-warning'">
            DashScope {{ multimodalReview?.dashscope_configured ? "已配置" : "未配置" }}
          </span>
          <span class="status-tag" :class="multimodalReview?.siliconflow_configured ? 'tone-stable' : 'tone-warning'">
            SiliconFlow {{ multimodalReview?.siliconflow_configured ? "已配置" : "未配置" }}
          </span>
        </div>

        <p class="helper-copy">
          这部分是系统已有的全局跌倒检测能力：在跌倒主链触发快照后，可交给多模态模型进行图像复核。当前页面展示的是能力状态，不代表本次单目标姿态分析已经触发了多模态复核。
        </p>
      </article>

      <article class="panel target-pose-preview-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Preview</p>
            <h2>原始画面与处理后画面</h2>
          </div>
          <div class="target-pose-preview-panel__status">
            <span class="status-tag" :class="livePreviewMode === 'stream' ? 'tone-stable' : 'tone-warning'">
              {{ livePreviewMode === "stream" ? "实时预览" : "快照模式" }}
            </span>
            <span class="status-tag tone-neutral">原始 / 处理后并排</span>
          </div>
        </div>

        <p v-if="livePreviewError" class="feedback-banner feedback-error">{{ livePreviewError }}</p>

        <div class="target-pose-preview-grid">
          <figure class="target-pose-preview-card">
            <figcaption>
              <span>原始画面</span>
              <button type="button" class="ghost-btn mini-switch" @click="retryLivePreview">
                重试实时预览
              </button>
            </figcaption>
            <div class="target-pose-preview-card__frame">
              <img
                v-if="livePreviewMode === 'stream'"
                class="target-pose-preview-card__image"
                :src="rawPreviewUrl"
                alt="实时原始画面"
                @load="handleLivePreviewLoaded"
                @error="handleLivePreviewError"
              />
              <img
                v-else-if="snapshotUrl"
                class="target-pose-preview-card__image"
                :src="snapshotUrl"
                alt="外部摄像头原始画面"
              />
              <div v-else class="target-pose-preview-card__empty">
                <strong>暂无原始画面</strong>
                <p>实时流或快照接通后，这里会显示原始视频画面。</p>
              </div>
            </div>
          </figure>

          <figure class="target-pose-preview-card">
            <figcaption>跌倒模型处理后画面</figcaption>
            <div class="target-pose-preview-card__frame">
              <img
                v-if="livePreviewMode === 'stream'"
                class="target-pose-preview-card__image"
                :src="processedPreviewUrl"
                alt="跌倒模型处理后画面"
              />
              <div v-else class="target-pose-preview-card__empty">
                <strong>暂无处理后画面</strong>
                <p>这里展示跌倒模型处理后的实时视频流，正常情况下应出现红色置信框与事件标签。</p>
              </div>
            </div>
          </figure>
        </div>
      </article>

      <article class="panel target-pose-visual-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Skeleton</p>
            <h2>多点位骨架处理画面</h2>
          </div>
          <div class="target-pose-visual-panel__controls">
            <span class="status-tag tone-neutral">姿态骨架流</span>
          </div>
        </div>

        <img
          class="target-pose-skeleton-stream"
          :src="skeletonPreviewUrl"
          alt="姿态骨架处理后画面"
        />
      </article>

      <article class="panel target-pose-guidance-panel">
        <h2>事件说明</h2>
        <div v-if="postureGuidance" class="target-pose-guidance">
          <div class="target-pose-guidance__hero">
            <strong>{{ postureGuidance.title ?? "状态正常" }}</strong>
            <span class="status-tag" :class="eventTone">
              {{ postureGuidance.level ?? "normal" }}
            </span>
          </div>
          <p class="helper-copy">
            {{ postureEvent?.reasons?.length ? postureEvent.reasons.join("；") : "当前未触发额外事件原因。" }}
          </p>
          <div class="target-pose-guidance__lists">
            <article>
              <span>Possible Causes</span>
              <ul>
                <li v-for="item in postureGuidance.possible_causes ?? []" :key="item">{{ item }}</li>
              </ul>
            </article>
            <article>
              <span>Immediate Actions</span>
              <ul>
                <li v-for="item in postureGuidance.immediate_actions ?? []" :key="item">{{ item }}</li>
              </ul>
            </article>
            <article>
              <span>Contraindications</span>
              <ul>
                <li v-for="item in postureGuidance.contraindications ?? []" :key="item">{{ item }}</li>
              </ul>
            </article>
          </div>
        </div>
        <div v-else class="state-block state-empty">
          <strong>等待姿态事件结果</strong>
          <p>执行目标姿态分析后，这里会展示 posture event 的说明和建议动作。</p>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.target-pose-grid,
.target-pose-hero,
.target-pose-hero__main,
.target-user-form,
.target-user-list,
.target-pose-guidance {
  display: grid;
  gap: 16px;
}

.target-pose-hero {
  padding: 28px;
  border-radius: 28px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid rgba(37, 99, 235, 0.16);
}

.target-pose-hero__main {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.target-user-actions,
.target-user-card__meta,
.dashboard-chip-row,
.target-pose-preview-panel__status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.target-user-form {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.target-user-form__wide {
  grid-column: span 2;
}

.target-user-file {
  padding-block: 10px;
}

.target-user-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--line-medium);
  background: #ffffff;
}

.target-user-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.target-user-card__head strong {
  display: block;
  color: var(--text-main);
  font-size: 1rem;
}

.target-user-card__head small {
  display: block;
  margin-top: 6px;
  color: var(--text-muted);
}

.target-user-card__meta span {
  border-radius: 999px;
  padding: 6px 10px;
  background: #f1f5f9;
  border: 1px solid var(--line-medium);
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 600;
}

.target-user-check-grid,
.target-pose-guidance__lists {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.target-pose-mm-panel__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.target-pose-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.target-pose-preview-card {
  display: grid;
  gap: 10px;
  margin: 0;
}

.target-pose-preview-card figcaption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.88rem;
  color: var(--text-sub);
  font-weight: 700;
}

.target-pose-preview-card__frame,
.target-pose-skeleton-stream {
  width: 100%;
  min-height: 360px;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background:
    radial-gradient(circle at top, rgba(96, 165, 250, 0.12), transparent 30%),
    linear-gradient(180deg, #0f172a 0%, #111827 100%);
}

.target-pose-preview-card__frame {
  position: relative;
}

.target-pose-preview-card__image,
.target-pose-skeleton-stream {
  display: block;
  object-fit: cover;
}

.target-pose-preview-card__image {
  width: 100%;
  height: 100%;
}

.target-pose-skeleton-stream {
  height: 360px;
}

.target-pose-preview-card__empty {
  min-height: 360px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  text-align: center;
  padding: 20px;
  color: rgba(255, 255, 255, 0.88);
}

.target-pose-preview-card__empty p {
  margin: 0;
  color: rgba(255, 255, 255, 0.7);
}

.target-pose-visual-panel {
  display: grid;
  gap: 14px;
}

.target-pose-visual-panel__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.target-user-check-grid article,
.target-pose-guidance__lists article {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--line-medium);
  background: #f8fafc;
}

.target-user-check-grid span,
.target-pose-guidance__lists article span {
  color: var(--text-sub);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.target-user-check-grid strong {
  color: var(--text-main);
  font-size: 1.2rem;
  line-height: 1.15;
}

.target-pose-guidance__hero {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.target-pose-guidance__hero strong {
  font-size: 1.1rem;
  color: var(--text-main);
}

.target-pose-guidance__lists ul {
  margin: 0;
  padding-left: 18px;
  color: var(--text-sub);
  line-height: 1.7;
}

@media (max-width: 960px) {
  .target-pose-hero__main,
  .target-user-form,
  .target-user-check-grid,
  .target-pose-preview-grid,
  .target-pose-guidance__lists {
    grid-template-columns: 1fr;
  }

  .target-user-form__wide {
    grid-column: span 1;
  }
}
</style>
