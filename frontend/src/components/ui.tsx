/** Small shared UI primitives: Modal + toast system. */

import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";

// ── Modal ──────────────────────────────────────────────────────────────────--
export function Modal({
  title, onClose, children, footer,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
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

export function copy(text: string): void {
  navigator.clipboard?.writeText(text).catch(() => {});
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
