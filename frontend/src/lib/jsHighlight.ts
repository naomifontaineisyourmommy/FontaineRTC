/** Minimal JavaScript syntax highlighter -> HTML for short snippets.
 *  Theme-aware via the `.code-block .js*` rules in global.css. Not a full parser,
 *  but it correctly distinguishes regex literals from division and handles
 *  strings/comments/numbers/keywords — enough to make a one-liner readable. */

const KEYWORDS = new Set([
  "const", "let", "var", "function", "return", "try", "catch", "finally",
  "for", "while", "do", "if", "else", "switch", "case", "break", "continue",
  "throw", "new", "delete", "typeof", "instanceof", "in", "of", "void",
  "yield", "await", "async", "class", "extends", "super", "this",
  "null", "true", "false", "undefined",
]);

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const span = (cls: string, s: string) => `<span class="${cls}">${esc(s)}</span>`;

export function highlightJs(src: string): string {
  let out = "";
  let i = 0;
  const n = src.length;
  // Whether the next `/` begins a regex literal (true) or is division (false).
  let regexOk = true;

  while (i < n) {
    const c = src[i];

    if (/\s/.test(c)) { out += c; i++; continue; }

    // line / block comments
    if (c === "/" && src[i + 1] === "/") {
      let j = i + 2; while (j < n && src[j] !== "\n") j++;
      out += span("jsc", src.slice(i, j)); i = j; regexOk = true; continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      let j = i + 2; while (j < n && !(src[j] === "*" && src[j + 1] === "/")) j++;
      j = Math.min(n, j + 2);
      out += span("jsc", src.slice(i, j)); i = j; regexOk = true; continue;
    }

    // strings (', ", `) — backslash escapes respected
    if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < n) {
        if (src[j] === "\\") { j += 2; continue; }
        if (src[j] === c) { j++; break; }
        j++;
      }
      out += span("jss", src.slice(i, j)); i = j; regexOk = false; continue;
    }

    // regex literal
    if (c === "/" && regexOk) {
      let j = i + 1, inClass = false;
      while (j < n) {
        const d = src[j];
        if (d === "\\") { j += 2; continue; }
        if (d === "[") inClass = true;
        else if (d === "]") inClass = false;
        else if (d === "/" && !inClass) { j++; break; }
        else if (d === "\n") break;
        j++;
      }
      while (j < n && /[a-z]/i.test(src[j])) j++;   // flags
      out += span("jsr", src.slice(i, j)); i = j; regexOk = false; continue;
    }

    // number
    if (/[0-9]/.test(c)) {
      let j = i; while (j < n && /[0-9.xXa-fA-F]/.test(src[j])) j++;
      out += span("jsn", src.slice(i, j)); i = j; regexOk = false; continue;
    }

    // identifier / keyword
    if (/[A-Za-z_$]/.test(c)) {
      let j = i; while (j < n && /[A-Za-z0-9_$]/.test(src[j])) j++;
      const word = src.slice(i, j);
      if (KEYWORDS.has(word)) { out += span("jsk", word); regexOk = true; }
      else { out += esc(word); regexOk = false; }
      i = j; continue;
    }

    // punctuation / operators — a regex may follow most, but not ) ] }
    out += span("jsp", c);
    regexOk = !(c === ")" || c === "]" || c === "}");
    i++;
  }
  return out;
}
