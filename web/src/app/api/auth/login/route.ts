import { NextResponse } from "next/server";
import { ApiError, authApi } from "@/lib/api";
import { setSessionCookie } from "@/lib/session";
import type { LoginRequest } from "@/lib/api-types";

/**
 * POST /api/auth/login — proxies the contract `/auth/login`, then stores the
 * returned opaque token in an httpOnly cookie. The client only sees `{ user }`.
 */
export async function POST(request: Request): Promise<NextResponse> {
  let body: LoginRequest;
  try {
    body = (await request.json()) as LoginRequest;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  try {
    const { data } = await authApi.login(body);
    setSessionCookie(data.token, data.expires_at);
    return NextResponse.json({ data: { user: data.user }, meta: null });
  } catch (err) {
    if (err instanceof ApiError) {
      return NextResponse.json({ error: err.body }, { status: err.status });
    }
    return NextResponse.json(
      { error: { code: "internal_error", message: "Sign-in failed.", details: null } },
      { status: 502 },
    );
  }
}
