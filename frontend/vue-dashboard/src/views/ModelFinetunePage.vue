<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  FileText,
  FlaskConical,
  GitBranch,
  PlayCircle,
  RefreshCw,
  Route,
  ShieldCheck,
} from "lucide-vue-next";
import { API_BASE } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";

const props = defineProps<{ refreshKey?: number }>();

type FineTuneStatus = "ready" | "needs_export" | "native_ready" | "baseline_ready" | "blocked" | "incomplete" | "registered" | string;

interface ArchitectureLayer {
  name: string;
  title: string;
  status: FineTuneStatus;
}

interface DatasetExport {
  name: string;
  path: string;
  exists: boolean;
  rows: number;
  config_exists: boolean;
}

interface TrainingTemplate {
  name: string;
  path: string;
  strategy: string;
  accelerators: string[];
  command: string;
}

interface EvalSuite {
  name: string;
  exists: boolean;
  cases: number;
}

interface EvalGates {
  exists?: boolean;
  thresholds?: Record<string, number>;
  suites?: EvalSuite[];
}

interface AdapterRoute {
  task: string;
  base_model: string;
  adapter: string;
  adapter_path: string;
  status: string;
  fallback: string;
  min_eval_score: number;
  feature_flag: string;
  path_exists?: boolean;
}

interface AdapterRegistry {
  version?: number;
  default_policy?: string;
  routes?: AdapterRoute[];
}

interface CapabilitySnapshot {
  ok?: boolean;
  modules?: Record<string, boolean>;
  native_ready?: Record<string, boolean>;
  cuda_available?: boolean;
  cuda_name?: string;
  torch_version?: string;
  recommendations?: string[];
}

interface FineTuneOverview {
  architecture: ArchitectureLayer[];
  capability: CapabilitySnapshot;
  templates: TrainingTemplate[];
  datasets: DatasetExport[];
  eval_gates: EvalGates;
  adapters: AdapterRegistry;
  commands: Array<{ name: string; command: string }>;
}

const defaultTuningUrl = "http://127.0.0.1:7860";
const rawTuningUrl = (import.meta.env.VITE_MODEL_TUNING_URL ?? defaultTuningUrl).trim();
const tuningUrl = rawTuningUrl.replace(/\/$/, "") || defaultTuningUrl;

const loading = ref(false);
const actionLoading = ref("");
const error = ref("");
const overview = ref<FineTuneOverview | null>(null);
const workbenchReachable = ref(false);
const workbenchLoading = ref(false);
const workbenchError = ref("");
const iframeVersion = ref(0);
let workbenchProbeController: AbortController | null = null;

