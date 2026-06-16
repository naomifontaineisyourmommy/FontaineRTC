import { useEffect, useState } from "react";
import { apiGet, clearToken, getRole } from "./api/client";
import { ApiError } from "./api/client";
import { Login } from "./pages/Login";
import { NodeDashboard } from "./pages/NodeDashboard";
import { AdminDashboard } from "./pages/AdminDashboard";
import { ThemeControls } from "./theme/ThemeControls";
import { useToast } from "./components/ui";

type Role = "node" | "admin";
type AuthState = "checking" | "needed" | "ok";

export default function App() {
  const [role, setRole] = useState<Role | null>(null);
  const [auth, setAuth] = useState<AuthState>("checking");
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

  if (!role) return <div className="empty">Подключение к серверу…</div>;
  if (auth === "checking") return <div className="empty">Загрузка…</div>;
  if (auth === "needed") return <Login onDone={() => setAuth("ok")} />;

  const logout = () => { clearToken(); setAuth("needed"); };

  return (
    <>
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">F</span> FontaineRTC
          <span className="role-pill">{role}</span>
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
