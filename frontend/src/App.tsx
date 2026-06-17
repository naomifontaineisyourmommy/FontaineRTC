import { useEffect, useRef, useState } from "react";
import { apiGet, clearToken, getRole } from "./api/client";
import { ApiError } from "./api/client";
import { Login } from "./pages/Login";
import { NodeDashboard } from "./pages/NodeDashboard";
import { AdminDashboard } from "./pages/AdminDashboard";
import { ThemeControls } from "./theme/ThemeControls";
import { UpdateOverlay, useToast } from "./components/ui";

type Role = "node" | "admin";
type AuthState = "checking" | "needed" | "ok";

interface UpdState { show: boolean; step: string; index: number; total: number; error: string; }
const NO_UPD: UpdState = { show: false, step: "", index: 0, total: 4, error: "" };

export default function App() {
  const [role, setRole] = useState<Role | null>(null);
  const [auth, setAuth] = useState<AuthState>("checking");
  const [upd, setUpd] = useState<UpdState>(NO_UPD);
  const [version, setVersion] = useState("");
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

  // version + "update available" check, once on open
  useEffect(() => {
    fetch("/api/version")
      .then((r) => r.json())
      .then((d) => {
        setVersion(d.current || "");
        if (d.update_available) toast.push("Доступно обновление");
      })
      .catch(() => {});
  }, [toast]);

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
          // update finished and the service is back up — reload to get new assets
          window.location.reload();
        }
      } catch {
        // server unreachable (likely restarting) — keep the overlay if we were updating
        if (wasUpdating.current) setUpd((u) => ({ ...u, show: true }));
      }
    };
    tick();
    const t = setInterval(tick, 1500);
    return () => clearInterval(t);
  }, []);

  const overlay = upd.show ? (
    <UpdateOverlay step={upd.step} index={upd.index} total={upd.total} error={upd.error}
      onClose={() => setUpd(NO_UPD)} />
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
            {version && <span className="version">{version}</span>}
          </div>
          <div className="hdr-actions">
            <ThemeControls onToast={(m, ok) => toast.push(m, ok)} />
            <button className="btn btn-ghost" onClick={logout}>Выйти</button>
          </div>
        </header>
        {role === "node" ? <NodeDashboard /> : <AdminDashboard />}
      </>
    );
  }

  return <>{overlay}{content}</>;
}
