import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { Modal, ModeToggle, Peers, Switch, copy, fmtBytes, fmtUptime, useToast } from "../components/ui";
import { WdttAddForm, WdttUsersTable, type WdttUser } from "../components/wdtt";
import { CARRIERS, compatTransports, PARAM_FIELDS } from "../lib/compat";
import { COUNTRIES, isKnownCountry } from "../lib/countries";

interface VUser {
  client_id: string; uri: string; running: boolean; uri_live: boolean;
  carrier: string; transport: string; uptime: number; peers_count: number;
  peers_devices: string[]; traffic_rx: number; traffic_tx: number;
  custom_room_id: string; jitsi_chosen_domain: string; auto_restart: boolean;
  wb_token: string; max_session_duration: string; [k: string]: any;
}
interface Server {
  id: number; name: string; ip: string; country: string; flag: string;
  group_id: number; group_name: string; online: boolean; cpu: number; ram: number;
  active_users: number; total_users: number; clients_online: number; push_active: boolean;
  jitsi_domains: string; users: VUser[];
  wdtt?: { installed: boolean; active: boolean; version: string; main_password: string; users: WdttUser[] };
}
interface Group { id: number; name: string; }
interface Data { servers: Server[]; groups: Group[]; tg_bot_token: string; tg_recipients: string; }

export function AdminDashboard() {
  const [data, setData] = useState<Data | null>(null);
  const [q, setQ] = useState("");
  const [openSrv, setOpenSrv] = useState<number | null>(null);
  const [modal, setModal] = useState<null | "addServer" | "groups" | "tg" | "jitsi">(null);
  const toast = useToast();

  const refresh = useCallback(async () => {
    try { setData(await apiGet("/api/data")); } catch { /* ignore */ }
  }, []);
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); toast.push(ok); refresh(); }
    catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  const groups = data?.groups ?? [];
  const servers = (data?.servers ?? []).filter((s) =>
    !q || s.name.toLowerCase().includes(q.toLowerCase()) ||
    s.country.toLowerCase().includes(q.toLowerCase()) ||
    s.group_name.toLowerCase().includes(q.toLowerCase()));
  const current = data?.servers.find((s) => s.id === openSrv) ?? null;

  return (
    <>
      <div className="row-between" style={{ padding: "14px 22px 0", flexWrap: "wrap", gap: 8 }}>
        <input className="search-input" style={{ maxWidth: 280 }} placeholder="Поиск серверов / групп…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={() => {
            if (groups.length === 0) toast.push("Сначала создайте группу", false);
            else setModal("addServer");
          }}>＋ Сервер</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setModal("groups")}>⊞ Группы</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setModal("jitsi")}>Jitsi-домены</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setModal("tg")}>TG-алерты</button>
          <button className="btn btn-ghost btn-sm" onClick={async () => {
            if (!confirm("Обновить все ноды из их репозиториев?")) return;
            try {
              const r = await apiPost("/api/servers/update-all", {});
              const res = r.results || [];
              const started = res.filter((x: any) => x.ok && !x.up_to_date).length;
              const upToDate = res.filter((x: any) => x.up_to_date).length;
              toast.push(`Обновление: запущено ${started}, уже актуальны ${upToDate}`);
            } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
          }}>↺ Обновить ноды</button>
        </div>
      </div>

      {groups.length === 0 && <div className="empty">Создайте группу (⊞ Группы), затем добавьте сервер.</div>}
      {servers.length === 0 && groups.length > 0 && <div className="empty">Нет серверов.</div>}

      {groups.map((g) => {
        const inGroup = servers.filter((s) => s.group_id === g.id);
        if (!inGroup.length) return null;
        const online = inGroup.reduce((a, s) => a + s.clients_online, 0);
        return (
          <div key={g.id}>
            <div className="section-title">{g.name} · Online: {online}</div>
            <div className="gallery">
              {inGroup.map((s) => <Tile key={s.id} s={s} onClick={() => setOpenSrv(s.id)} />)}
            </div>
          </div>
        );
      })}

      {current && <ServerModal srv={current} groups={groups}
        onClose={() => setOpenSrv(null)} onAction={act} onRefresh={refresh} />}
      {modal === "addServer" && <ServerFormModal groups={groups} onClose={() => setModal(null)}
        onSaved={() => { setModal(null); refresh(); }} />}
      {modal === "groups" && <GroupsModal groups={groups} onClose={() => setModal(null)} onChanged={refresh} />}
      {modal === "tg" && data && <TgModal data={data} onClose={() => setModal(null)} onSaved={() => { setModal(null); refresh(); }} />}
      {modal === "jitsi" && <JitsiModal onClose={() => setModal(null)} />}
    </>
  );
}

