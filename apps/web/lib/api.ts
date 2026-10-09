// Thin client for the MME OS API. The session lives in an httpOnly cookie set by the API;
// the CSRF token comes from /me and is sent on every write.

// Production serves the API on the same domain under /api, so the default there is a relative URL.
const ORIGIN = process.env.NEXT_PUBLIC_API_ORIGIN ?? (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");
export const API = ORIGIN + "/api/v1";

export type Scope = "own" | "team" | "department" | "all";

export interface Me {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  is_super_admin: boolean;
  roles: { key: string; name: string }[];
  team_ids: string[];
  department_id: string | null;
  mfa: { required: boolean; enrolled: boolean; passed: boolean };
  permissions: Record<string, Scope>;
  csrf_token: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public mfaRequired = false) {
    super(message);
  }
}

let csrf: string | null = null;
export const setCsrf = (token: string) => { csrf = token; };

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (method !== "GET" && csrf) headers["x-csrf-token"] = csrf;
  const res = await fetch(API + path, { method, headers, credentials: "include", body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let message = "Something went wrong. Try again.";
    try {
      const data = await res.json();
      message = data?.detail?.[0]?.msg || data?.detail || data?.error?.message || message;
    } catch { /* keep default */ }
    throw new ApiError(res.status, typeof message === "string" ? message : "Request failed.", res.headers.get("x-mfa-required") === "1");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(p: string) => call<T>("GET", p),
  post: <T>(p: string, b?: unknown) => call<T>("POST", p, b ?? {}),
  put: <T>(p: string, b?: unknown) => call<T>("PUT", p, b ?? {}),
  patch: <T>(p: string, b?: unknown) => call<T>("PATCH", p, b ?? {}),
  del: <T>(p: string) => call<T>("DELETE", p),
};

// UI hint only: the server computed `permissions` with the same engine that enforces every request.
export const can = (me: Me | null, permission: string) => !!me && permission in me.permissions;

export const googleSignInUrl = (next = "/", invite?: string | null) =>
  `${API}/auth/google/start?next=${encodeURIComponent(next)}${invite ? `&invite=${encodeURIComponent(invite)}` : ""}`;
