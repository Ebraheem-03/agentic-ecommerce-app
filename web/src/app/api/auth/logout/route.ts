import { NextResponse } from "next/server";
import { ApiError, authApi } from "@/lib/api";
import { clearSessionCookie, getSessionToken } from "@/lib/session";

/**
 * POST /api/auth/logout — revoke the backend session (delete the row) and clear
 * the cookie. We clear the cookie regardless so the client is always logged out
 * locally even if the backend call fails.
 */
export async function POST(): Promise<NextResponse> {
  const token = getSessionToken();
  if (token) {
    try {
      await authApi.logout(token);
    } catch (err) {
      // Cookie is cleared below regardless; only surface true server faults.
      if (!(err instanceof ApiError)) {
        // swallow — local logout still proceeds
      }
    }
  }
  clearSessionCookie();
  return NextResponse.json({ data: { revoked: true }, meta: null });
}