function Tile({ s, onClick }: { s: Server; onClick: () => void }) {
  return (
    <div className="tile" onClick={onClick}>
      <div className="tile-head">
        <span dangerouslySetInnerHTML={{ __html: s.flag }} />
        <span className="tile-name">{s.name}</span>
        <span className={`badge ${s.online ? "badge-on" : "badge-off"}`} style={{ marginLeft: "auto" }}>
          {s.online ? "online" : "offline"}
        </span>
        {s.push_active && <span className="badge badge-live">⚡</span>}
      </div>
      <div className="tile-meta">
        <span>CPU {s.cpu}%</span><span>RAM {s.ram}%</span>
        <span>▶ {s.active_users}/{s.total_users}</span>
        <Peers count={s.clients_online} devices={s.users.flatMap((u) => u.peers_devices ?? [])} />
      </div>
    </div>
  );
}

function ServerModal({ srv, groups, onClose, onAction, onRefresh }: {
  srv: Server; groups: Group[]; onClose: () => void;
  onAction: (fn: () => Promise<any>, ok: string) => Promise<void>; onRefresh: () => void;
}) {
  const [edit, setEdit] = useState(false);
  const [editInst, setEditInst] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [mode, setMode] = useState<"olcrtc" | "wdtt">("olcrtc");
  const toast = useToast();
  const node = (action: string, body: object) => apiPost(`/api/node/${action}`, { server_id: srv.id, ...body });
  const anyStopped = srv.users.some((u) => !u.running);
  const anyRunning = srv.users.some((u) => u.running);
  const wdtt = srv.wdtt || { installed: false, active: false, version: "", main_password: "", users: [] };

  return (
    <Modal title={`${srv.name} · ${srv.country}`} onClose={onClose}
      headExtra={<>
        <ModeToggle value={mode}
          options={[{ id: "olcrtc", label: "olcrtc" }, { id: "wdtt", label: "wdtt" }]}
          onChange={(v) => setMode(v as "olcrtc" | "wdtt")} />
        <button className="btn btn-ghost btn-sm" onClick={() => setEdit(true)}>✎ Изменить</button>
        <button className="btn btn-ghost btn-sm" onClick={async () => {
          try {
            const r = await apiPost("/api/servers/update", { server_id: srv.id });
            toast.push(r.up_to_date ? "Последняя версия уже установлена" : "Обновление ноды запущено");
          } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
        }}>↺ Обновить</button>
      </>}>
      {mode === "olcrtc" && (
        <div className="row" style={{ gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          <button className="btn btn-success btn-sm" disabled={!anyStopped} onClick={() => onAction(() => node("start-all", {}), "Запуск всех")}>▶ Все</button>
          <button className="btn btn-danger btn-sm" disabled={!anyRunning} onClick={() => onAction(() => node("stop-all", {}), "Остановка всех")}>■ Все</button>
          <button className="btn btn-warning btn-sm" disabled={!anyRunning} onClick={() => onAction(() => node("restart-all", {}), "Перезапуск всех")}>↺ Все</button>
          <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>＋ Инстанс</button>
        </div>
      )}

      {mode === "wdtt" ? (
        !wdtt.installed
          ? <div className="faint" style={{ padding: "8px 0" }}>WDTT не установлен на этой ноде.</div>
          : <>
            <div className="row" style={{ gap: 12, marginBottom: 10, flexWrap: "wrap" }}>
              <span className={`badge ${wdtt.active ? "badge-on" : "badge-off"}`}>
                {wdtt.active ? "WDTT активен" : "WDTT не активен"}
              </span>
              {wdtt.main_password && (
                <span className="muted">Главный пароль{" "}
                  <span className="uri uri-copy" style={{ padding: "2px 6px" }}
                    onClick={() => { copy(wdtt.main_password); toast.push("Главный пароль скопирован"); }}>
                    {wdtt.main_password}
                  </span>
                </span>
              )}
            </div>
            <WdttAddForm onAdd={(p) => onAction(() => node("wdtt-add", p), "Пользователь добавлен")} />
            <WdttUsersTable
              users={wdtt.users}
              onToggle={(u) => onAction(() => node("wdtt-toggle",
                { password: u.password, deactivated: u.status !== "deactivated" }), "Готово")}
              onDelete={(u) => onAction(() => node("wdtt-del", { password: u.password }), "Удалён")}
            />
          </>
      ) : (<>
      {srv.users.length === 0 && <div className="faint" style={{ padding: "8px 0" }}>Нет инстансов.</div>}
      {srv.users.map((u) => (
        <div className="card" key={u.client_id} style={{ marginBottom: 8, padding: 12 }}>
          <div className="row-between">
            <span className="row" style={{ gap: 8 }}>
              <span className={`dot ${u.running ? "dot-on" : "dot-off"}`} />
              {u.carrier}/{u.transport} · {u.client_id.slice(0, 6)}
            </span>
            <span className="row" style={{ gap: 6 }}>
              {u.uri_live && (
                <span className="badge badge-live badge-copy" title="Нажмите, чтобы скопировать URI"
                  onClick={() => { copy(u.uri); toast.push("URI скопирован"); }}>◆ URI live</span>
              )}
              {!u.running
                ? <button className="btn btn-success btn-sm" onClick={() => onAction(() => node("start-user", { id: u.client_id }), "Запущен")}>▶</button>
                : <button className="btn btn-danger btn-sm" onClick={() => onAction(() => node("stop-user", { id: u.client_id }), "Остановлен")}>■</button>}
              <button className="btn btn-ghost btn-sm" onClick={() => setEditInst(u.client_id)}>✎</button>
              <button className="btn btn-danger btn-sm" onClick={() => {
                if (confirm("Удалить инстанс?")) onAction(() => node("delete-user", { id: u.client_id }), "Удалён");
              }}>🗑</button>
            </span>
          </div>
          <div className="tile-meta" style={{ marginTop: 6 }}>
            <span>⏱ {fmtUptime(u.uptime)}</span>
            <Peers count={u.peers_count} devices={u.peers_devices} />
            <span>↓ {fmtBytes(u.traffic_rx)}</span>
            <span>↑ {fmtBytes(u.traffic_tx)}</span>
          </div>
        </div>
      ))}
      </>)}
      {edit && <ServerFormModal groups={groups} server={srv} onClose={() => setEdit(false)}
        onSaved={() => { setEdit(false); onRefresh(); }} />}
      {showAdd && <CreateInstanceModal serverId={srv.id} onClose={() => setShowAdd(false)}
        onCreated={() => { setShowAdd(false); onRefresh(); }} />}
      {editInst && (() => {
        const u = srv.users.find((x) => x.client_id === editInst);
        return u ? <InstanceEditModal serverId={srv.id} user={u} domains={srv.jitsi_domains}
          onClose={() => setEditInst(null)} onSaved={() => { setEditInst(null); onRefresh(); }} /> : null;
      })()}
    </Modal>
  );
}

function ServerFormModal({ groups, server, onClose, onSaved }: {
  groups: Group[]; server?: Server; onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    ip: server?.ip ?? "", api_key: "", country: server?.country ?? "",
    name: server?.name ?? "", group_id: server?.group_id ?? (groups[0]?.id ?? 0),
  });
  const toast = useToast();
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const save = async () => {
    if (!isKnownCountry(f.country)) {
      toast.push("Выберите страну из списка", false);
      return;
    }
    try {
      if (server) await apiPost("/api/servers/edit", { server_id: server.id, ...f });
      else await apiPost("/api/servers/add", f);
      toast.push(server ? "Сервер обновлён" : "Сервер добавлен"); onSaved();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };
  return (
    <Modal title={server ? "Изменить сервер" : "Новый сервер"} onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        {server && <button className="btn btn-danger" onClick={async () => {
          if (!confirm("Удалить сервер?")) return;
          try { await apiPost("/api/servers/delete", { server_id: server.id }); toast.push("Удалён"); onSaved(); }
          catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
        }}>Удалить</button>}
        <button className="btn" onClick={save}>Сохранить</button>
      </>}>
      <div className="field"><label>API-ссылка (http://IP:8080)</label>
        <input value={f.ip} onChange={(e) => set("ip", e.target.value)} placeholder="http://50.114.115.100:8080" /></div>
      <div className="field"><label>API-ключ {server && "(пусто = не менять)"}</label>
        <input value={f.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder="64 hex" /></div>
      <div className="field"><label>Страна</label>
        <input list="ft-countries" value={f.country} onChange={(e) => set("country", e.target.value)}
          placeholder="Начните вводить…" />
        <datalist id="ft-countries">
          {COUNTRIES.map((c) => <option key={c} value={c} />)}
        </datalist></div>
      <div className="field"><label>Название</label><input value={f.name} onChange={(e) => set("name", e.target.value)} /></div>
      <div className="field"><label>Группа</label>
        <select value={f.group_id} onChange={(e) => set("group_id", parseInt(e.target.value))}>
          {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select></div>
    </Modal>
  );
}

function GroupsModal({ groups, onClose, onChanged }: { groups: Group[]; onClose: () => void; onChanged: () => void }) {
  const [name, setName] = useState("");
  const toast = useToast();
  const run = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); toast.push(ok); onChanged(); } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };
  return (
    <Modal title="Группы серверов" onClose={onClose}>
      <div className="row" style={{ gap: 8, marginBottom: 12 }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название группы" />
        <button className="btn" onClick={() => { if (name.trim()) run(() => apiPost("/api/groups/add", { name }), "Группа создана"); setName(""); }}>＋</button>
      </div>
      {groups.map((g) => (
        <div className="row-between" key={g.id} style={{ padding: "6px 0" }}>
          <span>{g.name}</span>
          <button className="btn btn-danger btn-sm" onClick={() => run(() => apiPost("/api/groups/delete", { group_id: g.id }), "Группа удалена")}>🗑</button>
        </div>
      ))}
    </Modal>
  );
}

function TgModal({ data, onClose, onSaved }: { data: Data; onClose: () => void; onSaved: () => void }) {
  const [token, setToken] = useState(data.tg_bot_token);
  const [rec, setRec] = useState(data.tg_recipients);
  const toast = useToast();
  return (
    <Modal title="Telegram-уведомления" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={async () => {
          try { await apiPost("/api/tg-settings", { tg_bot_token: token, tg_recipients: rec }); toast.push("Сохранено"); onSaved(); }
          catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
        }}>Сохранить</button>
      </>}>
      <div className="field"><label>Bot Token</label><input value={token} onChange={(e) => setToken(e.target.value)} /></div>
      <div className="field"><label>Получатели (chat_id, по одному в строке)</label>
        <textarea rows={4} value={rec} onChange={(e) => setRec(e.target.value)} /></div>
      <button className="btn btn-ghost btn-sm" onClick={async () => {
        try {
          const r = await apiPost("/api/tg-updates", { tg_bot_token: token });
          if (r.users?.length) { setRec([...new Set([...rec.split("\n"), ...r.users.map((u: any) => String(u.id))].filter(Boolean))].join("\n")); toast.push(`Найдено: ${r.users.length}`); }
          else toast.push("Нет сообщений боту", false);
        } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
      }}>Получить chat_id</button>
    </Modal>
  );
}

function JitsiModal({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const toast = useToast();
  return (
    <Modal title="Jitsi-домены (рассылка на все ноды)" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={async () => {
          const domains = text.split("\n").map((d) => d.trim()).filter(Boolean);
          try { const r = await apiPost("/api/jitsi-domains/broadcast", { domains }); toast.push(`Отправлено: ${r.sent}, ошибок: ${r.errors}`); onClose(); }
          catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
        }}>Сохранить всем нодам</button>
      </>}>
      <div className="field"><label>Домены (по одному в строке)</label>
        <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder="https://meet.example.org" /></div>
    </Modal>
  );
}

function CreateInstanceModal({ serverId, onClose, onCreated }: { serverId: number; onClose: () => void; onCreated: () => void }) {
  const [carrier, setCarrier] = useState("jitsi");
  const [transport, setTransport] = useState("datachannel");
  const toast = useToast();
  return (
    <Modal title="Новый инстанс на ноде" onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={async () => {
          try { await apiPost("/api/node/create-user", { server_id: serverId, carrier, transport }); toast.push("Создан"); onCreated(); }
          catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
        }}>Создать</button>
      </>}>
      <div className="field"><label>Сервис</label>
        <select value={carrier} onChange={(e) => { const c = e.target.value; setCarrier(c); if (!compatTransports(c).includes(transport)) setTransport(compatTransports(c)[0]); }}>
          {CARRIERS.map((c) => <option key={c}>{c}</option>)}
        </select></div>
      <div className="field"><label>Транспорт</label>
        <select value={transport} onChange={(e) => setTransport(e.target.value)}>
          {compatTransports(carrier).map((t) => <option key={t}>{t}</option>)}
        </select></div>
    </Modal>
  );
}

