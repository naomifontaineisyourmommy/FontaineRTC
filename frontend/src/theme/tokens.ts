/**
 * Theme token registry — the single source of truth for FontaineRTC theming.
 *
 * Every interface element is styled through one of these semantic CSS variables.
 * Themes (built-in or custom) provide a value for each token. The registry is
 * also used to generate the downloadable theme template (with descriptions) and
 * to validate uploaded themes.
 *
 * To add a new themeable element: add a token here, use var(--ft-…) in CSS, and
 * give it a value in each built-in theme (themes.ts). Custom themes missing the
 * token fall back to the value declared here.
 */

export interface ThemeToken {
  key: string;          // CSS custom property name, e.g. "--ft-bg"
  group: string;        // grouping for the template / editor
  label: string;        // short human label
  description: string;  // what element this paints
  fallback: string;     // used when a theme omits the token
}

export const TOKENS: ThemeToken[] = [
  // Surfaces
  { key: "--ft-bg", group: "Surfaces", label: "App background", description: "Page background behind everything", fallback: "#0c0c0c" },
  { key: "--ft-surface", group: "Surfaces", label: "Surface", description: "Cards, panels, tiles", fallback: "#15161c" },
  { key: "--ft-surface-2", group: "Surfaces", label: "Elevated surface", description: "Modals, dropdowns, popovers", fallback: "#1a1b22" },
  { key: "--ft-surface-3", group: "Surfaces", label: "Inset surface", description: "Inputs, nested/inset areas", fallback: "#0d0d15" },

  // Borders
  { key: "--ft-border", group: "Borders", label: "Border", description: "Default borders and dividers", fallback: "#252535" },
  { key: "--ft-border-strong", group: "Borders", label: "Strong border", description: "Emphasized borders, hovered outlines", fallback: "#3a3a4a" },

  // Text
  { key: "--ft-text", group: "Text", label: "Primary text", description: "Main body / heading text", fallback: "#e0e0e0" },
  { key: "--ft-text-muted", group: "Text", label: "Muted text", description: "Secondary labels", fallback: "#9a9aae" },
  { key: "--ft-text-faint", group: "Text", label: "Faint text", description: "Placeholders, disabled, hints", fallback: "#5a5a6a" },
  { key: "--ft-text-on-accent", group: "Text", label: "Text on accent", description: "Text/icon on accent-filled buttons", fallback: "#ffffff" },

  // Accent
  { key: "--ft-accent", group: "Accent", label: "Accent", description: "Primary actions, links, active state", fallback: "#3b82f6" },
  { key: "--ft-accent-hover", group: "Accent", label: "Accent hover", description: "Hover/active accent", fallback: "#2f6fd6" },
  { key: "--ft-accent-soft", group: "Accent", label: "Soft accent", description: "Subtle accent fills, highlights, chips", fallback: "rgba(59,130,246,0.15)" },

  // Status
  { key: "--ft-success", group: "Status", label: "Success", description: "Running / online / start", fallback: "#22c55e" },
  { key: "--ft-success-soft", group: "Status", label: "Soft success", description: "Success backgrounds/badges", fallback: "rgba(34,197,94,0.15)" },
  { key: "--ft-danger", group: "Status", label: "Danger", description: "Stop / delete / offline / errors", fallback: "#ef4444" },
  { key: "--ft-danger-hover", group: "Status", label: "Danger hover", description: "Hover for destructive actions", fallback: "#dc2626" },
  { key: "--ft-warning", group: "Status", label: "Warning", description: "Restart / attention", fallback: "#f59e0b" },
  { key: "--ft-info", group: "Status", label: "Info", description: "Informational accents (live, hints)", fallback: "#38bdf8" },

  // Components
  { key: "--ft-header-bg", group: "Components", label: "Header background", description: "Top navigation bar", fallback: "#111217" },
  { key: "--ft-overlay", group: "Components", label: "Modal overlay", description: "Backdrop behind modals", fallback: "rgba(0,0,0,0.6)" },
  { key: "--ft-shadow", group: "Components", label: "Shadow color", description: "Box-shadow tint", fallback: "rgba(0,0,0,0.4)" },
  { key: "--ft-log-bg", group: "Components", label: "Log background", description: "Live log / terminal area", fallback: "#07070b" },
  { key: "--ft-log-text", group: "Components", label: "Log text", description: "Live log text", fallback: "#c8d0d8" },
  { key: "--ft-scrollbar", group: "Components", label: "Scrollbar", description: "Custom scrollbar thumb", fallback: "#2a2a3a" },

  // Log highlighting
  { key: "--ft-log-base", group: "Logs", label: "Log base line", description: "Default/info log line", fallback: "#9ca3af" },
  { key: "--ft-log-crit", group: "Logs", label: "Log critical", description: "ERROR / panic / fatal lines", fallback: "#f87171" },
  { key: "--ft-log-err", group: "Logs", label: "Log error", description: "Connection drops, EOF, failures", fallback: "#f87171" },
  { key: "--ft-log-warn", group: "Logs", label: "Log warning", description: "WARN / reconnect / disconnect", fallback: "#fb923c" },
  { key: "--ft-log-ok", group: "Logs", label: "Log success", description: "Connected / joined / opened", fallback: "#34d399" },
  { key: "--ft-log-okhi", group: "Logs", label: "Log success (strong)", description: "Healthy/alive heartbeats", fallback: "#22c55e" },
  { key: "--ft-log-dim", group: "Logs", label: "Log dim", description: "TRACE / DEBUG / xmpp noise", fallback: "#6b7280" },
  { key: "--ft-log-ts", group: "Logs", label: "Log timestamp", description: "Leading [HH:MM:SS] token", fallback: "#555a66" },
  { key: "--ft-log-id", group: "Logs", label: "Log id", description: "UUIDs, install-/peer ids", fallback: "#3b82f6" },
  { key: "--ft-log-dest", group: "Logs", label: "Log destination", description: "IP:port and host:port tokens", fallback: "#38bdf8" },
];

export const TOKEN_KEYS: string[] = TOKENS.map((t) => t.key);

/** Map of token key -> fallback value (used to fill gaps in any theme). */
export const FALLBACKS: Record<string, string> = Object.fromEntries(
  TOKENS.map((t) => [t.key, t.fallback]),
);
