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
import TargetPoseOverlaySvg from "../components/TargetPoseOverlaySvg.vue";
import TargetPoseSkeletonView from "../components/TargetPoseSkeletonView.vue";
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
const snapshotNaturalSize = ref<{ width: number; height: number } | null>(null);
const fallStatus = ref<CameraFallDetectionStatusResponse | null>(null);
const poseConfig = ref<CameraPoseDetectionConfigResponse | null>(null);
const poseToggleBusy = ref(false);
const showPoseOverlay = ref(true);
const labelMode = ref<"index" | "name">("index");
const selectedPointIndex = ref<number | null>(null);
const selectedTrendTimestamp = ref<number | null>(null);
const trendItems = ref<Array<{
  ts: number;
  posture: string;
  event: string;
  confidence: number;
  postureRaw: typeof analyzeResult.value;
}>>([]);

const form = ref({
  displayName: "",
  group: "default",
  note: "",
  files: [] as File[],
});

const pageMeta = computed(() => [
  `已注册 ${users.value.length}`,
  `摄像头 ${analyzeSource.value === "local" ? "本地电脑摄像头" : (externalHealth.value?.running ? "已接通" : "待联通")}`,
  `流 ${analyzeSource.value === "local" ? "local-camera" : (externalHealth.value?.stream ?? "unknown")}`,
]);

const selectedFileSummary = computed(() => {
  if (!form.value.files.length) return "未选择照片";
  if (form.value.files.length === 1) return form.value.files[0].name;
  return `${form.value.files.length} 张照片已选择`;
});

