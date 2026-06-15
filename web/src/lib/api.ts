import type {
  Envelope,
  ErrorBody,
  LoginRequest,
  RegisterRequest,
  SessionOut,
  UserOut,
} from "@/lib/api-types";

/**
 * Hearth API client.
 *
 * Talks the contract envelope (docs/api/contract-v0.md §1.1/§1.2): every 2xx is
 * `{ data, meta }`; every 4xx/5xx is `{ error: { code, message, details } }`.
 * Auth is an opaque server-side session token sent as `Authorization: Bearer`.
 *
 * Token persistence (documented choice): the token is stored in an **httpOnly
 * cookie** set by our own Next.js route handlers (`/api/auth/*`), never in
 * localStorage. The browser never reads the token — it calls the same-origin
 * route handlers, which attach the Bearer header server-side. This keeps the
 * token out of JS (XSS-safe), survives reload, and makes the client free of any
 * browser-storage assumption (per the test guidance).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

/** Thrown on any non-2xx; carries the canonical error body for the UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: ErrorBody;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function isErrorEnvelope(value: unknown): value is { error: ErrorBody } {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error: unknown }).error === "object"
  );
}

interface RequestOptions {
  method?: string;
  /** Bearer token to attach server-side (route handlers pass it from cookie). */
  token?: string | null;
  body?: unknown;
  /** Forwarded to fetch (e.g. `cache: "no-store"` from server components). */
  init?: Omit<RequestInit, "method" | "body" | "headers">;
}

/**
 * Low-level call against the real backend. Returns the unwrapped `data`.
 * Used by server-side code (route handlers, server components) that holds the
 * token. The browser does NOT call this directly — it goes through `/api/*`.
 */
export async function apiFetch<T>(
  path: string,
  { method = "GET", token, body, init }: RequestOptions = {},
): Promise<Envelope<T>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    ...init,
  });

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!res.ok) {
    if (isErrorEnvelope(payload)) {
      throw new ApiError(res.status, payload.error);
    }
    throw new ApiError(res.status, {
      code: "internal_error",
      message: `Request failed (${res.status}).`,
      details: null,
    });
  }

  return payload as Envelope<T>;
}

/** Typed auth operations against the backend (server-side). */
export const authApi = {
  register(body: RegisterRequest): Promise<Envelope<SessionOut>> {
    return apiFetch<SessionOut>("/auth/register", { method: "POST", body });
  },
  login(body: LoginRequest): Promise<Envelope<SessionOut>> {
    return apiFetch<SessionOut>("/auth/login", { method: "POST", body });
  },
  logout(token: string): Promise<Envelope<{ revoked: boolean }>> {
    return apiFetch<{ revoked: boolean }>("/auth/logout", {
      method: "POST",
      token,
    });
  },
  me(token: string): Promise<Envelope<UserOut>> {
    return apiFetch<UserOut>("/auth/me", { method: "GET", token });
  },
};
