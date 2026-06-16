/** Backend API client. Auth via X-Token header (stored in sessionStorage). */

const TOKEN_KEY = "fontaine.token";

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t: string): void {
  sessionStorage.setItem(TOKEN_KEY, t);
}
export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const t = getToken();
  if (t) h["X-Token"] = t;
  return h;
}

async function parse(res: Response): Promise<any> {
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { error: text };
  }
  if (!res.ok || (data && data.error)) {
    throw new ApiError(res.status, (data && data.error) || `HTTP ${res.status}`);
  }
  return data;
}

export async function apiGet(path: string): Promise<any> {
  return parse(await fetch(path, { headers: headers(false) }));
}

export async function apiPost(path: string, body?: unknown): Promise<any> {
  return parse(
    await fetch(path, {
      method: "POST",
      headers: headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

/** Health probe — returns the backend role. */
export async function getRole(): Promise<"node" | "admin"> {
  const r = await fetch("/healthz");
  const d = await r.json();
  return d.role;
}

/** Login; empty password panels return an empty token (still "logged in"). */
export async function login(password: string): Promise<void> {
  const d = await apiPost("/api/login", { password });
  setToken(d.token || "");
}

/** EventSource URL carrying the token as a query param (EventSource has no headers). */
export function sseUrl(path: string): string {
  const t = getToken();
  return t ? `${path}?token=${encodeURIComponent(t)}` : path;
}
