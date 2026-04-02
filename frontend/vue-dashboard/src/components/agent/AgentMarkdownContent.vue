<script setup lang="ts">
import { ref, watch } from "vue";
import { renderMarkdown } from "../../utils/markdown";

const props = withDefaults(
  defineProps<{
    content: string;
    variant?: "bubble" | "report";
    streaming?: boolean;
  }>(),
  {
    variant: "report",
    streaming: false,
  },
);

const renderedHtml = ref("");

let timer: ReturnType<typeof setTimeout> | null = null;
const DEBOUNCE_MS = 60;

function updateRenderedHtml() {
  const streaming = props.streaming || props.variant === "report";
  renderedHtml.value = renderMarkdown(props.content, { streaming });
}

watch(
  () => [props.variant, props.streaming],
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
  line-height: 1.75;
  overflow-x: auto;
  overflow-wrap: anywhere;
}

.agent-markdown--bubble {
  font-size: 0.95rem;
}

.agent-markdown--report {
  font-size: 1.02rem;
  line-height: 1.85;
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
  margin: 1.5em 0 0.6em;
  color: #1e293b;
  line-height: 1.35;
  letter-spacing: -0.01em;
  font-weight: 700;
}

.agent-markdown :deep(h1) {
  font-size: 1.45rem;
  padding-bottom: 0.4em;
  border-bottom: 1px solid #e2e8f0;
}

.agent-markdown :deep(h2) {
  font-size: 1.25rem;
}

.agent-markdown :deep(h3) {
  font-size: 1.15rem;
}

.agent-markdown :deep(h4) {
  font-size: 1.05rem;
}

.agent-markdown :deep(p),
.agent-markdown :deep(ul),
.agent-markdown :deep(ol),
.agent-markdown :deep(blockquote),
.agent-markdown :deep(pre),
.agent-markdown :deep(table),
.agent-markdown :deep(hr) {
  margin: 1em 0;
}

.agent-markdown :deep(ul),
.agent-markdown :deep(ol) {
  padding-left: 1.5rem;
}

.agent-markdown :deep(li + li) {
  margin-top: 0.4rem;
}

.agent-markdown :deep(li::marker) {
  color: #64748b;
}

.agent-markdown :deep(blockquote) {
  margin-left: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--brand, #3b82f6);
  border-radius: 4px 12px 12px 4px;
  background: #f8fafc;
  color: #475569;
  font-style: normal;
}

.agent-markdown :deep(code) {
  padding: 0.2rem 0.4rem;
  border-radius: 0.375rem;
  background: #f1f5f9;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.9em;
}

.agent-markdown :deep(pre) {
  padding: 1rem;
  border-radius: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  overflow-x: auto;
}

.agent-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  border: none;
  font-size: 0.9em;
}

.agent-markdown :deep(table) {
  width: 100%;
  margin: 1.25rem 0;
  border-collapse: separate;
  border-spacing: 0;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  font-size: 0.95rem;
  table-layout: auto;
}

.agent-markdown :deep(thead) {
  background: #f8fafc;
}

.agent-markdown :deep(thead th) {
  color: #334155;
  font-weight: 600;
  text-align: left;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.agent-markdown :deep(td) {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  color: #475569;
  vertical-align: top;
  line-height: 1.6;
}

.agent-markdown :deep(tr:nth-child(even) td) {
  background: #fcfcfc;
}

.agent-markdown :deep(tr:hover td) {
  background: #f1f5f9;
}

.agent-markdown :deep(tr:last-child td) {
  border-bottom: 0;
}

.agent-markdown :deep(hr) {
  border: 0;
  border-top: 1px solid #e2e8f0;
  margin: 2rem 0;
}

.agent-markdown :deep(a) {
  color: #0f766e;
  text-decoration: none;
  font-weight: 500;
}

.agent-markdown :deep(a:hover) {
  text-decoration: underline;
}
</style>
