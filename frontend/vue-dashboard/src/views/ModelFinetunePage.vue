<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Activity,
  Bot,
  DatabaseZap,
  ExternalLink,
  MonitorCheck,
  RefreshCw,
  ShieldCheck,
} from "lucide-vue-next";
import PageHeader from "../components/layout/PageHeader.vue";

const props = defineProps<{
  refreshKey?: number;
}>();

const defaultTuningUrl = "http://127.0.0.1:7860";
const rawTuningUrl = (import.meta.env.VITE_MODEL_TUNING_URL ?? defaultTuningUrl).trim();
const tuningUrl = rawTuningUrl.replace(/\/$/, "") || defaultTuningUrl;
const iframeVersion = ref(0);

const iframeSrc = computed(() => `${tuningUrl}/?embedded=health-console&v=${iframeVersion.value}`);
const displayUrl = computed(() => tuningUrl.replace(/^https?:\/\//, ""));
const serviceStatusText = computed(() => `服务地址 ${displayUrl.value}`);

const statusCards = computed(() => [
  {
    label: "训练环境",
    value: "独立 CUDA 环境",
    detail: "conda: llamafactory",
    icon: MonitorCheck,
  },
  {
    label: "服务状态",
    value: "本地工作台",
    detail: serviceStatusText.value,
    icon: Activity,
  },
  {
    label: "能力范围",
    value: "训练 / 评估 / 对话 / 导出",
    detail: "保持原有微调流程",
    icon: Bot,
  },
  {
    label: "数据与产物",
    value: "data / saves",
    detail: "沿用微调项目目录",
    icon: DatabaseZap,
  },
]);

const pageMeta = computed(() => ["社区与管理员可用", "本地服务嵌入", "默认中文界面"]);

function refreshWorkbench() {
  iframeVersion.value += 1;
}

function openWorkbench() {
  window.open(tuningUrl, "_blank", "noopener,noreferrer");
}

watch(
  () => props.refreshKey,
  (key, previous) => {
    if (key == null || previous == null) return;
    refreshWorkbench();
  },
);
</script>

<template>
  <section class="finetune-page">
    <PageHeader
      eyebrow="Model Training"
      title="模型微调中心"
      description="面向社区健康监测、告警解释和智能问答场景，统一完成领域数据训练、模型评估、对话验证与模型导出。"
      :meta="pageMeta"
    >
      <template #actions>
        <button type="button" class="finetune-btn finetune-btn--ghost" @click="refreshWorkbench">
          <RefreshCw :size="16" />
          刷新工作台
        </button>
        <button type="button" class="finetune-btn finetune-btn--primary" @click="openWorkbench">
          <ExternalLink :size="16" />
          独立打开
        </button>
      </template>
    </PageHeader>

    <section class="finetune-status-grid" aria-label="模型微调状态">
      <article v-for="card in statusCards" :key="card.label" class="finetune-status-card">
        <div class="finetune-status-card__icon">
          <component :is="card.icon" :size="20" />
        </div>
        <div class="finetune-status-card__copy">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </section>

    <section class="finetune-workbench" aria-label="模型微调工作台">
      <div class="finetune-workbench__bar">
        <div>
          <p class="finetune-workbench__eyebrow">Embedded Console</p>
          <h2>训练控制台</h2>
        </div>
        <div class="finetune-workbench__guard">
          <ShieldCheck :size="15" />
          <span>服务建议绑定 127.0.0.1，仅通过主系统入口访问</span>
        </div>
      </div>

      <div class="finetune-workbench__frame">
        <iframe
          :key="iframeVersion"
          :src="iframeSrc"
          title="模型微调工作台"
          loading="eager"
          referrerpolicy="no-referrer"
        />
      </div>
    </section>
  </section>
</template>

<style scoped>
.finetune-page {
  display: grid;
  gap: 20px;
  align-content: start;
  padding-bottom: 14px;
  max-width: 100%;
  overflow-x: hidden;
  position: relative;
}

.finetune-page::before {
  content: "";
  position: absolute;
  inset: -18px -18px auto -18px;
  height: 260px;
  pointer-events: none;
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(6, 182, 212, 0.10) 45%, rgba(16, 185, 129, 0.08) 100%),
    linear-gradient(90deg, rgba(37, 99, 235, 0.055) 1px, transparent 1px),
    linear-gradient(180deg, rgba(20, 184, 166, 0.05) 1px, transparent 1px);
  background-size: auto, 42px 42px, 42px 42px;
  z-index: 0;
}

.finetune-page > * {
  position: relative;
  z-index: 1;
}

.finetune-btn {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 18px;
  border-radius: 14px;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, background 180ms ease;
}

.finetune-btn:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 2px;
}

