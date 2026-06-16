import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, sseUrl } from "../api/client";
import { Modal, copy, fmtBytes, fmtUptime, useToast } from "../components/ui";
import { CARRIERS, compatTransports, PARAM_FIELDS } from "../lib/compat";

interface Instance {
  id: string; carrier: string; transport: string; running: boolean;
  uri: string; uri_live: boolean; uptime: number; peers_count: number;
  traffic_rx: number; traffic_tx: number; custom_room_id: string;
  jitsi_chosen_domain: string; auto_restart: boolean; wb_token: string;
  max_session_duration: string; key: string; [k: string]: any;
}
interface Status {
  users: Instance[];
  server: { cpu_percent: number; mem_percent: number; mem_used_mb: number; mem_total_mb: number };
  jitsi_domains: string;
}

export function NodeDashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [sel, setSel] = useState<string>("");
  const [showAdd, setShowAdd] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const toast = useToast();

  const refresh = useCallback(async () => {
    try { setStatus(await apiGet("/api/status")); } catch { /* shown elsewhere */ }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  const users = status?.users ?? [];
  useEffect(() => {
    if (users.length && !users.find((u) => u.id === sel)) setSel(users[0].id);
  }, [users, sel]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); toast.push(ok); refresh(); }
    catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  const selected = users.find((u) => u.id === sel);

  return (
    <>
      <div className="row-between" style={{ padding: "14px 22px 0", flexWrap: "wrap", gap: 8 }}>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={() => setShowAdd(true)}>＋ Инстанс</button>
          <button className="btn btn-success btn-sm" title="Запустить все"
            onClick={() => act(() => apiPost("/api/users/start-all"), "Запуск всех")}>▶</button>
          <button className="btn btn-danger btn-sm" title="Остановить все"
            onClick={() => act(() => apiPost("/api/users/stop-all"), "Остановка всех")}>■</button>
          <button className="btn btn-warning btn-sm" title="Перезапустить все"
            onClick={() => act(() => apiPost("/api/users/restart-all"), "Перезапуск всех")}>↺</button>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <a className="btn btn-ghost btn-sm" href={sseUrl("/api/logs/download-all")}>⬇ Все логи</a>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowSettings(true)}>⚙ Настройки</button>
        </div>
      </div>

      {users.length === 0 && <div className="empty">Нет инстансов. Нажмите «＋ Инстанс».</div>}

      {users.length > 0 && (
        <>
          <div className="tabs">
            {users.map((u) => (
              <div key={u.id} className={`tab ${u.id === sel ? "active" : ""}`} onClick={() => setSel(u.id)}>
                <span className={`dot ${u.running ? "dot-on" : "dot-off"}`} style={{ marginRight: 6 }} />
                {u.carrier}/{u.transport} · {u.id.slice(0, 6)}
              </div>
            ))}
          </div>
          {selected && (
            <div className="workspace">
              <InstancePanel inst={selected} domains={status?.jitsi_domains ?? ""}
                onAction={act} onRefresh={refresh} />
              <LogView uid={selected.id} />
            </div>
          )}
        </>
      )}

      {status && (
        <div className="section-title">
          CPU {status.server.cpu_percent}% · RAM {status.server.mem_percent}%
          ({status.server.mem_used_mb}/{status.server.mem_total_mb} MB)
        </div>
      )}

      {showAdd && <AddInstanceModal onClose={() => setShowAdd(false)}
        onCreate={(c, t) => act(() => apiPost("/api/users/add", { carrier: c, transport: t }), "Инстанс создан")} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} onSaved={() => { setShowSettings(false); refresh(); }} />}
    </>
  );
}


