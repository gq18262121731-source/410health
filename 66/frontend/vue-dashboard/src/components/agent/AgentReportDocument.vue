<script setup lang="ts">
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { Download, FileText } from "lucide-vue-next";
import { computed, ref } from "vue";
import {
  extractReportMeta,
  renderReportHtml,
} from "../../utils/reportDocument";

const props = withDefaults(
  defineProps<{
    content: string;
    title?: string;
    summary?: string;
  }>(),
  {
    title: "",
    summary: "",
  },
);

const reportRef = ref<HTMLElement | null>(null);
const downloading = ref(false);

const meta = computed(() => extractReportMeta(props.content, props.title || "社区健康运营报告"));
const renderedHtml = computed(() => renderReportHtml(props.content));

function safeFilename(value: string) {
  return `${value || "社区健康运营报告"}.pdf`.replace(/[\\/:*?"<>|]+/g, "-");
}

async function downloadPdf() {
  if (!reportRef.value || downloading.value) return;

  downloading.value = true;
  try {
    const canvas = await html2canvas(reportRef.value, {
      backgroundColor: "#ffffff",
      scale: Math.min(window.devicePixelRatio || 1, 2),
      useCORS: true,
      ignoreElements: (element) => element.hasAttribute("data-pdf-ignore"),
    });

    const pdf = new jsPDF("p", "mm", "a4");
    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 10;
    const targetWidth = pageWidth - margin * 2;
    const targetHeight = (canvas.height * targetWidth) / canvas.width;
    const pageContentHeight = pageHeight - margin * 2;

    const pageCanvas = document.createElement("canvas");
    const pageContext = pageCanvas.getContext("2d");
    if (!pageContext) return;

    const sliceHeight = Math.floor((pageContentHeight * canvas.width) / targetWidth);
    pageCanvas.width = canvas.width;
    pageCanvas.height = sliceHeight;

    let sourceY = 0;
    let pageIndex = 0;

    while (sourceY < canvas.height) {
      const remainingHeight = canvas.height - sourceY;
      const currentSliceHeight = Math.min(sliceHeight, remainingHeight);
      pageCanvas.height = currentSliceHeight;
      pageContext.clearRect(0, 0, pageCanvas.width, pageCanvas.height);
      pageContext.drawImage(
        canvas,
        0,
        sourceY,
        canvas.width,
        currentSliceHeight,
        0,
        0,
        canvas.width,
        currentSliceHeight,
      );

      if (pageIndex > 0) pdf.addPage();
      const imageData = pageCanvas.toDataURL("image/jpeg", 0.96);
      const imageHeight = Math.min(pageContentHeight, (currentSliceHeight * targetWidth) / canvas.width);
      pdf.addImage(imageData, "JPEG", margin, margin, targetWidth, imageHeight);

      sourceY += currentSliceHeight;
      pageIndex += 1;
    }

    if (targetHeight <= pageContentHeight && pageIndex === 0) {
      pdf.addImage(canvas.toDataURL("image/jpeg", 0.96), "JPEG", margin, margin, targetWidth, targetHeight);
    }

    pdf.save(safeFilename(meta.value.title));
  } finally {
    downloading.value = false;
  }
}
</script>

<template>
  <section ref="reportRef" class="report-document">
    <header class="report-document__cover">
      <div class="report-document__title-block">
        <span class="report-document__eyebrow">
          <FileText :size="16" />
          交接班报告
        </span>
        <h3>{{ meta.title }}</h3>
      </div>

      <div class="report-document__actions" data-pdf-ignore>
        <button type="button" class="report-action report-action--primary" :disabled="downloading" @click="downloadPdf">
          <Download :size="16" />
          {{ downloading ? "生成中..." : "下载 PDF" }}
        </button>
      </div>
    </header>

    <dl class="report-document__meta">
      <div v-if="meta.generatedAt">
        <dt>生成时间</dt>
        <dd>{{ meta.generatedAt }}</dd>
      </div>
      <div v-if="meta.windowLabel">
        <dt>分析窗口</dt>
        <dd>{{ meta.windowLabel }}</dd>
      </div>
      <div>
        <dt>报告用途</dt>
        <dd>社区交接班与风险处置跟进</dd>
      </div>
    </dl>

    <article class="report-document__body" v-html="renderedHtml" />
  </section>
</template>

<style scoped>
.report-document {
  display: grid;
  gap: 22px;
  padding: clamp(22px, 3vw, 34px);
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.98) 180px),
    #ffffff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
}

