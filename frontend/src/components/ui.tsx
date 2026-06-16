/** Small shared UI primitives: Modal + toast system. */

import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

// ── Modal ──────────────────────────────────────────────────────────────────--
// Rendered into document.body via a portal: a glass ancestor (backdrop-filter)
// becomes the containing block for position:fixed, which would otherwise clip a
// nested modal inside its parent.
export function Modal({
  title, onClose, children, footer,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

// ── Toasts ─────────────────────────────────────────────────────────────────--
interface Toast { id: number; msg: string; ok: boolean; }
interface ToastCtx { push: (msg: string, ok?: boolean) => void; }

const Ctx = createContext<ToastCtx | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((msg: string, ok = true) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, ok }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.ok ? "" : "err"}`}>{t.msg}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

/** Liquid-glass switch toggle (drop-in replacement for a checkbox). */
export function Switch({
  checked, onChange, label, disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className={`switch ${disabled ? "switch-disabled" : ""}`}>
      <input type="checkbox" checked={checked} disabled={disabled}
        onChange={(e) => onChange(e.target.checked)} />
      <span className="switch-track"><span className="switch-thumb" /></span>
      {label != null && <span className="switch-label">{label}</span>}
    </label>
  );
}

export function copy(text: string): void {
  // navigator.clipboard requires a secure context (HTTPS/localhost). The panel
  // is usually served over plain HTTP, so fall back to execCommand.
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text: string): void {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand("copy"); } catch { /* ignore */ }
  document.body.removeChild(ta);
}

export function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(n) / Math.log(1024));
  return `${(n / 1024 ** i).toFixed(1)} ${u[i]}`;
}

export function fmtUptime(s: number): string {
  if (!s) return "—";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}ч ${m}м` : `${m}м`;
}

/** Connected-clients counter with a themed hover popover listing their HWIDs. */
export function Peers({ count, devices }: { count: number; devices?: string[] }) {
  const list = devices ?? [];
  return (
    <span className="peers">
      👥 {count}
      <span className="peers-pop">
        <div className="peers-title">Подключённые HWID</div>
        {list.length
          ? list.map((d) => <div key={d} className="peers-hwid">{d}</div>)
          : <div className="faint">Никто не подключён</div>}
      </span>
    </span>
  );
}
