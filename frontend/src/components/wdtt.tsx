/** Shared WDTT UI: user table + add form, reused by the node page and the admin
 *  server modal (they differ only in which endpoint the callbacks hit). */

import { useState } from "react";
import { Switch, copy, fmtBytes, useToast } from "./ui";

export interface WdttUser {
  password: string;
  status: string;            // active | bound | expired | deactivated
  expires_at: number;
  down_bytes: number;
  up_bytes: number;
  device_id: string;
  device_ip: string;
}

const STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "активен", cls: "badge-on" },
  bound: { label: "активен · привязан", cls: "badge-on" },
  expired: { label: "истёк", cls: "badge-off" },
  deactivated: { label: "выключен", cls: "badge-off" },
};

function fmtExpires(exp: number): string {
  if (!exp) return "бессрочно";
  const d = new Date(exp * 1000);
  const days = Math.ceil((exp - Date.now() / 1000) / 86400);
  return `${d.toLocaleDateString()} (${days}д)`;
}

export function WdttUsersTable({ users, onToggle, onDelete }: {
  users: WdttUser[];
  onToggle: (u: WdttUser) => void;
  onDelete: (u: WdttUser) => void;
}) {
  const toast = useToast();
  if (!users.length) return <div className="faint" style={{ padding: "8px 0" }}>Пользователей нет.</div>;
  return (
    <>
      {users.map((u) => {
        const st = STATUS[u.status] ?? { label: u.status, cls: "badge-off" };
        return (
          <div className="card" key={u.password} style={{ marginBottom: 8, padding: 12 }}>
            <div className="row-between">
              <span className="uri uri-copy" style={{ maxWidth: "60%" }}
                title="Нажмите, чтобы скопировать пароль"
                onClick={() => { copy(u.password); toast.push("Пароль скопирован"); }}>
                {u.password}
              </span>
              <span className="row" style={{ gap: 6 }}>
                <span className={`badge ${st.cls}`}>{st.label}</span>
                <Switch checked={u.status !== "deactivated"} onChange={() => onToggle(u)} />
                <button className="btn btn-danger btn-sm" onClick={() => {
                  if (confirm("Удалить пользователя WDTT?")) onDelete(u);
                }}>🗑</button>
              </span>
            </div>
            <div className="tile-meta" style={{ marginTop: 6 }}>
              <span>срок: {fmtExpires(u.expires_at)}</span>
              <span>↓ {fmtBytes(u.down_bytes)}</span>
              <span>↑ {fmtBytes(u.up_bytes)}</span>
              <span>{u.device_id ? `${u.device_id} · ${u.device_ip || "?"}` : "не привязан"}</span>
            </div>
          </div>
        );
      })}
    </>
  );
}

export function WdttAddForm({ onAdd }: { onAdd: (p: { days: number; password: string; vk_hash: string }) => void }) {
  const [days, setDays] = useState("30");
  const [password, setPassword] = useState("");
  const [vk, setVk] = useState("");
  return (
    <div className="card" style={{ marginBottom: 12, padding: 12 }}>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ width: 90 }}>
          <label>Дней (0=∞)</label>
          <input value={days} onChange={(e) => setDays(e.target.value)} />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <label>Пароль (пусто = случайный)</label>
          <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="авто" />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <label>VK-хеш (необязательно)</label>
          <input value={vk} onChange={(e) => setVk(e.target.value)} placeholder="для готовой ссылки" />
        </div>
        <button className="btn" onClick={() => {
          onAdd({ days: parseInt(days) || 0, password: password.trim(), vk_hash: vk.trim() });
          setPassword(""); setVk("");
        }}>＋ Добавить</button>
      </div>
    </div>
  );
}
