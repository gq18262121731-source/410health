<script setup lang="ts">
import { Bot, RefreshCw, SendHorizontal, Sparkles, Square } from "lucide-vue-next";
import { computed, toRef, watch } from "vue";
import type { SessionUser } from "../api/client";
import AgentMarkdownContent from "../components/agent/AgentMarkdownContent.vue";
import AgentTracePanel from "../components/agent/AgentTracePanel.vue";
import CommunityAgentAttachmentRenderer from "../components/agent/CommunityAgentAttachmentRenderer.vue";
import { useCommunityAgentWorkbench } from "../composables/useCommunityAgentWorkbench";
import { useCommunityWorkspace } from "../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
  /**
   * Trigger refresh behavior when user re-clicks the nav entry,
   * even if the route/hash doesn't change.
   */
  refreshKey?: number;
}>();

const workspace = useCommunityWorkspace(toRef(props, "sessionUser"));
const workbench = useCommunityAgentWorkbench(
  () => workspace.deviceStatuses.value.map((item) => item.device_mac),
  () => workspace.selectedDeviceMac.value,
);

watch(
  () => props.refreshKey,
  (key, prev) => {
    if (key == null) return;
    // Ignore the first run after mount; this page already initializes a clean state.
    if (prev == null) return;
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
  if (workbench.demoDataStatus.value?.enabled && workbench.demoDataStatus.value.subject_count) {
    return `社区样本已准备 ${workbench.demoDataStatus.value.subject_count} 位对象`;
  }
  return "社区样本等待刷新";
});

const quickSuggestions = computed(() => workbench.quickActions.value.slice(0, 4));

function submitFreeChat() {
  void workbench.submit("free_chat");
}
</script>

<template>
  <section class="agent-page">
    <header class="agent-header">
      <div class="agent-header__copy">
        <span class="eyebrow">社区智能体</span>
        <h1>社区智能体工作台</h1>
        <p>围绕单个老人或整个社区，直接发起真实分析、图表整理、报告生成和综合建议。</p>
      </div>
    </header>

    <section class="agent-shell">
      <div class="agent-controls">
          <div class="agent-toggle-group">
            <button
              type="button"
              class="agent-toggle"
              :class="{ 'agent-toggle--active': workbench.selectedScope.value === 'elder' }"
              @click="workbench.selectedScope.value = 'elder'"
            >
              某位老人
            </button>
            <button
              type="button"
              class="agent-toggle"
              :class="{ 'agent-toggle--active': workbench.selectedScope.value === 'community' }"
              @click="workbench.selectedScope.value = 'community'"
            >
              整个社区
            </button>
          </div>

          <div class="agent-toggle-group">
            <button
              type="button"
              class="agent-toggle"
              :class="{ 'agent-toggle--active': workbench.selectedWindow.value === 'day' }"
              @click="workbench.selectedWindow.value = 'day'"
            >
              过去一天
            </button>
            <button
              type="button"
              class="agent-toggle"
              :class="{ 'agent-toggle--active': workbench.selectedWindow.value === 'week' }"
              @click="workbench.selectedWindow.value = 'week'"
            >
              过去一周
            </button>
          </div>

          <label v-if="workbench.selectedScope.value === 'elder'" class="agent-select agent-select--wide">
            <span>分析对象</span>
            <select v-model="workbench.selectedElderId.value">
              <option
                v-for="subject in workbench.elderSubjects.value"
                :key="subject.elder_id"
                :value="subject.elder_id"
              >
                {{ subject.elder_name }} / {{ subject.apartment }}
              </option>
            </select>
          </label>

          <label class="agent-select">
            <span>分析模型</span>
            <select v-model="workbench.selectedProvider.value">
              <option value="auto">自动</option>
              <option value="tongyi">Tongyi</option>
              <option value="ollama">Ollama</option>
            </select>
          </label>

          <button
            type="button"
            class="ghost-btn"
            :disabled="workbench.refreshingSamples.value"
            @click="workbench.refreshCommunitySamples"
          >
            <RefreshCw :size="15" />
            {{ workbench.refreshingSamples.value ? "刷新中..." : "刷新社区样本" }}
          </button>
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
            <h2>像真正的大模型一样，直接发起一次分析</h2>
            <p>选好分析对象和时间窗口后输入问题。执行过程、工具调用、图表和报告都会在同一条回答里展开。</p>
            <div class="agent-empty-state__actions">
              <button
                v-for="action in quickSuggestions"
                :key="action.workflow"
                type="button"
                class="agent-suggestion-chip"
                @click="workbench.submit(action.workflow, action.prompt)"
              >
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
              :data-role="message.role"
              :data-status="message.status"
            >
              <AgentMarkdownContent
                v-if="message.role === 'assistant' && message.text"
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
        <div class="agent-composer__quick">
          <button
            v-for="action in quickSuggestions"
            :key="action.workflow"
            type="button"
            class="agent-quick-pill"
            @click="workbench.submit(action.workflow, action.prompt)"
          >
            <Sparkles :size="14" />
            {{ action.label }}
          </button>
        </div>

        <label class="agent-composer__field">
          <textarea
            v-model="workbench.question.value"
            rows="5"
            :placeholder="
              workbench.selectedScope.value === 'elder'
                ? '例如：请分析这位老人过去一周的风险变化、异常原因和建议动作。'
                : '例如：请总结社区过去一天的高风险对象、告警热点和排班建议。'
            "
          />
        </label>

        <div class="agent-composer__footer">
          <div class="agent-badge-row">
            <span v-for="badge in headerBadges" :key="`footer-${badge}`" class="summary-badge">{{ badge }}</span>
          </div>

          <div class="agent-composer__actions">
            <button type="button" class="ghost-btn" :disabled="!workbench.running.value" @click="workbench.cancel">
              <Square :size="15" />
              停止
            </button>
            <button
              type="button"
              class="primary-btn agent-send-btn"
              :disabled="workbench.running.value || !workbench.canAnalyze.value"
              @click="submitFreeChat"
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
  gap: 18px;
}

