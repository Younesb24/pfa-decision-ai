/* ─── Auth client + token store ───
 *
 * Token lives in localStorage under PFA_TOKEN_KEY. We deliberately avoid
 * Server Components for this because the token is per-tab/user — passing it
 * through cookies would unlock SSR but adds CSRF surface area we don't need
 * for a demo. The login page redirects to "/" on success.
 *
 * Roles are a string union; runtime guards in the API are the source of
 * truth, the client just decides what UI to render.
 */

export type Role = "admin" | "ops" | "analyst" | "viewer";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  role: Role;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

const TOKEN_KEY = "pfa.access_token";
const USER_KEY = "pfa.user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: AuthUser): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let detail = `Login failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Role hierarchy mirror — kept in sync with services/auth.py. */
const LEVEL: Record<Role, number> = { viewer: 0, analyst: 1, ops: 2, admin: 3 };

export function hasRole(user: AuthUser | null, min: Role): boolean {
  if (!user) return false;
  return LEVEL[user.role] >= LEVEL[min];
}
