import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true,
});

type RenderMarkdownOptions = {
  /**
   * For streaming scenarios: the content may end mid-block (e.g. an unclosed code fence).
   * We try to "balance" common fences so the preview stays stable.
   */
  streaming?: boolean;
};

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

export function renderMarkdown(content: string, options: RenderMarkdownOptions = {}): string {
  const text = String(content ?? "");
  const trimmed = text.trim();
  if (!trimmed) return "";

  const normalized = options.streaming ? balanceCodeFences(trimmed) : trimmed;
  return markdown.render(normalized);
}