.agent-page {
  min-height: calc(100vh - 48px);
  align-content: start;
}

.agent-header__copy {
  max-width: 720px;
  display: grid;
  gap: 10px;
}

.agent-header__copy h1 {
  margin: 0;
  font-size: clamp(2rem, 3.2vw, 3.4rem);
  line-height: 0.98;
  color: var(--text-main);
  letter-spacing: -0.04em;
}

.agent-header__copy p {
  margin: 0;
  max-width: 640px;
  color: var(--text-sub);
  line-height: 1.8;
}

.agent-shell {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  padding: 22px;
  border-radius: 34px;
  background: #ffffff;
  border: 1px solid var(--line-medium);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
}

.agent-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
  max-height: 80vh;
  overflow-y: auto;
  padding-right: 8px;
}

.agent-sidebar::-webkit-scrollbar {
  width: 6px;
}

.agent-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.agent-sidebar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 3px;
}

.agent-sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.agent-controls,
.agent-toggle-group,
.agent-badge-row,
.agent-empty-state__actions,
.agent-composer__quick,
.agent-composer__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.agent-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
  max-height: 80vh;
  overflow-y: auto;
  padding-right: 8px;
}

.agent-sidebar::-webkit-scrollbar {
  width: 6px;
}

.agent-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.agent-sidebar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 3px;
}

.agent-sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.agent-controls {
  flex-direction: column;
  align-items: stretch;
}

.agent-toggle-group {
  border-radius: 999px;
  padding: 4px;
  background: #f1f5f9;
}

.agent-toggle {
  border: 0;
  min-width: 108px;
  border-radius: 999px;
  padding: 12px 18px;
  background: transparent;
  color: var(--text-sub);
  font-weight: 700;
  cursor: pointer;
  transition: all 180ms ease;
}

