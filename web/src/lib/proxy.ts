import { NextResponse } from "next/server";
import { ApiError } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import type { ErrorBody } from "@/lib/api-types";

/**
 * Shared helpers for the live `/api/*` proxy route handlers (Day-22 flip-to-live).
 * Each handler reads the httpOnly session token server-side, calls the backend
 * via `@/lib/api`, maps the wire shape → the FE view-model, and re-wraps the
 * canonical `{ data, meta }` / `{ error }` envelope. These helpers keep that
 * boilerplate in one place.
 */

/** 401 envelope when there's no session cookie. */
export function requireToken(): { token: string } | { response: NextResponse } {
  const token = getSessionToken();
  if (!token) {
    return {
      response: NextResponse.json(
        {
          error: {
            code: "unauthenticated",
            message: "Please sign in to continue.",
            details: null,
          } satisfies ErrorBody,
        },
        { status: 401 },
      ),
    };
  }
  return { token };
}

/** Turn a thrown backend error into the canonical error envelope response. */
export function toErrorResponse(err: unknown, fallback: string): NextResponse {
  if (err instanceof ApiError) {
    return NextResponse.json({ error: err.body }, { status: err.status });
  }
  return NextResponse.json(
    {
      error: {
        code: "internal_error",
        message: fallback,
        details: null,
      } satisfies ErrorBody,
    },
    { status: 502 },
  );
}

/** Parse a JSON request body, or return a 422 validation envelope on failure. */
export async function readJson<T>(
  request: Request,
): Promise<{ body: T } | { response: NextResponse }> {
  try {
    return { body: (await request.json()) as T };
  } catch {
    return {
      response: NextResponse.json(
        {
          error: {
            code: "validation_error",
            message: "Invalid request body.",
            details: null,
          } satisfies ErrorBody,
        },
        { status: 422 },
      ),
    };
  }
}
