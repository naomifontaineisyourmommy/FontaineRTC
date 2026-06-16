/** Log line highlighting, ported from OlcRTC-VPS (themed via --ft-log-* tokens).
 *
 * Two layers:
 *   A. line level class (.ll-<lvl>) chosen by keyword matching
 *   B. token overlays (timestamps, ids, ip/host) wrapped in .tok-* spans,
 *      applied on the ESCAPED text so log content can't inject markup.
 */

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function logLevel(s: string): string {
  if (/\bERROR\b|panic:|fatal error|Unauthorized|frame too large|not-allowed|message authentication failed|decrypt failed|type='error'/.test(s)) return "crit";
  if (/\bWARN\b/.test(s)) return "attn";
  if (/\b(TRACE|DEBUG)\b/.test(s)) return "dim";
  if (/\[xmpp(:loop)?\]/.test(s)) return "dim";
  if (/missed pong|unhealthy|stream ended|bridge closed|reconnect requested|context deadline exceeded|closed pipe|handshake failed|wait jingle failed|leave-muc handshake failed|read (hdr|body): EOF|: EOF\b|state (changed: )?failed/i.test(s)) return "err";
  if (/MUC joined|Link connected|session opened|peer connected|control alive|session-accept sent|bridge open sctp|state: connected|reconnected\b|connected to WB Stream|\bconnected\b/i.test(s)) return /control alive/i.test(s) ? "okhi" : "ok";
  if (/reconnect|rejoin|reinitiate|waiting for peer|tearing down|state: (checking|connecting|closed)|disconnected|session closed/i.test(s)) return "attn";
  return "info";
}

const TOKEN_RE = /(\[\d{2}:\d{2}:\d{2}\](?:\s\d{4}\/\d{2}\/\d{2}\s\d{2}:\d{2}:\d{2})?)|([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})|(\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})|([a-z0-9][a-z0-9.-]*\.[a-z]{2,}:\d{2,5})|(install-[0-9a-f]+)|(peer=[0-9a-f]{3,})|(missed_pongs=\d+|duration=\d+s|rtt=[\d.]+m?s|missed \d+ pong)/gi;

function tokenize(escaped: string): string {
  return escaped.replace(TOKEN_RE, (m, ts, uuid, ip, host, inst, peer) => {
    if (ts) return `<span class="tok-ts">${m}</span>`;
    if (uuid || inst || peer) return `<span class="tok-id">${m}</span>`;
    if (ip || host) return `<span class="tok-dest">${m}</span>`;
    return `<span class="tok-b">${m}</span>`;
  });
}

/** Return ready-to-render HTML for one log line (class + token spans). */
export function highlightLine(line: string): string {
  const lvl = logLevel(line);
  return `<span class="ll ll-${lvl}">${tokenize(escapeHtml(line))}</span>`;
}
