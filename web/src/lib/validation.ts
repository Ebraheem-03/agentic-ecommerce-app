/** Tiny client-side validators for the auth forms. Mirrors the server's rules
 * loosely; the server (`extra="forbid"`, real checks) remains authoritative. */

export function validateEmail(value: string): string | null {
  const v = value.trim();
  if (!v) return "Enter your email address.";
  // Pragmatic email shape check; the server does the real validation.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return "Enter a valid email address.";
  return null;
}

export function validatePassword(value: string, min = 8): string | null {
  if (!value) return "Enter a password.";
  if (value.length < min) return `Use at least ${min} characters.`;
  return null;
}

export function validateRequired(value: string, label: string): string | null {
  if (!value.trim()) return `${label} is required.`;
  return null;
}
