<script setup lang="ts">
import { Bot, ChevronDown, RefreshCw, SendHorizontal, Sparkles, Square } from "lucide-vue-next";
import { computed, ref, toRef, watch } from "vue";
import type { CommunityWorkflow, SessionUser } from "../api/client";
import AgentMarkdownContent from "../components/agent/AgentMarkdownContent.vue";
import AgentReportDocument from "../components/agent/AgentReportDocument.vue";
import AgentTracePanel from "../components/agent/AgentTracePanel.vue";
import CommunityAgentAttachmentRenderer from "../components/agent/CommunityAgentAttachmentRenderer.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCommunityAgentWorkbench } from "../composables/useCommunityAgentWorkbench";
import { useCommunityWorkspace } from "../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
  refreshKey?: number;
}>();

const workspace = useCommunityWorkspace(toRef(props, "sessionUser"), { mode: "dashboard" });
const workbench = useCommunityAgentWorkbench(
  () => workspace.deviceStatuses.value.map((item) => item.device_mac),
  () => workspace.selectedDeviceMac.value,
);

watch(
  () => props.refreshKey,
  (key, prev) => {
    if (key == null || prev == null) return;
    workbench.clearConversationState();
    void workbench.loadContext();
  },
);

const headerBadges = computed(() => [
  workbench.selectedSubjectLabel.value,
  workbench.selectedWindow.value === "week" ? "过去一周" : "过去一天",
  `模型 ${workbench.selectedProvider.value}`,
]);

const sampleStatusText = computed(() => {
  const status = workbench.demoDataStatus.value;
  if (status?.enabled && status.subject_count) {
    return `社区样本已就绪 ${status.subject_count} 位对象`;
  }
  return "社区样本等待刷新";
});

const quickSuggestions = computed(() => workbench.quickActions.value.slice(0, 4));
const workflowOptions = computed(() => workbench.quickActions.value);
const selectedWorkflow = ref<CommunityWorkflow>("free_chat");

const subjectSelectionValue = computed(() => {
  if (workbench.selectedScope.value === "community") return "community";
  return workbench.selectedElderId.value ? `elder:${workbench.selectedElderId.value}` : "elder:";
});

const selectedWorkflowPrompt = computed(
  () => workflowOptions.value.find((item) => item.workflow === selectedWorkflow.value)?.prompt ?? "",
);

watch(
  workflowOptions,
  (actions) => {
    if (!actions.length) {
      selectedWorkflow.value = "free_chat";
      return;
    }
    if (!actions.some((item) => item.workflow === selectedWorkflow.value)) {
      selectedWorkflow.value = actions[0].workflow;
    }
  },
  { immediate: true },
);

function updateSubjectSelection(value: string) {
  if (value === "community") {
    workbench.selectedScope.value = "community";
    return;
  }
  if (value.startsWith("elder:")) {
    workbench.selectedScope.value = "elder";
    workbench.selectedElderId.value = value.slice("elder:".length);
  }
}

function submitSuggestedWorkflow(workflow: CommunityWorkflow, prompt: string) {
  void workbench.submit(workflow, prompt);
}

function submitSelectedWorkflow() {
  const presetQuestion = workbench.question.value.trim() ? undefined : selectedWorkflowPrompt.value;
  void workbench.submit(selectedWorkflow.value, presetQuestion);
}

function isReportWorkflow(workflow: CommunityWorkflow) {
  return workflow === "community_report" || workflow === "elder_report" || workflow === "report_generation";
}
</script>