const targetPose = computed(() => analyzeResult.value?.target_pose?.pose ?? null);
const posePoints = computed(() => targetPose.value?.points ?? []);
const poseConnections = computed(() => targetPose.value?.connections ?? []);
const posePosture = computed(() => targetPose.value?.posture ?? null);
const poseQuality = computed(() => targetPose.value?.quality ?? null);
const postureEvent = computed(() => analyzeResult.value?.posture_event ?? null);
const postureGuidance = computed(() => analyzeResult.value?.posture_guidance ?? null);
const roiBbox = computed(() => analyzeResult.value?.tracking?.roi?.bbox ?? null);
const multimodalReview = computed(() => fallStatus.value?.multimodal_review ?? null);
const eventTone = computed(() => {
  const level = postureEvent.value?.level ?? postureGuidance.value?.level ?? "";
  if (level === "critical" || level === "danger") return "tone-critical";
  if (level === "warning") return "tone-warning";
  if (level === "attention") return "tone-info";
  return "tone-neutral";
});
const multimodalTone = computed(() => {
  if (!multimodalReview.value?.enabled) return "tone-neutral";
  if (multimodalReview.value?.dashscope_configured || multimodalReview.value?.siliconflow_configured) {
    return "tone-stable";
  }
  return "tone-warning";
});
const snapshotUrl = computed(() => {
  const localSnapshot = analyzeSource.value === "local" ? api.getLocalCameraSnapshotUrl() : "";
  const base = analyzeResult.value?.camera_source?.snapshot_url || localSnapshot || externalHealth.value?.snapshot_url;
  if (!base) return "";
  return `${base}${base.includes("?") ? "&" : "?"}t=${Date.now()}`;
});
const roiOverlayStyle = computed(() => {
  const bbox = roiBbox.value;
  const imageSize = snapshotNaturalSize.value;
  if (!bbox || bbox.length !== 4 || !imageSize) return null;
  const [x1, y1, x2, y2] = bbox;
  return {
    left: `${(x1 / imageSize.width) * 100}%`,
    top: `${(y1 / imageSize.height) * 100}%`,
    width: `${((x2 - x1) / imageSize.width) * 100}%`,
    height: `${((y2 - y1) / imageSize.height) * 100}%`,
  };
});
const roiPreviewStyle = computed(() => {
  const bbox = roiBbox.value;
  const imageSize = snapshotNaturalSize.value;
  if (!bbox || bbox.length !== 4 || !imageSize) return null;
  const [x1, y1, x2, y2] = bbox;
  const width = Math.max(1, x2 - x1);
  const height = Math.max(1, y2 - y1);
  return {
    backgroundImage: `url(${snapshotUrl.value})`,
    backgroundSize: `${imageSize.width}px ${imageSize.height}px`,
    backgroundPosition: `-${x1}px -${y1}px`,
    width: `${Math.min(100, width)}%`,
    maxWidth: `${Math.max(180, Math.min(360, width))}px`,
    aspectRatio: `${width} / ${height}`,
  };
});
const highlightParts = computed(() => {
  const parts = new Set<string>();
  const postureLabel = posePosture.value?.label ?? "";
  const eventType = postureEvent.value?.type ?? "";
  if (postureLabel === "hand_to_chest_or_abdomen" || eventType === "hand_to_chest_or_abdomen") {
    parts.add("left_arm");
    parts.add("right_arm");
    parts.add("torso");
  }
  if (postureLabel === "leaning" || eventType === "abnormal_lean" || eventType === "fall_slow") {
    parts.add("torso");
    parts.add("left_leg");
    parts.add("right_leg");
  }
  if (postureLabel === "fall_like" || eventType === "fall_fast") {
    parts.add("torso");
    parts.add("left_leg");
    parts.add("right_leg");
    parts.add("left_arm");
    parts.add("right_arm");
  }
  return Array.from(parts);
});
const highlightPointIndices = computed(() => {
  const indices = new Set<number>();
  const postureLabel = posePosture.value?.label ?? "";
  const eventType = postureEvent.value?.type ?? "";
  if (postureLabel === "hand_to_chest_or_abdomen" || eventType === "hand_to_chest_or_abdomen") {
    [5, 6, 9, 10, 11, 12].forEach((index) => indices.add(index));
  }
  if (postureLabel === "leaning" || eventType === "abnormal_lean" || eventType === "fall_slow") {
    [5, 6, 11, 12, 13, 14, 15, 16].forEach((index) => indices.add(index));
  }
  if (postureLabel === "fall_like" || eventType === "fall_fast") {
    [5, 6, 7, 8, 11, 12, 13, 14, 15, 16].forEach((index) => indices.add(index));
  }
  return Array.from(indices);
});
const selectedPoint = computed(() => posePoints.value.find((point) => point.index === selectedPointIndex.value) ?? null);

function formatError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  form.value.files = Array.from(input.files ?? []);
}

