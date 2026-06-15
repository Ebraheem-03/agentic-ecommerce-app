import { ApiError, authApi } from "@/lib/api";
import { getSessionToken } from "@/lib/session";
import type { UserOut } from "@/lib/api-types";

/**
 * Resolve the signed-in user for server components (the nav auth slot). Returns
 * null when there's no session or the token is rejected/expired. Network faults
 * also resolve to null so the shell renders the signed-out state rather than
 * erroring the whole page when the backend is unreachable.
 */
export async function getCurrentUser(): Promise<UserOut | null> {
  const token = getSessionToken();
  if (!token) return null;
  try {
    const { data } = await authApi.me(token);
    return data;
  } catch (err) {
    if (err instanceof ApiError) return null;
    return null;
  }
}
