import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, sseUrl } from "../api/client";
import { copy, useToast } from "../components/ui";
import { WdttAddForm, WdttUsersTable, type WdttUser } from "../components/wdtt";
import { highlightLine } from "../lib/logHighlight";

interface WdttData {
  installed: boolean;
  active: boolean;
  version: string;
  main_password: string;
  users: WdttUser[];
}

function WdttLogView() {
  const [lines, setLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const es = new EventSource(sseUrl("/api/wdtt/logs/stream"));
    es.onmessage = (ev) => {
      setLoading(false);
      if (ev.data === ":ka") return;
      setLines((l) => [...l.slice(-1000), ev.data]);
    };
    return () => es.close();
  }, []);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [lines]);
  if (loading) {
    return (
      <div className="log" ref={box}>
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="sk-line" style={{ width: `${40 + ((i * 23) % 55)}%` }} />
        ))}
      </div>
    );
  }
  return (
    <div className="log" ref={box}
      dangerouslySetInnerHTML={{
        __html: lines.length ? lines.map(highlightLine).join("")
          : '<span class="faint">Логи WDTT появятся здесь…</span>',
      }} />
  );
}

export function WdttPanel() {
  const [d, setD] = useState<WdttData | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const refresh = useCallback(async () => {
    try { setD(await apiGet("/api/wdtt")); } catch { /* ignore */ }
  }, []);
  useEffect(() => { refresh(); const t = setInterval(refresh, 4000); return () => clearInterval(t); }, [refresh]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); toast.push(ok); refresh(); }
    catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  const addUser = async (p: { days: number; password: string; vk_hash: string }) => {
    try {
      const r = await apiPost("/api/wdtt/users/add", p);
      toast.push(`Добавлен: ${r.password}`);
      if (r.uri) { copy(r.uri); toast.push("Ссылка wdtt:// скопирована"); }
      refresh();
    } catch (e) { toast.push(e instanceof Error ? e.message : "Ошибка", false); }
  };

  if (!d) return <div className="empty">Загрузка…</div>;

  if (!d.installed) {
    return (
      <div className="empty">
        <p style={{ marginBottom: 14 }}>WDTT не установлен на этой ноде.</p>
        <button className="btn" disabled={busy} onClick={async () => {
          setBusy(true);
          await act(() => apiPost("/api/wdtt/install", {}), "Установка WDTT запущена");
          setBusy(false);
        }}>Установить WDTT</button>
      </div>
    );
  }

  return (
    <div className="wdtt-layout">
      <div>
        <div className="row-between" style={{ marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
          <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
            <span className={`badge ${d.active ? "badge-on" : "badge-off"}`}>
              {d.active ? "WDTT активен" : "WDTT не активен"}
            </span>
            {d.main_password && (
              <span className="muted">Главный пароль{" "}
                <span className="uri uri-copy" style={{ padding: "2px 6px" }}
                  title="Скопировать главный пароль"
                  onClick={() => { copy(d.main_password); toast.push("Главный пароль скопирован"); }}>
                  {d.main_password}
                </span>
              </span>
            )}
          </div>
          <a className="btn btn-ghost btn-sm" href={sseUrl("/api/wdtt/logs/download")}>⬇ Скачать логи</a>
        </div>

        <WdttAddForm onAdd={addUser} />
        <WdttUsersTable
          users={d.users}
          onToggle={(u) => act(() => apiPost("/api/wdtt/users/toggle",
            { password: u.password, deactivated: u.status !== "deactivated" }), "Готово")}
          onDelete={(u) => act(() => apiPost("/api/wdtt/users/delete", { password: u.password }), "Удалён")}
        />
      </div>
      <WdttLogView />
    </div>
  );
}