.report-document__cover {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding-bottom: 18px;
  border-bottom: 1px solid #dbe4f0;
}

.report-document__title-block {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.report-document__eyebrow {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #1d4ed8;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.report-document h3 {
  margin: 0;
  color: #0f172a;
  font-size: clamp(1.5rem, 2vw, 2rem);
  line-height: 1.25;
  font-weight: 800;
}

.report-document__title-block p {
  max-width: 980px;
  margin: 0;
  color: #475569;
  line-height: 1.8;
  font-size: 1rem;
}

.report-document__actions {
  flex: 0 0 auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.report-action {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.24);
}

.report-action:hover:not(:disabled) {
  background: #1d4ed8;
}

.report-action:disabled {
  cursor: wait;
  opacity: 0.72;
}

.report-document__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.report-document__meta div {
  min-width: 0;
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid #dbe4f0;
  background: #f8fafc;
}

.report-document__meta dt {
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.report-document__meta dd {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.45;
}

.report-document__body {
  color: #0f172a;
  font-size: 1.04rem;
  line-height: 1.9;
}

.report-document__body :deep(*:first-child) {
  margin-top: 0;
}

.report-document__body :deep(*:last-child) {
  margin-bottom: 0;
}

.report-document__body :deep(h1) {
  display: none;
}

.report-document__body :deep(h2) {
  margin: 1.4rem 0 0.72rem;
  padding: 0 0 0.55rem;
  color: #0f172a;
  border-bottom: 1px solid #dbe4f0;
  font-size: 1.25rem;
  line-height: 1.35;
  font-weight: 800;
}

.report-document__body :deep(h3),
.report-document__body :deep(h4) {
  margin: 1rem 0 0.5rem;
  color: #1e293b;
  font-size: 1.08rem;
  font-weight: 800;
}

.report-document__body :deep(p) {
  margin: 0.62rem 0;
}

.report-document__body :deep(p:has(+ p)) {
  margin-bottom: 0.55rem;
}

.report-document__body :deep(p) {
  max-width: 100%;
}

.report-document__body :deep(ul),
.report-document__body :deep(ol) {
  margin: 0.6rem 0 0.9rem;
  padding-left: 1.35rem;
}

.report-document__body :deep(li) {
  margin: 0.38rem 0;
}

.report-document__body :deep(strong) {
  color: #0f172a;
  font-weight: 800;
}

.report-document__body :deep(table) {
  width: 100%;
  margin: 1rem 0;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  font-size: 0.94rem;
  table-layout: fixed;
}

.report-document__body :deep(th) {
  background: #eff6ff;
  color: #1e3a8a;
  font-weight: 800;
  text-align: left;
}

.report-document__body :deep(th),
.report-document__body :deep(td) {
  padding: 11px 13px;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: top;
  word-break: break-word;
}

.report-document__body :deep(td + td),
.report-document__body :deep(th + th) {
  border-left: 1px solid #e2e8f0;
}

.report-document__body :deep(tr:last-child td) {
  border-bottom: 0;
}

.report-document__body :deep(blockquote) {
  margin: 1rem 0;
  padding: 12px 14px;
  border-left: 4px solid #2563eb;
  border-radius: 0 8px 8px 0;
  background: #f8fafc;
  color: #334155;
}

.report-document__body :deep(code),
.report-document__body :deep(pre) {
  white-space: pre-wrap;
  font-family: inherit;
  background: #f8fafc;
  color: #334155;
}

@media (max-width: 860px) {
  .report-document__cover,
  .report-document__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .report-document__meta {
    grid-template-columns: 1fr;
  }
}
</style>
