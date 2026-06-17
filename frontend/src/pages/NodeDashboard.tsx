import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, sseUrl } from "../api/client";
import { Modal, Peers, Switch, copy, fmtBytes, fmtUptime, useToast } from "../components/ui";
import { CARRIERS, compatTransports, PARAM_FIELDS } from "../lib/compat";
import { highlightLine } from "../lib/logHighlight";

interface Instance {
  id: string; carrier: string; transport: string; running: boolean;
  uri: string; uri_live: boolean; uptime: number; peers_count: number;
  peers_devices: string[];
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
  const anyStopped = users.some((u) => !u.running);
  const anyRunning = users.some((u) => u.running);

  return (
    <>
      <div className="row-between" style={{ padding: "14px 22px 0", flexWrap: "wrap", gap: 8 }}>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={() => setShowAdd(true)}>＋ Инстанс</button>
          <button className="btn btn-success btn-sm" title="Запустить все" disabled={!anyStopped}
            onClick={() => act(() => apiPost("/api/users/start-all"), "Запуск всех")}>▶</button>
          <button className="btn btn-danger btn-sm" title="Остановить все" disabled={!anyRunning}
            onClick={() => act(() => apiPost("/api/users/stop-all"), "Остановка всех")}>■</button>
          <button className="btn btn-warning btn-sm" title="Перезапустить все" disabled={!anyRunning}
            onClick={() => act(() => apiPost("/api/users/restart-all"), "Перезапуск всех")}>↺</button>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <a className="btn btn-ghost btn-sm" href={sseUrl("/api/logs/download-all")}>⬇ Все логи</a>
          <button className="btn btn-ghost btn-sm" onClick={() => {
            if (!confirm("Обновить панель из репозитория и перезапустить сервис?")) return;
            act(() => apiPost("/api/update"), "Обновление запущено, сервис перезапустится");
          }}>↺ Обновить</button>
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
  const timer = useRef<number | null>(null);
  useEffect(() => { setForm(inst); }, [inst.id]); // reset when switching instance

  const locked = inst.running;            // settings are read-only while running
  const domainList = domains.split("\n").map((d) => d.trim()).filter(Boolean);
  const transportOpts = compatTransports(form.carrier);
  const params = PARAM_FIELDS[form.transport] ?? [];

  const persist = async (next: Instance) => {
    try {
      await apiPost(`/api/users/config/${inst.id}`, {
        carrier: next.carrier, transport: next.transport, key: next.key,
        custom_room_id: next.custom_room_id, jitsi_chosen_domain: next.jitsi_chosen_domain,
        auto_restart: next.auto_restart, wb_token: next.wb_token,
        max_session_duration: next.max_session_duration,
        ...Object.fromEntries((PARAM_FIELDS[next.transport] ?? []).map((p) => [p, next[p]])),
      });
      onRefresh();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  // auto-save: immediate for selects/checkbox, debounced for free-text fields
  const commit = (patch: Partial<Instance>, debounce = false) => {
    const next = { ...form, ...patch };
    setForm(next);
    if (timer.current) clearTimeout(timer.current);
    if (debounce) timer.current = window.setTimeout(() => persist(next), 700);
    else persist(next);
  };

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="row-between">
        <span className={`badge ${inst.running ? "badge-on" : "badge-off"}`}>
          {inst.running ? "● Работает" : "○ Остановлен"}
        </span>
        {inst.uri_live && (
          <span className="badge badge-live badge-copy" title="Нажмите, чтобы скопировать URI"
            onClick={() => { copy(inst.uri); toast.push("URI скопирован"); }}>◆ URI live</span>
        )}
      </div>
      <div className="row" style={{ gap: 6, margin: "8px 0" }}>
        {!inst.running
          ? <button className="btn btn-success btn-sm" onClick={() => onAction(() => apiPost(`/api/users/start/${inst.id}`), "Запущен")}>▶ Запустить</button>
          : <button className="btn btn-danger btn-sm" onClick={() => onAction(() => apiPost(`/api/users/stop/${inst.id}`), "Остановлен")}>■ Остановить</button>}
        <button className="btn btn-danger btn-sm" onClick={() => {
          if (confirm("Удалить инстанс?")) onAction(() => apiPost(`/api/users/delete/${inst.id}`), "Удалён");
        }}>🗑</button>
      </div>
      <div className="uri uri-copy" title="Нажмите, чтобы скопировать" style={{ marginBottom: 10 }}
        onClick={() => { copy(inst.uri); toast.push("URI скопирован"); }}>{inst.uri}</div>
      <div className="tile-meta" style={{ marginBottom: 10 }}>
        <span>⏱ {fmtUptime(inst.uptime)}</span>
        <Peers count={inst.peers_count} devices={inst.peers_devices} />
        <span>↓ {fmtBytes(inst.traffic_rx)}</span>
        <span>↑ {fmtBytes(inst.traffic_tx)}</span>
      </div>

      <div className="faint" style={{ fontSize: ".78rem", marginBottom: 4 }}>
        {locked
          ? "🔒 Остановите инстанс, чтобы изменить настройки"
          : "Изменения сохраняются автоматически"}
      </div>

      <div className="field">
        <label>Сервис</label>
        <select value={form.carrier} disabled={locked} onChange={(e) => {
          const c = e.target.value; const t = compatTransports(c);
          commit({ carrier: c, transport: t.includes(form.transport) ? form.transport : t[0] });
        }}>{CARRIERS.map((c) => <option key={c}>{c}</option>)}</select>
      </div>
      <div className="field">
        <label>Транспорт</label>
        <select value={form.transport} disabled={locked} onChange={(e) => commit({ transport: e.target.value })}>
          {transportOpts.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>
      {form.carrier === "jitsi" && domainList.length > 0 && (
        <div className="field">
          <label>Jitsi-домен (пусто = ручной Room ID)</label>
          <select value={form.jitsi_chosen_domain} disabled={locked}
            onChange={(e) => commit({ jitsi_chosen_domain: e.target.value })}>
            <option value="">— ручной —</option>
            {domainList.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
      )}
      {!(form.carrier === "jitsi" && form.jitsi_chosen_domain) && (
        <div className="field">
          <label>Room ID / URL</label>
          <input value={form.custom_room_id} disabled={locked}
            onChange={(e) => commit({ custom_room_id: e.target.value }, true)}
            placeholder={form.carrier === "telemost" ? "обязателен" : "авто, если пусто"} />
        </div>
      )}
      {form.carrier === "wbstream" && (
        <div className="field">
          <label>WB Token (owner-mode)</label>
          <input value={form.wb_token} disabled={locked}
            onChange={(e) => commit({ wb_token: e.target.value }, true)} placeholder="bearer-токен" />
        </div>
      )}
      {params.map((p) => (
        <div className="field" key={p}>
          <label>{p}</label>
          <input value={form[p] ?? ""} disabled={locked}
            onChange={(e) => commit({ [p]: e.target.value } as Partial<Instance>, true)} />
        </div>
      ))}
      <div className="field">
        <label>Макс. длительность сессии (напр. 6h)</label>
        <input value={form.max_session_duration} disabled={locked}
          onChange={(e) => commit({ max_session_duration: e.target.value }, true)} />
      </div>
      <Switch checked={form.auto_restart} disabled={locked}
        onChange={(v) => commit({ auto_restart: v })} label="Автозапуск" />
    </div>
  );
}

function LogView({ uid }: { uid: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setLines([]);          // drop the previous instance's logs immediately
    setLoading(true);
    const es = new EventSource(sseUrl(`/api/logs/stream/${uid}`));
    es.onmessage = (ev) => {
      setLoading(false);   // first byte (data or keepalive) = stream is live
      if (ev.data === ":ka") return;
      if (ev.data === "__CLEAR__") { setLines([]); return; }
      setLines((l) => [...l.slice(-1000), ev.data]);
    };
    return () => es.close();
  }, [uid]);
  useEffect(() => { if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight; }, [lines]);

  if (loading) {
    return (
      <div className="log" ref={boxRef}>
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="sk-line" style={{ width: `${40 + ((i * 23) % 55)}%` }} />
        ))}
      </div>
    );
  }
  return (
    <div
      className="log"
      ref={boxRef}
      dangerouslySetInnerHTML={{
        __html: lines.length
          ? lines.map(highlightLine).join("")
          : '<span class="faint">Логи появятся после запуска…</span>',
      }}
    />
  );
}

function SettingsModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [cfg, setCfg] = useState<Record<string, any>>({});
  const toast = useToast();
  useEffect(() => { apiGet("/api/config").then(setCfg).catch(() => {}); }, []);
  const set = (k: string, v: any) => setCfg((c) => ({ ...c, [k]: v }));
  const save = async () => {
    try {
      await apiPost("/api/config/save", {
        dns: cfg.dns, socks_proxy: cfg.socks_proxy,
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
      <div className="field"><label>SOCKS5 proxy</label><input value={cfg.socks_proxy ?? ""} onChange={(e) => set("socks_proxy", e.target.value)} /></div>
      <div className="field"><label>SOCKS5 port</label><input value={cfg.socks_proxy_port ?? ""} onChange={(e) => set("socks_proxy_port", e.target.value)} /></div>
      <div className="field"><label>Jitsi-домены (по одному в строке)</label>
        <textarea rows={4} value={cfg.jitsi_domains ?? ""} onChange={(e) => set("jitsi_domains", e.target.value)} /></div>
      <div style={{ marginBottom: 10 }}>
        <Switch checked={!!cfg.debug} onChange={(v) => set("debug", v)} label="Debug-логи" />
      </div>
      <Switch checked={!!cfg.full_logs} onChange={(v) => set("full_logs", v)} label="Хранить полные логи" />
    </Modal>
  );
}
