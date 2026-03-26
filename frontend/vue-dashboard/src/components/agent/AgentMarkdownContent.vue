<script setup lang="ts">
import { ref, watch } from "vue";
import { renderMarkdown } from "../../utils/markdown";

const props = withDefaults(
  defineProps<{
    content: string;
    variant?: "bubble" | "report";
  }>(),
  {
    variant: "report",
  },
);

const renderedHtml = ref("");

let timer: ReturnType<typeof setTimeout> | null = null;
const DEBOUNCE_MS = 60;

function updateRenderedHtml() {
  const streaming = props.variant === "report";
  renderedHtml.value = renderMarkdown(props.content, { streaming });
}

watch(
  () => props.variant,
  () => {
    // Variant 切换时立即更新一次，避免样式/渲染模式滞后。
    if (timer) clearTimeout(timer);
    updateRenderedHtml();
  },
);

watch(
  () => props.content,
  (value) => {
    const text = String(value ?? "");
    if (!text.trim()) {
      renderedHtml.value = "";
      return;
    }

    // 尽量保持“流式可见”，但避免每次更新都触发 markdown-it 全量重排。
    const shouldUpdateImmediately = renderedHtml.value === "" || text.length < 120;

    if (timer) clearTimeout(timer);
    if (shouldUpdateImmediately) updateRenderedHtml();
    else timer = setTimeout(() => updateRenderedHtml(), DEBOUNCE_MS);
  },
  { immediate: true },
);
</script>

<template>
  <div
    class="agent-markdown"
    :class="`agent-markdown--${variant}`"
    v-html="renderedHtml"
  />
</template>

<style scoped>
.agent-markdown {
  color: var(--text-main);
  line-height: 1.85;
  overflow-x: auto;
  overflow-wrap: anywhere;
}

.agent-markdown--bubble {
  font-size: 0.98rem;
}

.agent-markdown--report {
  font-size: 1.18rem;
  line-height: 2;
}

.agent-markdown :deep(*:first-child) {
  margin-top: 0;
}

.agent-markdown :deep(*:last-child) {
  margin-bottom: 0;
}

.agent-markdown :deep(h1),
.agent-markdown :deep(h2),
.agent-markdown :deep(h3),
.agent-markdown :deep(h4),
.agent-markdown :deep(h5),
.agent-markdown :deep(h6) {
  margin: 1.1em 0 0.45em;
  color: var(--text-main);
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.agent-markdown :deep(h1) {
  font-size: 1.46rem;
}

.agent-markdown :deep(h2) {
  font-size: 1.28rem;
}

.agent-markdown :deep(h3) {
  font-size: 1.12rem;
}

.agent-markdown :deep(p),
.agent-markdown :deep(ul),
.agent-markdown :deep(ol),
.agent-markdown :deep(blockquote),
.agent-markdown :deep(pre),
.agent-markdown :deep(table),
.agent-markdown :deep(hr) {
  margin: 1.2em 0;
}

.agent-markdown :deep(ul),
.agent-markdown :deep(ol) {
  padding-left: 1.8rem;
}

.agent-markdown :deep(li + li) {
  margin-top: 0.6rem;
}

.agent-markdown :deep(blockquote) {
  margin-left: 0;
  padding: 0.9rem 1rem;
  border-left: 3px solid rgba(34, 211, 238, 0.36);
  border-radius: 0 16px 16px 0;
  background: rgba(34, 211, 238, 0.06);
  color: var(--text-sub);
}

.agent-markdown :deep(code) {
  padding: 0.14rem 0.38rem;
  border-radius: 0.5rem;
  background: rgba(34, 211, 238, 0.10);
  color: #67e8f9;
  font-size: 0.92em;
}

.agent-markdown :deep(pre) {
  padding: 1rem;
  border-radius: 1rem;
  background: #060c18;
  color: #a5d8ff;
}

.agent-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.agent-markdown :deep(table) {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
  border-spacing: 0;
  background: rgba(12, 18, 32, 0.96);
  border: 1px solid rgba(56, 189, 248, 0.14);
  border-radius: 1rem;
  overflow: hidden;
}

.agent-markdown :deep(th),
.agent-markdown :deep(td) {
  padding: 0.82rem 0.9rem;
  border-bottom: 1px solid rgba(56, 189, 248, 0.10);
  border-right: 1px solid rgba(56, 189, 248, 0.08);
  text-align: left;
  vertical-align: top;
  white-space: normal;
}

.agent-markdown :deep(th:last-child),
.agent-markdown :deep(td:last-child) {
  border-right: 0;
}

.agent-markdown :deep(thead th) {
  background: rgba(34, 211, 238, 0.08);
  color: #22d3ee;
  font-weight: 700;
}

.agent-markdown :deep(tr:last-child td) {
  border-bottom: 0;
}

.agent-markdown :deep(hr) {
  border: 0;
  border-top: 1px solid rgba(148, 163, 184, 0.24);
}

.agent-markdown :deep(a) {
  color: #0f766e;
  text-decoration: none;
}

.agent-markdown :deep(a:hover) {
  text-decoration: underline;
}
</style>