.finetune-btn--ghost {
  border: 2px solid rgba(14, 165, 233, 0.24);
  background: rgba(255, 255, 255, 0.86);
  color: #0f766e;
}

.finetune-btn--ghost:hover {
  border-color: #14b8a6;
  color: #0f172a;
  background: #ecfdf5;
  transform: translateY(-1px);
}

.finetune-btn--primary {
  border: 0;
  background: linear-gradient(135deg, #2563eb 0%, #0891b2 55%, #14b8a6 100%);
  color: #ffffff;
  box-shadow: 0 8px 20px rgba(6, 182, 212, 0.28), 0 2px 8px rgba(37, 99, 235, 0.18);
}

.finetune-btn--primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(6, 182, 212, 0.34), 0 4px 12px rgba(37, 99, 235, 0.22);
}

.finetune-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.finetune-status-card {
  --card-accent: #2563eb;
  --card-accent-soft: rgba(37, 99, 235, 0.14);
  min-width: 0;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(14, 165, 233, 0.18);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(240, 253, 250, 0.82) 100%);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06), 0 4px 16px rgba(6, 182, 212, 0.06);
  backdrop-filter: blur(16px);
  position: relative;
  overflow: hidden;
}

.finetune-status-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, var(--card-accent) 0%, rgba(255, 255, 255, 0) 100%);
}

.finetune-status-card:nth-child(2) {
  --card-accent: #06b6d4;
  --card-accent-soft: rgba(6, 182, 212, 0.16);
}

.finetune-status-card:nth-child(3) {
  --card-accent: #10b981;
  --card-accent-soft: rgba(16, 185, 129, 0.16);
}

.finetune-status-card:nth-child(4) {
  --card-accent: #f59e0b;
  --card-accent-soft: rgba(245, 158, 11, 0.14);
}

.finetune-status-card__icon {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.82) 0%, var(--card-accent-soft) 100%);
  color: var(--card-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.finetune-status-card__copy {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.finetune-status-card__copy span {
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 700;
}

.finetune-status-card__copy strong {
  color: #0f172a;
  font-size: 1rem;
  line-height: 1.35;
}

.finetune-status-card__copy small {
  color: #64748b;
  font-size: 0.8rem;
  line-height: 1.45;
  word-break: break-word;
}

.finetune-workbench {
  min-width: 0;
  display: grid;
  gap: 0;
  border-radius: 24px;
  border: 1px solid rgba(14, 165, 233, 0.22);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 253, 255, 0.92) 100%);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.10), 0 10px 24px rgba(6, 182, 212, 0.08);
  overflow: hidden;
  backdrop-filter: blur(18px);
}

.finetune-workbench__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(125, 211, 252, 0.24);
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.97) 0%, rgba(30, 64, 175, 0.92) 54%, rgba(13, 148, 136, 0.90) 100%),
    #0f172a;
}

.finetune-workbench__bar h2,
.finetune-workbench__eyebrow {
  margin: 0;
}

.finetune-workbench__bar h2 {
  margin-top: 4px;
  color: #ffffff;
  font-size: 1.08rem;
  font-weight: 800;
}

.finetune-workbench__eyebrow {
  color: #7dd3fc;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.finetune-workbench__guard {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(125, 211, 252, 0.32);
  background: rgba(240, 253, 250, 0.10);
  color: #ccfbf1;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
}

.finetune-workbench__frame {
  min-height: calc(100vh - 330px);
  height: clamp(960px, 92vh, 1380px);
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.06) 0%, rgba(6, 182, 212, 0.08) 44%, rgba(16, 185, 129, 0.06) 100%),
    #eef7fb;
}

.finetune-workbench__frame iframe {
  width: 100%;
  height: 100%;
  display: block;
  border: 0;
  background: #eef7fb;
}

@media (max-width: 1180px) {
  .finetune-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .finetune-status-grid {
    grid-template-columns: 1fr;
  }

  .finetune-workbench__bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .finetune-workbench__guard {
    white-space: normal;
  }

  .finetune-workbench__frame {
    height: 860px;
  }
}
</style>
