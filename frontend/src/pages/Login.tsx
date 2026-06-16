import { useState } from "react";
import { login } from "../api/client";
import { useToast } from "../components/ui";

export function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(pw);
      onDone();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Ошибка входа", false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="logo" style={{ marginBottom: 16 }}>
          <span className="logo-icon">F</span> FontaineRTC
        </div>
        <div className="field">
          <label>Пароль панели</label>
          <input
            type="password"
            value={pw}
            autoFocus
            onChange={(e) => setPw(e.target.value)}
            placeholder="••••••••"
          />
        </div>
        <button className="btn" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