<template>
  <section class="agent-page">
    <PageHeader
      eyebrow="社区智能体"
      title="社区智能体工作台"
      description="围绕单个老人或整个社区，发起分析、整理图表与报告，并给出行动建议。"
    />

    <section class="agent-shell agent-shell--unified">
      <div class="agent-controls">
        <div class="agent-filter-bar">
          <label class="agent-filter-field">
            <span class="agent-filter-field__label">分析对象</span>
            <div class="agent-filter-field__control">
              <select
                :value="subjectSelectionValue"
                @change="updateSubjectSelection(($event.target as HTMLSelectElement).value)"
              >
                <option value="community">整个社区</option>
                <option
                  v-for="subject in workbench.elderSubjects.value"
                  :key="subject.elder_id"
                  :value="`elder:${subject.elder_id}`"
                >
                  {{ subject.elder_name }} / {{ subject.apartment }}
                </option>
              </select>
              <ChevronDown :size="16" />
            </div>
          </label>

          <label class="agent-filter-field">
            <span class="agent-filter-field__label">时间范围</span>
            <div class="agent-filter-field__control">
              <select v-model="workbench.selectedWindow.value">
                <option value="day">过去一天</option>
                <option value="week">过去一周</option>
              </select>
              <ChevronDown :size="16" />
            </div>
          </label>

          <label class="agent-filter-field">
            <span class="agent-filter-field__label">智能体能力</span>
            <div class="agent-filter-field__control">
              <select v-model="selectedWorkflow">
                <option v-for="action in workflowOptions" :key="action.workflow" :value="action.workflow">
                  {{ action.label }}
                </option>
              </select>
              <ChevronDown :size="16" />
            </div>
          </label>

          <label class="agent-filter-field">
            <span class="agent-filter-field__label">分析模型</span>
            <div class="agent-filter-field__control">
              <select v-model="workbench.selectedProvider.value">
                <option value="auto">自动选择</option>
                <option value="tongyi">Tongyi</option>
                <option value="ollama">Ollama</option>
              </select>
              <ChevronDown :size="16" />
            </div>
          </label>

          <button
            type="button"
            class="ghost-btn agent-refresh-btn"
            :disabled="workbench.refreshingSamples.value"
            @click="workbench.refreshCommunitySamples"
          >
            <RefreshCw :size="15" />
            {{ workbench.refreshingSamples.value ? "刷新中..." : "刷新社区样本" }}
          </button>
        </div>
      </div>

      <div class="agent-chat-surface">
        <div class="agent-chat-surface__head">
          <div class="agent-badge-row">
            <span v-for="badge in headerBadges" :key="badge" class="summary-badge">{{ badge }}</span>
          </div>
          <span class="agent-sample-status">{{ sampleStatusText }}</span>
        </div>

        <p v-if="workbench.errorText.value" class="feedback-banner feedback-error">
          {{ workbench.errorText.value }}
        </p>

        <div class="agent-message-list">
          <div v-if="!workbench.messages.value.length" class="agent-empty-state">
            <div class="agent-empty-state__icon">
              <Sparkles :size="20" />
            </div>
            <h2>从一个明确能力开始，让智能体直接进入分析</h2>
            <p>上方下拉栏用于固定分析对象、时间范围、智能体能力和模型来源，避免来回切换按钮。</p>
            <div class="agent-empty-state__actions">
              <button
                v-for="action in quickSuggestions"
                :key="action.workflow"
                type="button"
                class="agent-quick-pill"
                @click="submitSuggestedWorkflow(action.workflow, action.prompt)"
              >
                <Sparkles :size="14" />
                {{ action.label }}
              </button>
            </div>
          </div>

          <article
            v-for="message in workbench.messages.value"
            :key="message.id"
            class="agent-message"
            :class="`agent-message--${message.role}`"
          >
            <div class="agent-message__meta">
              <div class="agent-message__author">
                <span class="agent-message__avatar">
                  <Bot v-if="message.role === 'assistant'" :size="16" />
                  <span v-else>我</span>
                </span>
                <strong>{{ message.role === "assistant" ? "社区智能体" : "我" }}</strong>
              </div>
              <span>{{ workbench.workflowLabel(message.workflow) }}</span>
            </div>

            <AgentTracePanel
              v-if="message.role === 'assistant' && message.trace"
              :stages="message.trace.stages"
              :tools="message.trace.tools"
              :citations="message.trace.citations"
              :selected-model="message.trace.selectedModel"
              :degraded-notes="message.trace.degradedNotes"
              :streaming="message.status === 'streaming'"
            />

            <CommunityAgentAttachmentRenderer
              v-if="message.role === 'assistant' && message.attachments.length"
              :attachments="message.attachments"
            />

            <div
              v-if="message.role === 'user' || message.text || message.status !== 'completed'"
              class="agent-message__bubble"
              :class="{ 'agent-message__bubble--report': message.role === 'assistant' && isReportWorkflow(message.workflow) }"
              :data-role="message.role"
              :data-status="message.status"
            >
              <AgentReportDocument
                v-if="message.role === 'assistant' && message.text && isReportWorkflow(message.workflow)"
                :content="message.text"
              />
              <AgentMarkdownContent
                v-else-if="message.role === 'assistant' && message.text"
                :content="message.text"
                variant="bubble"
                :streaming="message.status === 'streaming'"
              />
              <p v-else>{{ message.text || (message.role === "assistant" ? "正在整理结果..." : "") }}</p>
            </div>
          </article>
        </div>
      </div>

      <footer class="agent-composer">
        <label class="agent-composer__field">
          <textarea
            v-model="workbench.question.value"
            rows="3"
            :placeholder="
              workbench.selectedScope.value === 'elder'
                ? '例如：请分析这位老人过去一周的风险变化、异常原因和建议动作。'
                : '例如：请总结社区过去一天的高风险对象、告警热点和排班建议。'
            "
          />
        </label>

        <div class="agent-composer__footer">
          <div class="agent-composer__actions">
            <button
              type="button"
              class="agent-stop-btn"
              :class="{ 'agent-stop-btn--active': workbench.running.value }"
              :disabled="!workbench.running.value"
              @click="workbench.cancel"
            >
              <Square :size="15" />
              停止
            </button>
            <button
              type="button"
              class="agent-start-btn"
              :class="{ 'agent-start-btn--running': workbench.running.value }"
              :disabled="workbench.running.value || !workbench.canAnalyze.value"
              @click="submitSelectedWorkflow"
            >
              <SendHorizontal :size="16" />
              {{ workbench.running.value ? "分析中..." : "开始分析" }}
            </button>
          </div>
        </div>
      </footer>
    </section>
  </section>
