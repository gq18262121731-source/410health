import { renderMarkdown } from "./markdown";

export type ReportDocumentMeta = {
  title: string;
  generatedAt?: string;
  windowLabel?: string;
};

const MARKDOWN_FENCE = /```(?:markdown|md)?|```/gi;
const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$/;
const SECTION_PREFIX = /^[\s#*-]*([一二三四五六七八九十]+[、.．]\s*)/;
const ACTION_PREFIX = /^(\d+\.\s*(?:立即行动|今日必查|持续观察|立即动作|今日复查))/;
const RISK_LEVEL_PATTERN = /(高风险|中\/低风险|中低风险|未知风险|低风险|数据链路风险)/g;
const ACTION_SECTION_PREFIX = /^[\s#*-]*(?:\u56db|4)[\u3001.．]\s*/;
const ACTION_SECTION_KEYWORDS = /(?:\u5904\u7f6e\u5efa\u8bae|\u660e\u786e\u52a8\u4f5c|\u8d23\u4efb\u4e3b\u4f53)/;
const ACTION_HEADER_KEYWORDS = /(?:\u7c7b\u522b|\u7c7b\u578b|\u5efa\u8bae\u52a8\u4f5c|\u6267\u884c\u8981\u6c42)/;
const CHECK_SECTION_PREFIX = /^[\s#*-]*(?:\u4e94|5)[\u3001.．]\s*/;
const CHECK_SECTION_KEYWORDS = /(?:\u5f85\u6838\u5b9e\u9879|\u4ea4\u73ed\u5fc5\u4ea4)/;
const ACTION_TABLE_LABELS = [
  "\u7d27\u6025\u6838\u67e5",
  "\u94fe\u8def\u6392\u67e5",
  "\u5de1\u68c0\u8865\u4f4d",
  "\u4ea4\u73ed\u540c\u6b65",
  "\u7acb\u5373\u884c\u52a8",
  "\u4eca\u65e5\u5fc5\u67e5",
  "\u6301\u7eed\u89c2\u5bdf",
];

function cleanInline(input: string): string {
  return String(input ?? "")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/^>\s*/, "")
    .replace(/^#+\s*/, "")
    .trim();
}

function splitPipeRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cleanInline(cell))
    .filter(Boolean);
}

function isPipeRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.includes("|") && !/^https?:\/\//i.test(trimmed);
}

function isSectionText(value: string): boolean {
  return SECTION_PREFIX.test(value.trim());
}

function asSectionHeading(value: string): string {
  return `## ${cleanInline(value).replace(/^[-*\s]+/, "")}`;
}

function isActionSectionText(value: string): boolean {
  const text = cleanInline(value);
  return (
    ACTION_SECTION_PREFIX.test(text) ||
    /^\s*#{0,3}\s*(?:\u56db|4)[\u3001\uff0e.]\s*/.test(text) ||
    text.includes("\u5904\u7f6e\u5efa\u8bae") ||
    text.includes("\u660e\u786e\u52a8\u4f5c") ||
    text.includes("\u8d23\u4efb\u4e3b\u4f53")
  );
}

function isCheckSectionText(value: string): boolean {
  const text = cleanInline(value);
  return CHECK_SECTION_PREFIX.test(text) || CHECK_SECTION_KEYWORDS.test(text);
}

function actionItemsFromCells(cells: string[]): string[] {
  return cells
    .map((cell) => cleanInline(cell))
    .filter((cell) => cell && !isDashCell(cell))
    .filter((cell) => !ACTION_HEADER_KEYWORDS.test(cell))
    .flatMap((cell) =>
      cell
        .split(/(?:\s*[；;]\s*|\s{2,})/)
        .map((item) => item.trim())
        .filter(Boolean),
    );
}

function pushActionList(output: string[], cells: string[]) {
  const items = actionItemsFromCells(cells);
  if (!items.length) return;
  if (output.length && output[output.length - 1] !== "") output.push("");
  items.forEach((item, index) => {
    const normalized = item.replace(/^\d+[.．、]\s*/, "");
    output.push(`${index + 1}. ${normalized}`);
  });
}