const iframeSrc = computed(() => `${tuningUrl}/?embedded=health-console&v=${iframeVersion.value}`);
const displayUrl = computed(() => tuningUrl.replace(/^https?:\/\//, ""));
const capability = computed(() => overview.value?.capability ?? {});
const modules = computed(() => capability.value.modules ?? {});
const nativeReady = computed(() => capability.value.native_ready ?? {});
const datasets = computed(() => overview.value?.datasets ?? []);
const templates = computed(() => overview.value?.templates ?? []);
const adapters = computed(() => overview.value?.adapters.routes ?? []);
const evalSuites = computed(() => overview.value?.eval_gates.suites ?? []);

const highLevelCards = computed(() => [
  {
    label: "训练环境",
    value: nativeReady.value.qlora_4bit_8bit ? "QLoRA 可用" : nativeReady.value.sft_lora ? "LoRA 可用" : "待修复",
    detail: capability.value.cuda_available ? `CUDA: ${capability.value.cuda_name ?? "GPU"}` : "当前未检测到 CUDA",
    ok: Boolean(nativeReady.value.sft_lora),
    icon: Activity,
  },
  {
    label: "数据层",
    value: `${datasets.value.filter((item) => item.exists).length}/${datasets.value.length} 已导出`,
    detail: "健康报告、工具轨迹、跌倒偏好、安全拒答",
    ok: datasets.value.length > 0 && datasets.value.every((item) => item.exists && item.rows > 0),
    icon: Database,
  },
  {
    label: "评测门禁",
    value: `${evalSuites.value.filter((item) => item.exists).length}/${evalSuites.value.length} 套件`,
    detail: "工具调用、事实一致性、安全边界、响应速度",
    ok: evalSuites.value.length > 0 && evalSuites.value.every((item) => item.exists && item.cases > 0),
    icon: ShieldCheck,
  },
  {
    label: "Adapter 路由",
    value: `${adapters.value.length} 条任务路由`,
    detail: "candidate -> shadow -> canary -> stable",
    ok: adapters.value.length > 0,
    icon: Route,
  },
]);

function statusLabel(status: FineTuneStatus) {
  const labels: Record<string, string> = {
    ready: "就绪",
    needs_export: "待导出",
    native_ready: "原生可用",
    baseline_ready: "基线可用",
    blocked: "受阻",
    incomplete: "不完整",
    registered: "已登记",
  };
  return labels[status] ?? status;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json() as Promise<T>;
}

async function refreshOverview() {
  loading.value = true;
  error.value = "";
  try {
    overview.value = await requestJson<FineTuneOverview>("/model-finetune/overview");
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    loading.value = false;
  }
}

async function runAction(kind: "export" | "eval") {
  actionLoading.value = kind;
  error.value = "";
  try {
    const path = kind === "export" ? "/model-finetune/datasets/export" : "/model-finetune/eval-gates/run";
    await requestJson(path, { method: "POST" });
    await refreshOverview();
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    actionLoading.value = "";
  }
}

function openWorkbench() {
  window.open(tuningUrl, "_blank", "noopener,noreferrer");
}

function refreshWorkbench() {
  iframeVersion.value += 1;
  void probeWorkbench();
}

async function probeWorkbench() {
  workbenchProbeController?.abort();
  const controller = new AbortController();
  workbenchProbeController = controller;
  workbenchLoading.value = true;
  workbenchError.value = "";
  try {
    await fetch(`${tuningUrl}/`, { method: "GET", mode: "no-cors", signal: controller.signal });
    workbenchReachable.value = true;
  } catch (exc) {
    if ((exc as Error)?.name === "AbortError") return;
    workbenchReachable.value = false;
    workbenchError.value = exc instanceof Error ? exc.message : String(exc);
  } finally {
    if (workbenchProbeController === controller) {
      workbenchLoading.value = false;
      workbenchProbeController = null;
    }
  }
}

watch(
  () => props.refreshKey,
  (key, previous) => {
    if (key == null || previous == null) return;
    void refreshOverview();
    refreshWorkbench();
  },
);

onMounted(() => {
  void refreshOverview();
  void probeWorkbench();
});

onUnmounted(() => {
  workbenchProbeController?.abort();
});
</script>

<template>
  <section class="model-page">
    <PageHeader
      eyebrow="LLM Fine-tuning"
      title="大模型微调运营面板"
      description="把数据导出、训练模板、评测门禁和 adapter 路由集中管理；新模型先离线评测和灰度路由，不影响摄像头、告警和社区端主链路。"
      :meta="['数据层 / 训练层 / 评测层 / 部署层', 'LLaMA-Factory', 'Adapter 灰度']"
    >
      <template #actions>
        <button type="button" class="model-btn model-btn--ghost" :disabled="loading" @click="refreshOverview">
          <RefreshCw :size="16" />
          刷新状态
        </button>
        <button type="button" class="model-btn model-btn--primary" @click="openWorkbench">
          <ExternalLink :size="16" />
          打开 7860
        </button>
      </template>
    </PageHeader>

    <div v-if="error" class="model-alert">
      <AlertTriangle :size="18" />
      <span>{{ error }}</span>
    </div>

    <section class="model-status-grid">
      <article v-for="card in highLevelCards" :key="card.label" class="model-status-card">
        <div class="model-status-card__icon" :class="{ 'model-status-card__icon--ok': card.ok }">
          <component :is="card.icon" :size="20" />
        </div>
        <div class="model-status-card__copy">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="model-layer-panel">
      <article v-for="layer in overview?.architecture ?? []" :key="layer.name" class="model-layer-card">
        <span>{{ layer.title }}</span>
        <strong>{{ statusLabel(layer.status) }}</strong>
      </article>
    </section>

    <section class="model-grid">
      <article class="model-section">
        <div class="model-section__head">
          <div>
            <p class="model-section__eyebrow">DATA</p>
            <h2>领域数据导出</h2>
          </div>
          <button
            type="button"
            class="model-btn model-btn--ghost"
            :disabled="Boolean(actionLoading)"
            @click="runAction('export')"
          >
            <PlayCircle :size="16" />
            {{ actionLoading === "export" ? "导出中..." : "导出数据" }}
          </button>
        </div>
        <div class="model-list">
          <div v-for="item in datasets" :key="item.name" class="model-list-row">
            <Database :size="17" />
            <div>
              <strong>{{ item.name }}</strong>
              <small>{{ item.rows }} rows · {{ item.exists ? "文件已生成" : "等待导出" }}</small>
            </div>
          </div>
        </div>
      </article>

      <article class="model-section">
        <div class="model-section__head">
          <div>
            <p class="model-section__eyebrow">TRAINING</p>
            <h2>训练模板</h2>
          </div>
          <FlaskConical :size="22" />
        </div>
        <div class="model-list">
          <div v-for="item in templates" :key="item.name" class="model-list-row model-list-row--stack">
            <FileText :size="17" />
            <div>
              <strong>{{ item.name }}</strong>
              <small>{{ item.strategy }}</small>
              <code>{{ item.command }}</code>
              <em v-if="item.accelerators.length">{{ item.accelerators.join(" / ") }}</em>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="model-grid">
      <article class="model-section">
        <div class="model-section__head">
          <div>
            <p class="model-section__eyebrow">EVAL</p>
            <h2>养老健康评测门禁</h2>
          </div>
          <button
            type="button"
            class="model-btn model-btn--ghost"
            :disabled="Boolean(actionLoading)"
            @click="runAction('eval')"
          >
            <PlayCircle :size="16" />
            {{ actionLoading === "eval" ? "评测中..." : "运行门禁" }}
          </button>
        </div>
        <div class="model-list">
          <div v-for="suite in evalSuites" :key="suite.name" class="model-list-row">
            <CheckCircle2 :size="17" />
            <div>
              <strong>{{ suite.name }}</strong>
              <small>{{ suite.cases }} cases · {{ suite.exists ? "已配置" : "缺失" }}</small>
            </div>
          </div>
        </div>
      </article>

      <article class="model-section">
        <div class="model-section__head">
          <div>
            <p class="model-section__eyebrow">DEPLOY</p>
            <h2>Adapter 任务路由</h2>
          </div>
          <GitBranch :size="22" />
        </div>
        <div class="model-list">
          <div v-for="item in adapters" :key="item.task" class="model-list-row model-list-row--stack">
            <Route :size="17" />
            <div>
              <strong>{{ item.task }} -> {{ item.adapter }}</strong>
              <small>{{ item.status }} · min score {{ item.min_eval_score }} · fallback {{ item.fallback }}</small>
              <code>{{ item.feature_flag }}</code>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="model-section model-section--wide">
      <div class="model-section__head">
        <div>
          <p class="model-section__eyebrow">CAPABILITY</p>
          <h2>当前可调用能力</h2>
        </div>
        <ShieldCheck :size="22" />
      </div>
      <div class="module-grid">
        <span v-for="(enabled, name) in modules" :key="name" :class="{ ok: enabled }">
          {{ name }} · {{ enabled ? "可用" : "不可用" }}
        </span>
      </div>
      <p v-for="item in capability.recommendations ?? []" :key="item" class="model-note">{{ item }}</p>
    </section>

    <section class="model-workbench">
      <div class="model-section__head">
        <div>
          <p class="model-section__eyebrow">Embedded Console</p>
          <h2>LLaMA-Factory 工作台</h2>
          <p>服务地址 {{ displayUrl }}。训练任务建议先使用上方模板和评测门禁管理，再进入原生工作台细调参数。</p>
        </div>
        <button type="button" class="model-btn model-btn--ghost" @click="refreshWorkbench">
          <RefreshCw :size="16" />
          重试连接
        </button>
      </div>
      <div class="model-workbench__frame">
        <iframe
          v-if="workbenchReachable"
          :key="iframeVersion"
          :src="iframeSrc"
          title="LLaMA-Factory 微调工作台"
          loading="eager"
          referrerpolicy="no-referrer"
        />
        <div v-else class="model-workbench__fallback">
          <ExternalLink :size="28" />
          <strong>{{ workbenchLoading ? "正在检测 7860 工作台..." : "7860 工作台暂不可访问" }}</strong>
          <p>{{ workbenchError || "请先运行 scripts/start_model_tuning_console.ps1，或使用上方管理面板准备数据和模板。" }}</p>
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.model-page {
  display: grid;
  gap: 18px;
  align-content: start;
  padding-bottom: 16px;
}

.model-btn {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 14px;
  border-radius: 8px;
  font-weight: 800;
  cursor: pointer;
  border: 1px solid transparent;
}

.model-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.model-btn--ghost {
  background: #ffffff;
  color: #0f172a;
  border-color: #cbd5e1;
}

.model-btn--primary {
  background: #2563eb;
  color: #ffffff;
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
}

.model-status-grid,
.model-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.model-status-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.model-status-card,
.model-section,
.model-layer-card,
.model-workbench {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.model-status-card {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
  min-height: 112px;
  padding: 16px;
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

.model-status-card__copy,
.model-list-row > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.model-status-card__copy span,
.model-section__eyebrow {
  color: #2563eb;
  font-size: 0.75rem;
  font-weight: 900;
  text-transform: uppercase;
}

.model-status-card__copy strong,
.model-list-row strong,
.model-layer-card strong {
  color: #0f172a;
}

.model-status-card__copy small,
.model-list-row small,
.model-section p {
  color: #64748b;
  line-height: 1.5;
}

.model-layer-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.model-layer-card {
  padding: 14px;
  display: grid;
  gap: 8px;
}

.model-layer-card span {
  color: #64748b;
  font-weight: 800;
}

.model-section,
.model-workbench {
  padding: 18px;
  display: grid;
  gap: 14px;
}

.model-section--wide {
  grid-column: 1 / -1;
}

.model-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.model-section__head h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.1rem;
}

.model-section__eyebrow {
  margin: 0 0 4px;
}

.model-list {
  display: grid;
  gap: 10px;
}

.model-list-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
  padding: 12px;
  border-radius: 8px;
  background: #f8fafc;
}

.model-list-row code {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 6px 8px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 0.78rem;
}

.model-list-row em {
  color: #1d4ed8;
  font-style: normal;
  font-weight: 800;
  font-size: 0.78rem;
}

.module-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.module-grid span {
  padding: 7px 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-weight: 800;
  font-size: 0.8rem;
}

.module-grid span.ok {
  background: #dcfce7;
  color: #166534;
}

.model-note {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff7ed;
  color: #9a3412;
}

.model-workbench__frame {
  height: min(62vh, 720px);
  min-height: 460px;
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
  gap: 12px;
  padding: 28px;
  text-align: center;
}

@media (max-width: 1180px) {
  .model-status-grid,
  .model-layer-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .model-status-grid,
  .model-grid,
  .model-layer-panel {
    grid-template-columns: 1fr;
  }
}
</style>