.agent-toggle--active {
  background: #ffffff;
  color: var(--brand);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.agent-select {
  min-width: 170px;
  display: grid;
  gap: 8px;
}

.agent-select--wide {
  min-width: min(360px, 100%);
}

.agent-select span {
  color: var(--text-sub);
  font-size: 0.82rem;
}

.agent-select select {
  width: 100%;
  min-height: 48px;
  padding: 0 14px;
  border-radius: 16px;
  border: 1px solid var(--line-medium);
  background: #ffffff;
  color: var(--text-main);
}

.agent-chat-surface {
  padding: 8px 2px 0;
  min-height: 48vh;
  display: grid;
  gap: 18px;
}

.agent-chat-surface__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding-bottom: 8px;
}

.agent-sample-status {
  color: var(--text-sub);
  font-size: 0.88rem;
}

.agent-message-list {
  padding-top: 6px;
}

.agent-empty-state {
  min-height: 360px;
  display: grid;
  place-content: center;
  gap: 14px;
  text-align: center;
}

.agent-empty-state__icon {
  width: 56px;
  height: 56px;
  margin: 0 auto;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.agent-empty-state h2 {
  margin: 0;
  color: var(--text-main);
  font-size: clamp(1.5rem, 2.1vw, 2rem);
}

.agent-empty-state p {
  margin: 0;
  color: var(--text-sub);
  max-width: 560px;
  line-height: 1.8;
}

.agent-message {
  display: grid;
  gap: 12px;
  max-width: 100%;
}

.agent-message--user {
  justify-self: end;
}

.agent-message__meta {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
  color: var(--text-sub);
  font-size: 0.92rem;
}

.agent-message__author {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-message__avatar {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: #f1f5f9;
  color: var(--text-main);
  font-size: 0.85rem;
}

.agent-message__bubble {
  padding: 18px 20px;
  border-radius: 26px;
  border: 1px solid var(--line-medium);
}

.agent-message__bubble[data-role="assistant"] {
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.agent-message__bubble[data-role="assistant"][data-status="streaming"] {
  border-color: var(--brand);
}

.agent-message__bubble[data-role="user"] {
  background: #eff6ff;
  color: var(--text-main);
  border-color: rgba(37, 99, 235, 0.15);
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.06);
}

.agent-message__bubble p {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.85;
  font-size: 1.15rem;
}

.agent-composer {
  position: sticky;
  bottom: 12px;
  display: grid;
  gap: 14px;
  padding: 18px;
  margin-top: 8px;
  border-radius: 28px;
  border: 1px solid var(--line-medium);
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(16px);
}

.agent-quick-pill,
.agent-suggestion-chip {
  border: 1px solid var(--line-medium);
  border-radius: 999px;
  padding: 10px 14px;
  background: #f8fafc;
  color: var(--text-sub);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.agent-quick-pill:hover,
.agent-suggestion-chip:hover {
  transform: translateY(-1px);
  border-color: var(--brand);
  background: #eff6ff;
  color: var(--brand);
}

.agent-composer__field textarea {
  width: 100%;
  min-height: 168px;
  resize: vertical;
  border-radius: 28px;
  border: 1px solid var(--line-medium);
  background: #ffffff;
  color: var(--text-main);
  padding: 22px 24px;
  font: inherit;
  line-height: 1.8;
  box-shadow: inset 0 2px 8px rgba(15, 23, 42, 0.03);
}

.agent-composer__footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.agent-send-btn {
  min-width: 148px;
}

@media (max-width: 980px) {
  .agent-shell {
    grid-template-columns: 1fr;
  }

  .agent-sidebar {
    max-height: none;
  }

  .agent-controls {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
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

  .agent-select,
  .agent-select--wide {
    min-width: 100%;
  }

  .agent-composer {
    position: static;
  }
}
</style>