function onSnapshotLoaded(event: Event) {
  const image = event.target as HTMLImageElement;
  if (!image?.naturalWidth || !image?.naturalHeight) return;
  snapshotNaturalSize.value = {
    width: image.naturalWidth,
    height: image.naturalHeight,
  };
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
      ? `创建完成，但有提示：${created.warnings.join("、")}`
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
    analyzeResult.value = analyzeSource.value === "local"
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
    selectedPointIndex.value = null;
    selectedTrendTimestamp.value = null;
    trendItems.value = [
      ...trendItems.value.slice(-7),
      {
        ts: Date.now(),
        posture: analyzeResult.value?.target_pose?.pose?.posture?.label ?? "unknown",
        event: analyzeResult.value?.posture_event?.type ?? "normal",
        confidence: Number(analyzeResult.value?.posture_event?.confidence ?? analyzeResult.value?.target_pose?.pose?.posture?.confidence ?? 0),
        postureRaw: analyzeResult.value,
      },
    ];
    if (analyzeSource.value === "external") {
      await refreshExternalHealth();
    }
    await refreshFallStatus();
    await refreshPoseConfig();
  } catch (error) {
    externalHealthError.value = formatError(
      error,
      analyzeSource.value === "local" ? "本地摄像头姿态分析执行失败。" : "目标姿态分析执行失败。",
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

function selectPoint(index: number | null) {
  selectedPointIndex.value = index;
}

function applyTrendItem(ts: number) {
  const item = trendItems.value.find((entry) => entry.ts === ts);
  if (!item) return;
  analyzeResult.value = item.postureRaw;
  selectedTrendTimestamp.value = ts;
  selectedPointIndex.value = null;
}
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Target Pose Demo"
      title="单目标姿态分析演示"
      description="聚焦目标人物 ROI 内的骨架估计、轻量姿态判断和异常行为提示。"
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

        <div class="target-pose-metrics">
          <div class="target-pose-metrics__item">
            <span>quality</span>
            <strong>{{ poseQuality?.mean_score ?? "--" }}</strong>
            <small>可见点 {{ poseQuality?.visible_points ?? 0 }} / 估计点 {{ poseQuality?.estimated_points ?? 0 }}</small>
          </div>
          <div class="target-pose-metrics__item">
            <span>angle</span>
            <strong>{{ posePosture?.torso_angle_deg ?? "--" }}</strong>
            <small>躯干角度（度）</small>
          </div>
          <div class="target-pose-metrics__item">
            <span>confidence</span>
            <strong>{{ postureEvent?.confidence ?? posePosture?.confidence ?? "--" }}</strong>
            <small>姿态/事件置信度</small>
          </div>
          <div class="target-pose-metrics__item">
            <span>track</span>
            <strong>{{ analyzeResult?.tracking?.track_id ?? "--" }}</strong>
            <small>候选 {{ analyzeResult?.tracking?.candidate_count ?? 0 }}</small>
          </div>
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
          这部分是系统已有的全局跌倒检测能力：在跌倒主链触发快照后，可交给多模态模型进行图像复核。
          当前页面展示的是能力状态，不代表本次单目标姿态分析已经触发了多模态复核。
        </p>
      </article>

      <article class="panel target-pose-preview-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Preview</p>
            <h2>原始画面与目标 ROI</h2>
          </div>
          <span class="status-tag tone-neutral">{{ snapshotUrl ? "快照已接入" : "等待快照" }}</span>
        </div>

        <div class="target-pose-preview-grid">
          <figure class="target-pose-preview-card">
            <figcaption>原始画面 + ROI / 骨架</figcaption>
            <div class="target-pose-preview-card__frame">
              <img
                v-if="snapshotUrl"
                class="target-pose-preview-card__image"
                :src="snapshotUrl"
                alt="外部摄像头原始画面"
                @load="onSnapshotLoaded"
              />
              <div
                v-if="roiOverlayStyle"
                class="target-pose-preview-card__roi-overlay"
                :style="roiOverlayStyle"
              />
              <TargetPoseOverlaySvg
                v-if="showPoseOverlay && snapshotNaturalSize && posePoints.length"
                :points="posePoints"
                :connections="poseConnections"
                :bbox="roiBbox"
                :image-width="snapshotNaturalSize.width"
                :image-height="snapshotNaturalSize.height"
                :label-mode="labelMode"
                :highlight-parts="highlightParts"
                :highlight-point-indices="highlightPointIndices"
              />
              <div v-else class="target-pose-preview-card__empty">
                <strong>暂无快照</strong>
                <p>执行目标姿态分析后，这里会展示外部摄像头最新画面。</p>
              </div>
            </div>
          </figure>

          <figure class="target-pose-preview-card">
            <figcaption>目标 ROI</figcaption>
            <div class="target-pose-preview-card__frame">
              <div
                v-if="roiPreviewStyle"
                class="target-pose-preview-card__roi"
                :style="roiPreviewStyle"
              />
              <div v-else class="target-pose-preview-card__empty">
                <strong>暂无 ROI</strong>
                <p>目标匹配成功后，这里会裁剪展示目标人物 ROI。</p>
              </div>
            </div>
          </figure>
        </div>
      </article>

      <article class="panel target-pose-visual-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Skeleton</p>
            <h2>火柴人骨架渲染</h2>
          </div>
          <div class="target-pose-visual-panel__controls">
            <span class="status-tag tone-neutral">ROI {{ roiBbox ? "已锁定" : "未锁定" }}</span>
            <button type="button" class="ghost-btn mini-switch" @click="showPoseOverlay = !showPoseOverlay">
              {{ showPoseOverlay ? "隐藏原图骨架" : "显示原图骨架" }}
            </button>
            <button type="button" class="ghost-btn mini-switch" @click="labelMode = labelMode === 'index' ? 'name' : 'index'">
              {{ labelMode === "index" ? "显示关键点名称" : "显示关键点编号" }}
            </button>
          </div>
        </div>

        <TargetPoseSkeletonView
          :points="posePoints"
          :connections="poseConnections"
          :bbox="roiBbox"
          title="目标人物骨架"
          :label-mode="labelMode"
          :highlight-parts="highlightParts"
          :highlight-point-indices="highlightPointIndices"
          :selected-point-index="selectedPointIndex"
          @select-point="selectPoint($event.index)"
        />

        <div v-if="selectedPoint" class="target-pose-selected-point">
          <strong>关键点详情</strong>
          <div class="target-pose-selected-point__grid">
            <span>名称 {{ selectedPoint.name }}</span>
            <span>编号 {{ selectedPoint.index }}</span>
            <span>X {{ selectedPoint.x }}</span>
            <span>Y {{ selectedPoint.y }}</span>
            <span>Score {{ selectedPoint.score }}</span>
            <span>Tracked {{ selectedPoint.tracked ? "yes" : "no" }}</span>
            <span>Estimated {{ selectedPoint.estimated ? "yes" : "no" }}</span>
          </div>
        </div>
      </article>

      <article class="panel target-pose-points-panel">
        <h2>关键点与骨架</h2>
        <div class="target-pose-points-panel__meta">
          <span class="meta-pill">Points {{ posePoints.length }}</span>
          <span class="meta-pill">Links {{ poseConnections.length }}</span>
          <span class="meta-pill">Source Pose {{ postureEvent?.source_pose ?? posePosture?.label ?? "-" }}</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Index</th>
                <th>Name</th>
                <th>X</th>
                <th>Y</th>
                <th>Score</th>
                <th>Tracked</th>
                <th>Estimated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="point in posePoints" :key="`${point.index}-${point.name}`">
                <td>{{ point.index }}</td>
                <td>{{ point.name }}</td>
                <td>{{ point.x }}</td>
                <td>{{ point.y }}</td>
                <td>{{ point.score }}</td>
                <td>{{ point.tracked ? "yes" : "no" }}</td>
                <td>{{ point.estimated ? "yes" : "no" }}</td>
              </tr>
              <tr v-if="!posePoints.length">
                <td colspan="7">执行分析后会在这里展示 17 个关键点坐标。</td>
              </tr>
            </tbody>
          </table>
        </div>
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
            {{ postureEvent?.reasons?.length ? postureEvent.reasons.join("、") : "当前未触发额外事件原因。" }}
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

      <article class="panel target-pose-trend-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Timeline</p>
            <h2>动作趋势时间条</h2>
          </div>
          <span class="status-tag tone-neutral">最近 {{ trendItems.length }} 次</span>
        </div>

        <div v-if="trendItems.length" class="target-pose-trend-list">
          <article
            v-for="item in [...trendItems].reverse()"
            :key="item.ts"
            class="target-pose-trend-item"
            :class="{ 'is-selected': selectedTrendTimestamp === item.ts }"
            @click="applyTrendItem(item.ts)"
          >
            <div class="target-pose-trend-item__time">
              {{ new Date(item.ts).toLocaleTimeString("zh-CN", { hour12: false }) }}
            </div>
            <div class="target-pose-trend-item__body">
              <strong>{{ item.posture }}</strong>
              <span>{{ item.event }}</span>
            </div>
            <div class="target-pose-trend-item__confidence" :class="item.event === 'fall_fast' ? 'is-critical' : (item.event === 'abnormal_lean' || item.event === 'fall_slow' || item.event === 'hand_to_chest_or_abdomen' ? 'is-warning' : '')">
              {{ item.confidence.toFixed(2) }}
            </div>
          </article>
        </div>
        <div v-else class="state-block state-empty">
          <strong>还没有趋势数据</strong>
          <p>连续执行几次目标姿态分析后，这里会显示 posture / posture_event 的变化。</p>
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
.target-pose-points-panel__meta {
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
.target-pose-metrics,
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
  gap: 14px;
}

.target-pose-preview-card {
  display: grid;
  gap: 10px;
  margin: 0;
}

.target-pose-preview-card figcaption {
  font-size: 0.88rem;
  color: var(--text-sub);
  font-weight: 700;
}

.target-pose-preview-card__frame {
  min-height: 280px;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
  display: grid;
  place-items: center;
  position: relative;
}

.target-pose-preview-card__image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.target-pose-preview-card__roi {
  background-repeat: no-repeat;
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.55);
  box-shadow: 0 14px 24px rgba(15, 23, 42, 0.22);
}

.target-pose-preview-card__roi-overlay {
  position: absolute;
  border: 2px solid rgba(244, 63, 94, 0.92);
  border-radius: 14px;
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.08), 0 0 0 4px rgba(244, 63, 94, 0.15);
  pointer-events: none;
}

