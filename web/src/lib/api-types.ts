/**
 * Typed shapes for the Hearth API contract (docs/api/contract-v0.md).
 * snake_case is preserved on the wire; we keep it on the types so the client is
 * a 1:1 mirror of the contract and there's no hidden casing transform to drift.
 */

/** §1.1 — success envelope. `meta` is `null` for single-resource responses. */
export interface PageMeta {
  next_cursor: string | null;
  limit: number;
  total: number | null;
}

export interface Envelope<T> {
  data: T;
  meta: PageMeta | null;
}

/** §1.2 — canonical error body. `code` is a closed set in the contract. */
export type ErrorCode =
  | "validation_error"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "cart_already_open"
  | "duplicate_review"
  | "email_taken"
  | "out_of_stock"
  | "return_window_closed"
  | "empty_cart"
  | "payment_declined"
  | "rate_limited"
  | "internal_error"
  | "not_implemented";

export interface ErrorBody {
  code: ErrorCode;
  message: string;
  details: unknown | null;
}

export interface ErrorEnvelope {
  error: ErrorBody;
}

/** auth — §2. Roles per the ORM/journeys. */
export type UserRole = "buyer" | "seller" | "support" | "admin";

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  email_verified: boolean;
  created_at: string;
}

/** `SessionOut` — returned by register/login; carries the opaque bearer token. */
export interface SessionOut {
  token: string;
  expires_at: string;
  user: UserOut;
}

export interface LogoutResult {
  revoked: boolean;
}

/** Request bodies — `extra="forbid"` server-side, so keep these exact. */
export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
  role: Extract<UserRole, "buyer" | "seller">;
}

export interface LoginRequest {
  email: string;
  password: string;
}
