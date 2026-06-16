/** Theme import/export: downloadable template + uploaded-file parsing. */

import { FALLBACKS, TOKENS } from "./tokens";
import type { Theme } from "./themes";

/**
 * Build a documented theme template (JSON with // comments — JSONC). Each token
 * is annotated with its description so users know what every color paints. Base
 * values come from `base` (e.g. the current theme) or the registry fallbacks.
 */
export function buildTemplate(base?: Theme): string {
  const values = { ...FALLBACKS, ...(base?.tokens ?? {}) };
  const lines: string[] = [];
  lines.push("{");
  lines.push(`  "name": "My Custom Theme",`);
  lines.push(`  "tokens": {`);

  let currentGroup = "";
  TOKENS.forEach((t, i) => {
    if (t.group !== currentGroup) {
      currentGroup = t.group;
      lines.push("");
      lines.push(`    // ── ${t.group} ──`);
    }
    const comma = i < TOKENS.length - 1 ? "," : "";
    lines.push(`    "${t.key}": ${JSON.stringify(values[t.key])}${comma}  // ${t.description}`);
  });

  lines.push(`  }`);
  lines.push("}");
  return lines.join("\n");
}

/** Strip // line and /* *​/ block comments so JSONC parses as JSON. */
function stripComments(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

export interface ParsedTheme {
  theme: Theme;
  unknownKeys: string[];
  missingKeys: string[];
}

/** Parse + validate an uploaded theme file. Missing tokens fall back; unknown
 *  keys are ignored (but reported). Throws on unusable input. */
export function parseThemeFile(text: string): ParsedTheme {
  let data: unknown;
  try {
    data = JSON.parse(stripComments(text));
  } catch {
    throw new Error("Файл не является корректным JSON");
  }
  if (typeof data !== "object" || data === null) {
    throw new Error("Ожидался объект темы");
  }
  const obj = data as Record<string, unknown>;
  const name = typeof obj.name === "string" && obj.name.trim() ? obj.name.trim() : "Импортированная тема";
  const rawTokens = obj.tokens;
  if (typeof rawTokens !== "object" || rawTokens === null) {
    throw new Error('Отсутствует объект "tokens"');
  }
  const tokensIn = rawTokens as Record<string, unknown>;

  const known = new Set(TOKENS.map((t) => t.key));
  const tokens: Record<string, string> = { ...FALLBACKS };
  const unknownKeys: string[] = [];
  for (const [k, v] of Object.entries(tokensIn)) {
    if (!known.has(k)) {
      unknownKeys.push(k);
      continue;
    }
    if (typeof v === "string" && v.trim()) tokens[k] = v.trim();
  }
  const missingKeys = TOKENS.filter((t) => !(t.key in tokensIn)).map((t) => t.key);
  return { theme: { name, tokens }, unknownKeys, missingKeys };
}

/** Trigger a browser download of `text` as `filename`. */
export function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
