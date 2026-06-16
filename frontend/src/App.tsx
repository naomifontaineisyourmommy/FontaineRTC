import { useQuery } from "@tanstack/react-query";

/**
 * FontaineRTC SPA shell.
 *
 * The same bundle serves both roles; it reads /healthz to learn whether the
 * backend is running as `node` or `admin` and renders the matching dashboard.
 * NodeDashboard / AdminDashboard are filled in during migration phase 4.
 */
function App() {
  const { data, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const r = await fetch("/healthz");
      return r.json() as Promise<{ ok: boolean; role: "node" | "admin" }>;
    },
  });

  if (isLoading) return <p style={{ fontFamily: "sans-serif" }}>Загрузка…</p>;

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>FontaineRTC</h1>
      <p>
        Роль бэкенда: <strong>{data?.role ?? "—"}</strong>
      </p>
      <p style={{ color: "#888" }}>
        Скелет фронтенда. Дашборды переносятся на этапе 4 (см. docs/MIGRATION.md).
      </p>
    </main>
  );
}

export default App;