function actionLabelIndex(value: string): number {
  const text = cleanInline(value).replace(/^\d+[.．、]\s*/, "");
  return ACTION_TABLE_LABELS.findIndex((label) => text.includes(label));
}

function splitActionRequirement(lines: string[]): { action: string; requirement: string } {
  const cleanLines = lines.map((line) => cleanInline(line)).filter(Boolean);
  if (!cleanLines.length) return { action: "-", requirement: "-" };

  const requirementIndex = cleanLines.findIndex((line) =>
    /(?:分钟|小时|今日|当日|下班前|交班|完成|反馈|记录|明确写入)/.test(line),
  );

  if (requirementIndex >= 0 && cleanLines.length > 1) {
    return {
      action: cleanLines.filter((_, index) => index !== requirementIndex).join("；") || "-",
      requirement: cleanLines[requirementIndex],
    };
  }

  return { action: cleanLines.join("；"), requirement: "-" };
}

function pushActionTable(output: string[], cells: string[]) {
  const items = actionItemsFromCells(cells);
  if (!items.length) return;

  const rows: Array<{ label: string; lines: string[] }> = [];
  let current: { label: string; lines: string[] } | null = null;

  for (const item of items) {
    const labelIndex = actionLabelIndex(item);
    if (labelIndex >= 0) {
      if (current?.lines.length) rows.push(current);
      const label = ACTION_TABLE_LABELS[labelIndex];
      const rest = cleanInline(item).replace(label, "").replace(/^[:：\-—\s]+/, "");
      current = { label, lines: rest ? [rest] : [] };
      continue;
    }

    if (!current) {
      current = { label: ACTION_TABLE_LABELS[rows.length] ?? "\u5904\u7f6e\u4e8b\u9879", lines: [] };
    }
    current.lines.push(item);
  }

  if (current?.lines.length) rows.push(current);
  if (!rows.length) return;

  if (output.length && output[output.length - 1] !== "") output.push("");
  output.push("| \u5904\u7f6e\u7c7b\u578b | \u5904\u7f6e\u5185\u5bb9 | \u5b8c\u6210\u8981\u6c42 |");
  output.push("| --- | --- | --- |");
  for (const row of rows) {
    const { action, requirement } = splitActionRequirement(row.lines);
    output.push(`| ${row.label} | ${action} | ${requirement} |`);
  }
  output.push("");
}

function removeDuplicatedMetaLine(input: string): string {
  const lines = input.split("\n");
  const firstContentIndex = lines.findIndex((line) => line.trim());
  if (firstContentIndex < 0) return input;

  const firstLine = lines[firstContentIndex].trim();
  if (/生成时间[:：]/.test(firstLine) && /分析窗口[:：]/.test(firstLine)) {
    lines.splice(firstContentIndex, 1);
  }

  return lines.join("\n").trim();
}

function normalizeRiskCells(cells: string[]): string[] {
  if (cells.length <= 3) {
    return [cells[0] ?? "", cells[1] ?? "", cells[2] ?? ""];
  }
  return [cells[0] ?? "", cells[1] ?? "", cells.slice(2).join("；")];
}

function isDashCell(value: string): boolean {
  return /^[-—–\s]+$/.test(value.trim());
}

function extractCompressedRiskRows(cells: string[]): string[][] {
  const compact = cells
    .filter((cell) => !isDashCell(cell))
    .join("；")
    .replace(/[；;]\s*/g, "；")
    .replace(/\s+/g, " ")
    .trim();

  if (!compact || !RISK_LEVEL_PATTERN.test(compact)) {
    RISK_LEVEL_PATTERN.lastIndex = 0;
    return [];
  }
  RISK_LEVEL_PATTERN.lastIndex = 0;

  const rows: string[][] = [];
  const matches = [...compact.matchAll(RISK_LEVEL_PATTERN)];
  for (let index = 0; index < matches.length; index += 1) {
    const current = matches[index];
    const next = matches[index + 1];
    const level = current[1];
    const start = (current.index ?? 0) + current[0].length;
    const end = next?.index ?? compact.length;
    const rest = compact.slice(start, end).replace(/^[：:；;\s]+/, "").trim();
    const parts = rest.split("；").map((part) => part.trim()).filter(Boolean);
    const count = parts.shift() ?? "-";
    const description = parts.join("；") || "-";
    rows.push([level, count, description]);
  }

  return rows;
}