</template>

<style scoped>
.agent-page,
.agent-shell,
.agent-chat-surface,
.agent-message-list {
  display: grid;
  gap: 24px;
}

.agent-page {
  align-content: start;
  padding-bottom: 12px;
  max-width: 100%;
  overflow-x: hidden;
}

.agent-shell {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  padding: 32px;
  border-radius: 24px;
  background: #ffffff;
  border: 2px solid #e2e8f0;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.agent-shell--unified {
  gap: 18px;
}

.agent-controls {
  position: sticky;
  top: 16px;
  z-index: 6;
}

.agent-filter-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 14px;
  align-items: end;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid #dbe4f0;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(14px);
}

.agent-filter-field {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.agent-filter-field__label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.02em;
}

.agent-filter-field__control {
  position: relative;
  display: flex;
  align-items: center;
}

.agent-filter-field__control select {
  width: 100%;
  min-height: 54px;
  padding: 0 46px 0 16px;
  border-radius: 16px;
  border: 2px solid #d7dfeb;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  color: #0f172a;
  font: inherit;
  font-size: 0.94rem;
  font-weight: 600;
  appearance: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.agent-filter-field__control select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.agent-filter-field__control svg {
  position: absolute;
  right: 16px;
  color: #64748b;
  pointer-events: none;
}

.ghost-btn {
  padding: 12px 20px;
  border-radius: 16px;
  border: 2px solid #cbd5e1;
  background: #ffffff;
  color: #475569;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 200ms ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ghost-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  color: #1e40af;
  background: #eff6ff;
  transform: translateY(-1px);
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.agent-refresh-btn {
  align-self: end;
  min-height: 54px;
}

.agent-chat-surface {
  padding: 6px 4px 0;
  min-height: clamp(320px, 44vh, 520px);
  display: grid;
  gap: 20px;
}

.agent-chat-surface__head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 2px solid #e2e8f0;
}

.agent-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.summary-badge {
  padding: 10px 18px;
  border-radius: 999px;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1e40af;
  font-size: 0.85rem;
  font-weight: 700;
  border: 2px solid #3b82f6;
  white-space: nowrap;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.15);
}

.agent-sample-status {
  color: #64748b;
  font-size: 0.9rem;
  font-weight: 500;
}

.feedback-banner {
  padding: 18px 24px;
  border-radius: 16px;
  font-size: 0.95rem;
  margin: 0;
}

.feedback-error {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #991b1b;
  border: 2px solid #fca5a5;
}

.agent-empty-state {
  min-height: clamp(260px, 34vh, 320px);
  display: grid;
  place-content: start center;
  gap: 16px;
  text-align: center;
  padding: 16px 20px 4px;
}

.agent-empty-state__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.agent-empty-state__icon {
  width: 72px;
  height: 72px;
  margin: 0 auto;
  border-radius: 20px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #1e40af;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.agent-empty-state h2 {
  margin: 0;
  color: #0f172a;
  font-size: clamp(1.5rem, 2.1vw, 2rem);
  font-weight: 700;
}

