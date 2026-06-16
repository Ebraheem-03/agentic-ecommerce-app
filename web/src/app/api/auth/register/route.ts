import { NextResponse } from "next/server";
import { ApiError, authApi } from "@/lib/api";
import { setSessionCookie } from "@/lib/session";
import type { RegisterRequest } from "@/lib/api-types";

/**
 * POST /api/auth/register — proxies the contract `/auth/register`. The backend
 * returns a session (the persona is seeded verified), so we set the cookie and
 * the new account is signed in.
 */
export async function POST(request: Request): Promise<NextResponse> {
  let body: RegisterRequest;
  try {
    body = (await request.json()) as RegisterRequest;
  } catch {
    return NextResponse.json(
      { error: { code: "validation_error", message: "Invalid request body.", details: null } },
      { status: 422 },
    );
  }

  try {
    const { data } = await authApi.register(body);
    setSessionCookie(data.token, data.expires_at);
    return NextResponse.json({ data: { user: data.user }, meta: null }, { status: 201 });
  } catch (err) {
    if (err instanceof ApiError) {
      return NextResponse.json({ error: err.body }, { status: err.status });
    }
    return NextResponse.json(
      { error: { code: "internal_error", message: "Sign-up failed.", details: null } },
      { status: 502 },
    );
  }
}