function AddInstanceModal({ onClose, onCreate }: { onClose: () => void; onCreate: (c: string, t: string) => void }) {
  const [carrier, setCarrier] = useState("jitsi");
  const [transport, setTransport] = useState("datachannel");
  const opts = compatTransports(carrier);
  return (
    <Modal title="Новый инстанс" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={() => { onCreate(carrier, transport); onClose(); }}>Создать</button>
      </>}>
      <div className="field">
        <label>Сервис</label>
        <select value={carrier} onChange={(e) => {
          const c = e.target.value; setCarrier(c);
          if (!compatTransports(c).includes(transport)) setTransport(compatTransports(c)[0]);
        }}>
          {CARRIERS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Транспорт</label>
        <select value={transport} onChange={(e) => setTransport(e.target.value)}>
          {opts.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
    </Modal>
  );
}

function InstancePanel({ inst, domains, onAction, onRefresh }: {
  inst: Instance; domains: string;
  onAction: (fn: () => Promise<any>, ok: string) => Promise<void>;
  onRefresh: () => void;
}) {
  const [form, setForm] = useState<Instance>(inst);
  const toast = useToast();
  useEffect(() => { setForm(inst); }, [inst.id]); // reset when switching instance

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const domainList = domains.split("\n").map((d) => d.trim()).filter(Boolean);
  const transportOpts = compatTransports(form.carrier);
  const params = PARAM_FIELDS[form.transport] ?? [];

  const save = async () => {
    try {
      await apiPost(`/api/users/config/${inst.id}`, {
        carrier: form.carrier, transport: form.transport, key: form.key,
        custom_room_id: form.custom_room_id, jitsi_chosen_domain: form.jitsi_chosen_domain,
        auto_restart: form.auto_restart, wb_token: form.wb_token,
        max_session_duration: form.max_session_duration,
        ...Object.fromEntries(params.map((p) => [p, form[p]])),
      });
      toast.push("Сохранено"); onRefresh();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="row-between">
        <span className={`badge ${inst.running ? "badge-on" : "badge-off"}`}>
          {inst.running ? "● Работает" : "○ Остановлен"}
        </span>
        {inst.uri_live && <span className="badge badge-live">◆ URI live</span>}
      </div>
      <div className="row" style={{ gap: 6, margin: "8px 0" }}>
        {!inst.running
          ? <button className="btn btn-success btn-sm" onClick={() => onAction(() => apiPost(`/api/users/start/${inst.id}`), "Запущен")}>▶ Запустить</button>
          : <button className="btn btn-danger btn-sm" onClick={() => onAction(() => apiPost(`/api/users/stop/${inst.id}`), "Остановлен")}>■ Остановить</button>}
        <button className="btn btn-ghost btn-sm" onClick={() => { copy(inst.uri); toast.push("URI скопирован"); }}>⧉ URI</button>
        <button className="btn btn-danger btn-sm" onClick={() => {
          if (confirm("Удалить инстанс?")) onAction(() => apiPost(`/api/users/delete/${inst.id}`), "Удалён");
        }}>🗑</button>
      </div>
      <div className="uri" style={{ marginBottom: 10 }}>{inst.uri}</div>
      <div className="tile-meta" style={{ marginBottom: 10 }}>
        <span>⏱ {fmtUptime(inst.uptime)}</span>
        <span>👥 {inst.peers_count}</span>
        <span>↓ {fmtBytes(inst.traffic_rx)}</span>
        <span>↑ {fmtBytes(inst.traffic_tx)}</span>
      </div>

      <div className="field">
        <label>Сервис</label>
        <select value={form.carrier} onChange={(e) => {
          const c = e.target.value; const t = compatTransports(c);
          set("carrier", c); if (!t.includes(form.transport)) set("transport", t[0]);
        }}>{CARRIERS.map((c) => <option key={c}>{c}</option>)}</select>
      </div>
      <div className="field">
        <label>Транспорт</label>
        <select value={form.transport} onChange={(e) => set("transport", e.target.value)}>
          {transportOpts.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>
      {form.carrier === "jitsi" && domainList.length > 0 && (
        <div className="field">
          <label>Jitsi-домен (пусто = ручной Room ID)</label>
          <select value={form.jitsi_chosen_domain} onChange={(e) => set("jitsi_chosen_domain", e.target.value)}>
            <option value="">— ручной —</option>
            {domainList.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
      )}
      <div className="field">
        <label>Room ID / URL</label>
        <input value={form.custom_room_id} onChange={(e) => set("custom_room_id", e.target.value)}
          placeholder={form.carrier === "telemost" ? "обязателен" : "авто, если пусто"} />
      </div>
      {form.carrier === "wbstream" && (
        <div className="field">
          <label>WB Token (owner-mode)</label>
          <input value={form.wb_token} onChange={(e) => set("wb_token", e.target.value)} placeholder="bearer-токен" />
        </div>
      )}
      {params.map((p) => (
        <div className="field" key={p}>
          <label>{p}</label>
          <input value={form[p] ?? ""} onChange={(e) => set(p, e.target.value)} />
        </div>
      ))}
      <div className="field">
        <label>Макс. длительность сессии (напр. 6h)</label>
        <input value={form.max_session_duration} onChange={(e) => set("max_session_duration", e.target.value)} />
      </div>
      <label className="row" style={{ gap: 8 }}>
        <input type="checkbox" style={{ width: "auto" }} checked={form.auto_restart}
          onChange={(e) => set("auto_restart", e.target.checked)} /> Автозапуск
      </label>
      <button className="btn" style={{ marginTop: 12 }} onClick={save}>Сохранить</button>
    </div>
  );
}

function LogView({ uid }: { uid: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setLines([]);
    const es = new EventSource(sseUrl(`/api/logs/stream/${uid}`));
    es.onmessage = (ev) => {
      if (ev.data === ":ka") return;
      if (ev.data === "__CLEAR__") { setLines([]); return; }
      setLines((l) => [...l.slice(-1000), ev.data]);
    };
    return () => es.close();
  }, [uid]);
  useEffect(() => { if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight; }, [lines]);
  return <div className="log" ref={boxRef}>{lines.join("\n") || "Логи появятся после запуска…"}</div>;
}

function SettingsModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [cfg, setCfg] = useState<Record<string, any>>({});
  const toast = useToast();
  useEffect(() => { apiGet("/api/config").then(setCfg).catch(() => {}); }, []);
  const set = (k: string, v: any) => setCfg((c) => ({ ...c, [k]: v }));
  const save = async () => {
    try {
      await apiPost("/api/config/save", {
        dns: cfg.dns, ffmpeg: cfg.ffmpeg, socks_proxy: cfg.socks_proxy,
        socks_proxy_port: cfg.socks_proxy_port, debug: !!cfg.debug,
        full_logs: !!cfg.full_logs, jitsi_domains: cfg.jitsi_domains,
      });
      toast.push("Настройки сохранены"); onSaved();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };
  return (
    <Modal title="Глобальные настройки" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={save}>Сохранить</button>
      </>}>
      <div className="field"><label>DNS</label><input value={cfg.dns ?? ""} onChange={(e) => set("dns", e.target.value)} /></div>
      <div className="field"><label>ffmpeg</label><input value={cfg.ffmpeg ?? ""} onChange={(e) => set("ffmpeg", e.target.value)} /></div>
      <div className="field"><label>SOCKS5 proxy</label><input value={cfg.socks_proxy ?? ""} onChange={(e) => set("socks_proxy", e.target.value)} /></div>
      <div className="field"><label>SOCKS5 port</label><input value={cfg.socks_proxy_port ?? ""} onChange={(e) => set("socks_proxy_port", e.target.value)} /></div>
      <div className="field"><label>Jitsi-домены (по одному в строке)</label>
        <textarea rows={4} value={cfg.jitsi_domains ?? ""} onChange={(e) => set("jitsi_domains", e.target.value)} /></div>
      <label className="row" style={{ gap: 8, marginBottom: 8 }}>
        <input type="checkbox" style={{ width: "auto" }} checked={!!cfg.debug} onChange={(e) => set("debug", e.target.checked)} /> Debug-логи
      </label>
      <label className="row" style={{ gap: 8 }}>
        <input type="checkbox" style={{ width: "auto" }} checked={!!cfg.full_logs} onChange={(e) => set("full_logs", e.target.checked)} /> Хранить полные логи
      </label>
    </Modal>
  );
}