function pushTableHeader(output: string[], headers: string[]) {
  if (output.length && output[output.length - 1] !== "") output.push("");
  output.push(`| ${headers.join(" | ")} |`);
  output.push(`| ${headers.map(() => "---").join(" | ")} |`);
}

function normalizePipeTables(input: string): string {
  const lines = input.split("\n");
  const output: string[] = [];
  let tableMode: "risk" | "generic" | null = null;
  let genericColumnCount = 0;
  let inActionSection = false;
  let actionCellsBuffer: string[] = [];

  const closeTable = () => {
    if (tableMode && output[output.length - 1] !== "") output.push("");
    tableMode = null;
    genericColumnCount = 0;
  };

  const flushActionTable = () => {
    if (!actionCellsBuffer.length) return;
    pushActionTable(output, actionCellsBuffer);
    actionCellsBuffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      closeTable();
      if (!inActionSection) output.push("");
      continue;
    }

    if (TABLE_SEPARATOR.test(line)) continue;

    if (!isPipeRow(line)) {
      closeTable();
      if (isActionSectionText(line)) {
        flushActionTable();
        inActionSection = true;
      }
      if (isSectionText(line)) {
        if (inActionSection) flushActionTable();
        inActionSection = isActionSectionText(line);
      }
      if (inActionSection && ACTION_HEADER_KEYWORDS.test(line)) {
        continue;
      }
      output.push(rawLine);
      continue;
    }

    const cells = splitPipeRow(line);
    if (!cells.length) continue;

    const firstCell = cells[0] ?? "";
    const hasSectionCell = cells.some((cell) => isSectionText(cell));
    if (hasSectionCell) {
      closeTable();
      const sectionCellIndex = cells.findIndex((cell) => isSectionText(cell));
      if (inActionSection) flushActionTable();
      inActionSection = isActionSectionText(cells[sectionCellIndex]);
      output.push(asSectionHeading(cells[sectionCellIndex]));

      const trailingCells = cells.slice(sectionCellIndex + 1).filter(Boolean);
      if (inActionSection) {
        actionCellsBuffer.push(...trailingCells);
        continue;
      }
      if (trailingCells.length >= 2) {
        pushTableHeader(output, trailingCells);
        tableMode = "generic";
        genericColumnCount = trailingCells.length;
      }
      continue;
    }

    if (inActionSection) {
      closeTable();
      actionCellsBuffer.push(...cells);
      continue;
    }

    const riskHeader = cells.some((cell) => /风险等级|数量|说明/.test(cell));
    const riskRow = /^(高风险|中\/低风险|中低风险|未知风险|低风险|数据链路风险)$/.test(firstCell);
    if (riskHeader || riskRow || tableMode === "risk") {
      if (tableMode !== "risk") {
        closeTable();
        pushTableHeader(output, ["风险等级", "数量", "说明"]);
        tableMode = "risk";
      }
      if (!riskHeader) {
        if (cells.every(isDashCell)) continue;
        const compressedRows = extractCompressedRiskRows(cells);
        if (compressedRows.length) {
          for (const [level, count, description] of compressedRows) {
            output.push(`| ${level || "-"} | ${count || "-"} | ${description || "-"} |`);
          }
        } else {
          const [level, count, description] = normalizeRiskCells(cells);
          if (isDashCell(level) && isDashCell(count)) continue;
          output.push(`| ${level || "-"} | ${count || "-"} | ${description || "-"} |`);
        }
      }
      continue;
    }

    const genericHeader = cells.some((cell) => /老人|房号|设备MAC|优先原因|对象|事项|责任/.test(cell));
    if (genericHeader || tableMode === "generic") {
      if (tableMode !== "generic") {
        closeTable();
        pushTableHeader(output, cells);
        tableMode = "generic";
        genericColumnCount = cells.length;
        continue;
      }

      const paddedCells = [...cells];
      while (paddedCells.length < genericColumnCount) paddedCells.push("");
      output.push(`| ${paddedCells.slice(0, genericColumnCount).join(" | ")} |`);
      continue;
    }

    closeTable();
    output.push(cells.join(" / "));
  }

  if (inActionSection) flushActionTable();
  return output.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function normalizeActionParagraphTables(input: string): string {
  const lines = input.split("\n");
  const output: string[] = [];
  let inActionSection = false;
  let pendingRows: Array<{ label: string; lines: string[] }> = [];
  let current: { label: string; lines: string[] } | null = null;

  const flushRows = () => {
    if (current) {
      pendingRows.push(current);
      current = null;
    }
    if (!pendingRows.length) return;
    if (output.length && output[output.length - 1] !== "") output.push("");
    output.push("| \u5904\u7f6e\u7c7b\u578b | \u5904\u7f6e\u5185\u5bb9 | \u5b8c\u6210\u8981\u6c42 |");
    output.push("| --- | --- | --- |");
    for (const row of pendingRows) {
      const { action, requirement } = splitActionRequirement(row.lines);
      output.push(`| ${row.label} | ${action} | ${requirement} |`);
    }
    output.push("");
    pendingRows = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      if (!inActionSection || current) {
        continue;
      }
      output.push("");
      continue;
    }

    if (isSectionText(line)) {
      if (inActionSection) flushRows();
      inActionSection = isActionSectionText(line);
      output.push(rawLine);
      continue;
    }

    if (!inActionSection) {
      output.push(rawLine);
      continue;
    }

    if (ACTION_HEADER_KEYWORDS.test(line)) {
      continue;
    }

    if (line.startsWith("|")) {
      output.push(rawLine);
      continue;
    }

    const labelIndex = actionLabelIndex(line);
    if (labelIndex >= 0) {
      if (current) pendingRows.push(current);
      const label = ACTION_TABLE_LABELS[labelIndex];
      const rest = cleanInline(line).replace(label, "").replace(/^[:：\-—\s]+/, "");
      current = { label, lines: rest ? [rest] : [] };
      continue;
    }

    if (current) {
      current.lines.push(line);
      continue;
    }

    output.push(rawLine);
  }

  if (inActionSection) flushRows();
  return output.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function normalizeChecklistItems(input: string): string {
  const lines = input.split("\n");
  const output: string[] = [];
  let inCheckSection = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (isSectionText(line)) {
      inCheckSection = isCheckSectionText(line);
      output.push(rawLine);
      continue;
    }

    if (!inCheckSection) {
      output.push(rawLine);
      continue;
    }

    if (!line) {
      output.push(rawLine);
      continue;
    }

    const normalized = line
      .replace(/-\s*\[\s?\]/g, "□")
      .replace(/\[\s?\]/g, "□")
      .replace(/\s+-\s*□/g, " □");

    const items = normalized
      .split(/(?=□)/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (items.length > 1 || items[0]?.startsWith("□")) {
      for (const item of items) {
        output.push(item.startsWith("□") ? item : `□ ${item}`);
      }
      continue;
    }

    output.push(rawLine);
  }

  return output.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function normalizeListsAndHeadings(input: string): string {
  let text = input
    .replace(/^[-\s]*#{1,6}\s*(?=[一二三四五六七八九十]+[、.．])/gm, "## ")
    .replace(/^\s*[-*]\s*(?=[一二三四五六七八九十]+[、.．])/gm, "## ")
    .replace(/^([一二三四五六七八九十]+[、.．]\s*)/gm, "## $1")
    .replace(/^\s*-\s*(风险分布|核心判断|告警状态|风险态势|核心异常)[:：]/gm, "- **$1：**")
    .replace(/^\s*-\s*(?!\s|-)/gm, "- ")
    .replace(/^\s*[-*]\s*\[\s?\]\s*/gm, "- ")
    .replace(/^\s*√\s*/gm, "- ")
    .replace(/([；;。])\s*-\s*/g, "$1\n- ")
    .replace(/([；;。])\s*(\d+\.\s*(?:立即行动|今日必查|持续观察|立即动作|今日复查))/g, "$1\n\n### $2")
    .replace(/(^|\n)(\d+\.\s*(?:立即行动|今日必查|持续观察|立即动作|今日复查))/g, "$1### $2");

  text = text.replace(
    /^(##\s*(?:\u4e00|\u4e8c|\u4e09|\u56db|\u4e94|\u516d|\u4e03|\u516b|\u4e5d|\u5341|\d+)[\u3001\uff0e.][^\n]*?)(\s+\d+[\u3001\uff0e.]\s+.+)$/gm,
    "$1\n\n$2",
  );

  text = text
    .split("\n")
    .map((line) => {
      const trimmed = line.trim();
      if (ACTION_PREFIX.test(trimmed) && !trimmed.startsWith("###")) return `### ${trimmed}`;
      return line;
    })
    .join("\n");

  return text;
}

export function stripMarkdownNoise(input: string): string {
  let text = String(input ?? "").trim();
  if (!text) return "";

  text = removeDuplicatedMetaLine(text.replace(/\r\n/g, "\n").replace(MARKDOWN_FENCE, ""));
  text = normalizePipeTables(text);

  return text
    .replace(/^[-\s]*#{1,6}\s*/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(TABLE_SEPARATOR, "")
    .replace(/^\s*\|(.+)\|\s*$/gm, (_match, body: string) =>
      body
        .split("|")
        .map((cell) => cell.trim())
        .filter(Boolean)
        .join(" / "),
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function normalizeReportMarkdown(input: string): string {
  let text = String(input ?? "").trim();
  if (!text) return "";

  text = text
    .replace(/\r\n/g, "\n")
    .replace(MARKDOWN_FENCE, "")
    .replace(/^---+\s*(#{1,6})/gm, "$1")
    .replace(/^---+(?=\S)/gm, "")
    .replace(/^\s*>\s*✅?\s*注[:：]?\s*/gm, "> 注：")
    .replace(/\*\*\s+/g, "**")
    .replace(/\s+\*\*/g, "**");

  text = removeDuplicatedMetaLine(text);
  text = normalizeListsAndHeadings(text);
  text = normalizePipeTables(text);
  text = normalizeActionParagraphTables(text);
  text = normalizeChecklistItems(text);

  return text
    .replace(/([^\n])\n(#{2,3}\s)/g, "$1\n\n$2")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function extractReportMeta(content: string, fallbackTitle = "社区健康运营报告"): ReportDocumentMeta {
  const plain = stripMarkdownNoise(content);
  const firstLine = plain.split("\n").map((line) => line.trim()).find(Boolean) ?? fallbackTitle;
  const generatedAt = firstLine.match(/生成时间[:：]\s*([^|｜]+)/)?.[1]?.trim();
  const windowLabel = firstLine.match(/分析窗口[:：]\s*(.+)$/)?.[1]?.trim();
  const candidateTitle = firstLine
    .replace(/生成时间[:：].*$/g, "")
    .replace(/\s*[|｜]\s*$/g, "")
    .trim();
  const title =
    /报告|交接班|日度窗口|健康运营/.test(candidateTitle) && !isSectionText(candidateTitle)
      ? candidateTitle
      : fallbackTitle;

  return { title, generatedAt, windowLabel };
}

export function renderReportHtml(content: string): string {
  const normalized = normalizeReportMarkdown(content);
  return renderMarkdown(normalized || stripMarkdownNoise(content), { streaming: false });
}