.target-pose-preview-card__empty {
  display: grid;
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

.target-pose-selected-point {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--line-medium);
  background: #f8fafc;
}

.target-pose-selected-point strong {
  color: var(--text-main);
}

.target-pose-selected-point__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.target-pose-selected-point__grid span {
  border-radius: 999px;
  padding: 6px 10px;
  background: #ffffff;
  border: 1px solid var(--line-medium);
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 600;
}

.target-user-check-grid article,
.target-pose-metrics__item,
.target-pose-guidance__lists article {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--line-medium);
  background: #f8fafc;
}

.target-user-check-grid span,
.target-pose-metrics__item span,
.target-pose-guidance__lists article span {
  color: var(--text-sub);
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.target-user-check-grid strong,
.target-pose-metrics__item strong {
  color: var(--text-main);
  font-size: 1.2rem;
  line-height: 1.15;
}

.target-pose-metrics__item small {
  color: var(--text-muted);
  line-height: 1.6;
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

.target-pose-trend-list {
  display: grid;
  gap: 10px;
}

.target-pose-trend-item {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr) 72px;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--line-medium);
  background: #f8fafc;
  cursor: pointer;
  transition: all 180ms ease;
}

.target-pose-trend-item:hover {
  border-color: rgba(59, 130, 246, 0.28);
  transform: translateY(-1px);
}

.target-pose-trend-item.is-selected {
  border-color: rgba(59, 130, 246, 0.42);
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.12);
}

.target-pose-trend-item__time {
  color: var(--text-sub);
  font-size: 0.84rem;
  font-weight: 700;
}

.target-pose-trend-item__body {
  display: grid;
  gap: 4px;
}

.target-pose-trend-item__body strong {
  color: var(--text-main);
  font-size: 0.95rem;
}

.target-pose-trend-item__body span,
.target-pose-trend-item__confidence {
  color: var(--text-sub);
  font-size: 0.84rem;
  font-weight: 600;
}

.target-pose-trend-item__confidence.is-critical {
  color: #dc2626;
}

.target-pose-trend-item__confidence.is-warning {
  color: #d97706;
}

@media (max-width: 960px) {
  .target-pose-hero__main,
  .target-user-form,
  .target-user-check-grid,
  .target-pose-preview-grid,
  .target-pose-metrics,
  .target-pose-guidance__lists {
    grid-template-columns: 1fr;
  }

  .target-pose-trend-item {
    grid-template-columns: 1fr;
  }

  .target-user-form__wide {
    grid-column: span 1;
  }
}
</style>