function InstanceEditModal({ serverId, user, domains, onClose, onSaved }: {
  serverId: number; user: VUser; domains: string; onClose: () => void; onSaved: () => void;
}) {
  // Preset fields built from the data feed — no separate get_user round trip.
  const [f, setF] = useState<Record<string, any>>(() => ({
    carrier: user.carrier, transport: user.transport,
    room_id: user.custom_room_id ?? "", jitsi_domain: user.jitsi_chosen_domain ?? "",
    wb_token: user.wb_token ?? "", auto_restart: !!user.auto_restart,
    max_session_duration: user.max_session_duration ?? "",
    ...Object.fromEntries((PARAM_FIELDS[user.transport] ?? []).map((p) => [p, user[p] ?? ""])),
  }));
  const toast = useToast();
  const set = (k: string, v: any) => setF((s) => ({ ...s, [k]: v }));
  const domainList = domains.split("\n").map((d) => d.trim()).filter(Boolean);
  const params = PARAM_FIELDS[f.transport] ?? [];
  const usingDomain = f.carrier === "jitsi" && !!f.jitsi_domain;

  const save = async () => {
    try {
      await apiPost("/api/node/set-user", {
        server_id: serverId, id: user.client_id, carrier: f.carrier, transport: f.transport,
        room_id: f.room_id, jitsi_domain: f.jitsi_domain, auto_restart: f.auto_restart,
        wb_token: f.wb_token, max_session_duration: f.max_session_duration,
        ...Object.fromEntries(params.map((p) => [p, f[p]])),
      });
      toast.push("Сохранено"); onSaved();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  return (
    <Modal title={`Инстанс ${user.client_id.slice(0, 6)}`} onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn" onClick={save}>Сохранить</button>
      </>}>
      <div className="field"><label>Сервис</label>
        <select value={f.carrier} onChange={(e) => { const c = e.target.value; set("carrier", c); if (!compatTransports(c).includes(f.transport)) set("transport", compatTransports(c)[0]); }}>
          {CARRIERS.map((c) => <option key={c}>{c}</option>)}</select></div>
      <div className="field"><label>Транспорт</label>
        <select value={f.transport} onChange={(e) => set("transport", e.target.value)}>
          {compatTransports(f.carrier).map((t) => <option key={t}>{t}</option>)}</select></div>
      {f.carrier === "jitsi" && domainList.length > 0 && (
        <div className="field"><label>Jitsi-домен (пусто = ручной Room ID)</label>
          <select value={f.jitsi_domain} onChange={(e) => set("jitsi_domain", e.target.value)}>
            <option value="">— ручной —</option>{domainList.map((d) => <option key={d}>{d}</option>)}</select></div>
      )}
      {!usingDomain && (
        <div className="field"><label>Room ID / URL</label>
          <input value={f.room_id} onChange={(e) => set("room_id", e.target.value)}
            placeholder={f.carrier === "telemost" ? "обязателен" : "авто, если пусто"} /></div>
      )}
      {f.carrier === "wbstream" && (
        <div className="field"><label>WB Token (owner-mode)</label>
          <input value={f.wb_token} onChange={(e) => set("wb_token", e.target.value)} placeholder="bearer-токен" /></div>
      )}
      {params.map((p) => (
        <div className="field" key={p}><label>{p}</label>
          <input value={f[p] ?? ""} onChange={(e) => set(p, e.target.value)} /></div>
      ))}
      <div className="field"><label>Макс. длительность сессии (напр. 6h)</label>
        <input value={f.max_session_duration} onChange={(e) => set("max_session_duration", e.target.value)} /></div>
      <Switch checked={!!f.auto_restart} onChange={(v) => set("auto_restart", v)} label="Автозапуск" />
    </Modal>
  );
}
