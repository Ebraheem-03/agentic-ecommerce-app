import { cookies } from "next/headers";
import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";

/**
 * Server-side session-token cookie helpers. The opaque bearer token from the
 * backend lives in an httpOnly cookie; nothing in the browser reads it. Route
 * handlers and server components use these to set / read / clear it.
 */
export const SESSION_COOKIE = "hearth_session";

const baseCookie: Partial<ResponseCookie> = {
  httpOnly: true,
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

/** Read the token in a server component / route handler (or null if absent). */
export function getSessionToken(): string | null {
  return cookies().get(SESSION_COOKIE)?.value ?? null;
}

/**
 * Persist the token. `expiresAt` is the contract's ISO expiry; we mirror it to
 * the cookie so the browser drops it in lockstep with the backend session.
 */
export function setSessionCookie(token: string, expiresAt: string): void {
  cookies().set(SESSION_COOKIE, token, {
    ...baseCookie,
    expires: new Date(expiresAt),
  });
}

/** Clear the token (logout / failed refresh). */
export function clearSessionCookie(): void {
  cookies().set(SESSION_COOKIE, "", { ...baseCookie, maxAge: 0 });
}
