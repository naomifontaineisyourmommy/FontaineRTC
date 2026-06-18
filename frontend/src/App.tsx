import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, clearToken, getRole } from "./api/client";
import { ApiError } from "./api/client";
import { Login } from "./pages/Login";
import { NodeDashboard } from "./pages/NodeDashboard";
import { AdminDashboard } from "./pages/AdminDashboard";
import { ThemeControls } from "./theme/ThemeControls";
import { ErrorBoundary, Modal, ModeToggle, UpdateOverlay, useToast } from "./components/ui";

type Role = "node" | "admin";
type AuthState = "checking" | "needed" | "ok";

interface UpdState { show: boolean; step: string; index: number; total: number; error: string; }
const NO_UPD: UpdState = { show: false, step: "", index: 0, total: 4, error: "" };

interface Ver { current: string; latest: string; binary: string; binary_latest: string; wdtt: string; }

export default function App() {
  const [role, setRole] = useState<Role | null>(null);
  const [auth, setAuth] = useState<AuthState>("checking");
  const [upd, setUpd] = useState<UpdState>(NO_UPD);
  const [ver, setVer] = useState<Ver>({ current: "", latest: "", binary: "", binary_latest: "", wdtt: "" });
  const [prompt, setPrompt] = useState(false);
  const [nodeMode, setNodeMode] = useState<"olcrtc" | "wdtt">("olcrtc");
  const wasUpdating = useRef(false);
  const toast = useToast();

  const probe = async (r: Role) => {
    try {
      await apiGet(r === "node" ? "/api/status" : "/api/data");
      setAuth("ok");
    } catch (e) {
      setAuth(e instanceof ApiError && e.status === 401 ? "needed" : "ok");
    }
  };

  useEffect(() => {
    getRole()
      .then((r) => { setRole(r); return probe(r); })
      .catch(() => setRole(null));
  }, []);

  // One-time version check on page load — prompt with a modal if behind.
  useEffect(() => {
    fetch("/api/version")
      .then((r) => r.json())
      .then((d) => {
        setVer({
          current: d.current || "", latest: d.latest || "",
          binary: d.binary || "", binary_latest: d.binary_latest || "",
          wdtt: (d.wdtt && d.wdtt.version) || "",
        });
        if (d.update_available) setPrompt(true);
      })
      .catch(() => {});
  }, []);

  // Poll update status — also catches updates triggered externally via the API
  // (the node case, when the admin panel pushes update_panel).
  useEffect(() => {
    const tick = async () => {
      try {
        const r = await fetch("/api/updating");
        const d = await r.json();
        if (d.updating) {
          wasUpdating.current = true;
          setUpd({ show: true, step: d.step, index: d.index, total: d.total, error: "" });
        } else if (d.error) {
          wasUpdating.current = false;
          setUpd((u) => ({ ...u, show: true, error: d.error }));
        } else if (wasUpdating.current) {
          window.location.reload();
        }
      } catch {
        if (wasUpdating.current) setUpd((u) => ({ ...u, show: true }));
      }
    };
    tick();
    const t = setInterval(tick, 1500);
    return () => clearInterval(t);
  }, []);

  const startUpdate = async () => {
    setPrompt(false);
    try {
      const r = await apiPost("/api/update");
      if (r.up_to_date) toast.push("Последняя версия уже установлена");
      // otherwise the overlay appears via the /api/updating poll
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Ошибка", false);
    }
  };

  const overlay = upd.show ? (
    <UpdateOverlay step={upd.step} index={upd.index} total={upd.total} error={upd.error}
      onClose={() => setUpd(NO_UPD)} />
  ) : null;

  const updatePrompt = (prompt && !upd.show) ? (
    <Modal title="Доступно обновление" onClose={() => setPrompt(false)}
      footer={<>
        <button className="btn btn-ghost" onClick={() => setPrompt(false)}>Закрыть</button>
        <button className="btn" onClick={startUpdate}>Обновить</button>
      </>}>
      <p className="muted" style={{ marginBottom: 12 }}>Доступна новая версия. Обновить сейчас?</p>
      {ver.current !== ver.latest && ver.latest && (
        <div className="row-between" style={{ marginBottom: 6 }}>
          <span className="muted">FontaineRTC</span>
          <span><code>{ver.current}</code> → <code>{ver.latest}</code></span>
        </div>
      )}
      {ver.binary && ver.binary_latest && ver.binary !== ver.binary_latest && (
        <div className="row-between">
          <span className="muted">OlcRTC</span>
          <span><code>{ver.binary}</code> → <code>{ver.binary_latest}</code></span>
        </div>
      )}
    </Modal>
  ) : null;

  let content;
  if (!role) content = <div className="empty">Подключение к серверу…</div>;
  else if (auth === "checking") content = <div className="empty">Загрузка…</div>;
  else if (auth === "needed") content = <Login onDone={() => setAuth("ok")} />;
  else {
    const logout = () => { clearToken(); setAuth("needed"); };
    content = (
      <>
        <header className="app-header">
          <div className="logo">
            <img className="logo-avatar" src="/naomi.jpg" alt="" /> FontaineRTC
            <span className="role-pill">{role}</span>
            {ver.current && <span className="version" title="Версия FontaineRTC">{ver.current}</span>}
            {ver.binary && <span className="version" title="Версия OlcRTC-AdvancedInteractive">{ver.binary}</span>}
            {role === "node" && ver.wdtt && <span className="version" title="Версия WDTT">{ver.wdtt}</span>}
            {role === "node" && (
              <button className="btn btn-ghost btn-sm" style={{ marginLeft: 6 }} onClick={startUpdate}>↺ Обновить</button>
            )}
            {role === "node" && (
              <ModeToggle value={nodeMode}
                options={[{ id: "olcrtc", label: "olcrtc" }, { id: "wdtt", label: "wdtt" }]}
                onChange={(v) => setNodeMode(v as "olcrtc" | "wdtt")} />
            )}
          </div>
          <div className="hdr-actions">
            <ThemeControls onToast={(m, ok) => toast.push(m, ok)} />
            <button className="btn btn-ghost" onClick={logout}>Выйти</button>
          </div>
        </header>
        <ErrorBoundary key={role === "node" ? nodeMode : "admin"}>
          {role === "node" ? <NodeDashboard mode={nodeMode} /> : <AdminDashboard />}
        </ErrorBoundary>
      </>
    );
  }

  return <>{overlay}{updatePrompt}{content}</>;
}
