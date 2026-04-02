import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true,
  typographer: false,
});

type RenderMarkdownOptions = {
  /**
   * For streaming scenarios: the content may end mid-block (e.g. an unclosed code fence).
   * We try to "balance" common fences so the preview stays stable.
   */
  streaming?: boolean;
};

function unwrapOuterMarkdownFence(input: string): string {
  const text = String(input ?? "");
  const openingMatch = text.match(/^\s*(```|~~~)(?:markdown|md)\s*\r?\n/i);
  if (!openingMatch) return text;

  const fence = openingMatch[1];
  let body = text.slice(openingMatch[0].length);
  const closingPattern = new RegExp(`(?:\\r?\\n)${fence}\\s*$`);
  body = body.replace(closingPattern, "");
  return body.trim();
}

function balanceCodeFences(input: string): string {
  let text = String(input ?? "");

  // Balance triple-backtick fenced code blocks.
  const backtickCount = (text.match(/```/g) ?? []).length;
  if (backtickCount % 2 === 1) {
    text = text + "\n```\n";
  }

  // Balance triple-tilde fenced code blocks.
  const tildeCount = (text.match(/~~~/g) ?? []).length;
  if (tildeCount % 2 === 1) {
    text = `${text}\n~~~\n`;
  }

  return text;
}

/**
 * Normalizes common LLM markdown quirks so that markdown-it can parse
 * tables, headings, and lists correctly.
 */
function normalizeMarkdown(input: string): string {
  let text = String(input ?? "");

  // 1. Remove emulated "horizontal lines" or extra dashes that often break table detection
  //    if they are directly glued to the table pipe.
  //    e.g. "-------------------|| 1 |" -> "\n\n| 1 |"
  text = text.replace(/^-{3,}(\|{1,2})/gm, "\n\n|");

  // 2. Fix double pipes at start of line which confuse standard parsers
  text = text.replace(/^\|\|/gm, "|");

  // 3. Ensure a blank line BEFORE a table header row.
  //    Markdown-it is strict: a table must be preceded by a blank line.
  //    Pattern: non-blank line → table header (| ... |) → separator (| --- | ... |)
  text = text.replace(
    /([^\n])\n(\|[^\n]+\|\s*\n\s*\|[\s:]*-{2,}[\s:]*\|)/g,
    "$1\n\n$2",
  );

  // 4. Ensure a blank line AFTER a table (before non-table content)
  //    This prevents the next paragraph from being swallowed into the table.
  text = text.replace(
    /(\|[^\n]+\|\s*\n)([^\s|])/g,
    "$1\n$2",
  );

  // 5. Ensure blank lines before headings (# ... ##)
  //    LLMs frequently glue headings directly to paragraphs.
  text = text.replace(/([^\n])\n(#{1,6}\s)/g, "$1\n\n$2");

  // 6. Ensure blank lines before list items that come after a paragraph
  text = text.replace(/([^\n])\n(\s*[-*+]\s)/g, "$1\n\n$2");
  text = text.replace(/([^\n])\n(\s*\d+\.\s)/g, "$1\n\n$2");

  // 7. Ensure blank line before blockquotes
  text = text.replace(/([^\n>])\n(>\s)/g, "$1\n\n$2");

  // 8. Normalize bold markers that LLMs sometimes emit with extra spaces
  //    e.g. "** 标题 **" → "**标题**"
  text = text.replace(/\*\*\s+/g, "**");
  text = text.replace(/\s+\*\*/g, "**");

  // 9. Collapse 3+ consecutive blank lines into 2 (keeps structure clean)
  text = text.replace(/\n{4,}/g, "\n\n\n");

  return text;
}

export function renderMarkdown(content: string, options: RenderMarkdownOptions = {}): string {
  const text = String(content ?? "");
  const trimmed = text.trim();
  if (!trimmed) return "";

  // Normalize before balancing fences
  let processed = unwrapOuterMarkdownFence(trimmed);
  processed = normalizeMarkdown(processed);
  if (options.streaming) {
    processed = balanceCodeFences(processed);
  }

  return markdown.render(processed);
}