.agent-empty-state p {
  margin: 0;
  color: #64748b;
  max-width: 600px;
  line-height: 1.8;
  font-size: 1rem;
}

.agent-message {
  display: grid;
  gap: 16px;
  max-width: 100%;
}

.agent-message--user {
  justify-self: end;
}

.agent-message__meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  color: #64748b;
  font-size: 0.9rem;
  font-weight: 500;
}

.agent-message__author {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agent-message__author strong {
  color: #0f172a;
  font-weight: 700;
}

.agent-message__avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  color: #475569;
  font-size: 0.85rem;
  font-weight: 700;
  border: 2px solid #cbd5e1;
}

.agent-message__bubble {
  padding: 24px 28px;
  border-radius: 20px;
  border: 2px solid #e2e8f0;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.agent-message__bubble[data-role="assistant"] {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
}

.agent-message__bubble[data-role="assistant"][data-status="streaming"] {
  border-color: #3b82f6;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
}

.agent-message__bubble[data-role="user"] {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #1e40af;
  border-color: #3b82f6;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
}

.agent-message__bubble--report {
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent !important;
  box-shadow: none;
}

.agent-message__bubble p {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 1rem;
}

.agent-composer {
  display: grid;
  gap: 12px;
  padding-top: 18px;
  border-top: 1px solid #e2e8f0;
}

.agent-quick-pill {
  border: 2px solid #cbd5e1;
  border-radius: 999px;
  padding: 10px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  color: #64748b;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 200ms ease;
  font-weight: 600;
  font-size: 0.85rem;
}

.agent-quick-pill:hover {
  transform: translateY(-1px);
  border-color: #3b82f6;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #1e40af;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.agent-composer__field textarea {
  width: 100%;
  min-height: 120px;
  max-height: min(32vh, 300px);
  resize: vertical;
  border-radius: 16px;
  border: 2px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  padding: 16px 20px;
  font: inherit;
  line-height: 1.7;
  font-size: 0.95rem;
  box-shadow: inset 0 2px 8px rgba(15, 23, 42, 0.04);
  transition: all 200ms ease;
}

.agent-composer__field textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1), inset 0 2px 8px rgba(15, 23, 42, 0.04);
}

.agent-composer__footer {
  display: flex;
  justify-content: flex-end;
  gap: 20px;
  align-items: center;
}

.agent-composer__actions {
  display: flex;
  gap: 12px;
}

.agent-stop-btn {
  min-width: 110px;
  height: 52px;
  border: 2px solid #e2e8f0;
  border-radius: 16px;
  padding: 0 24px;
  background: #ffffff;
  color: #64748b;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: all 200ms ease;
  font-size: 0.95rem;
}

.agent-stop-btn:hover:not(:disabled) {
  border-color: #f87171;
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #dc2626;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(248, 113, 113, 0.25);
}

.agent-stop-btn--active {
  border-color: #f87171;
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #dc2626;
  animation: pulse-stop 2s infinite;
}

.agent-stop-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.agent-start-btn {
  min-width: 160px;
  height: 52px;
  border: none;
  border-radius: 16px;
  padding: 0 28px;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  color: #ffffff;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: all 200ms ease;
  font-size: 0.95rem;
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.35);
}

.agent-start-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.45);
}

.agent-start-btn--running {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  animation: pulse-running 2s infinite;
}

.agent-start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

@keyframes pulse-stop {
  0%,
  100% {
    box-shadow: 0 6px 16px rgba(248, 113, 113, 0.25);
  }
  50% {
    box-shadow: 0 8px 24px rgba(248, 113, 113, 0.4);
  }
}

@keyframes pulse-running {
  0%,
  100% {
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.35);
  }
  50% {
    box-shadow: 0 8px 24px rgba(16, 185, 129, 0.5);
  }
}

@media (max-width: 980px) {
  .agent-shell {
    padding: 24px;
  }

  .agent-controls {
    position: static;
  }

  .agent-filter-bar {
    grid-template-columns: 1fr;
  }

  .agent-chat-surface__head,
  .agent-composer__footer {
    flex-direction: column;
    align-items: stretch;
  }

  .agent-message {
    max-width: 100%;
  }

  .agent-message--user {
    justify-self: stretch;
  }

  .agent-composer__actions {
    width: 100%;
    justify-content: stretch;
  }

  .agent-stop-btn,
  .agent-start-btn {
    flex: 1;
  }
}
</style>
