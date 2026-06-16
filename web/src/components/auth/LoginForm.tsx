"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Field, FieldError } from "@/components/ui/field";
import type { ErrorEnvelope } from "@/lib/api-types";
import { validateEmail, validatePassword } from "@/lib/validation";

interface FieldErrors {
  email?: string;
  password?: string;
}

/**
 * Sign-in form. Client-side validation gates the submit; on submit it POSTs to
 * the `/api/auth/login` route handler (which sets the httpOnly session cookie),
 * then navigates home and refreshes server components so the shell reflects the
 * signed-in state. Errors map the canonical `{error}` envelope to a friendly
 * form-level message; `unauthenticated` is surfaced as bad credentials.
 */
export function LoginForm(): JSX.Element {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: FieldErrors = {
      email: validateEmail(email) ?? undefined,
      password: password ? undefined : "Enter your password.",
    };
    setErrors(next);
    return !next.email && !next.password;
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (res.ok) {
        router.push("/");
        router.refresh();
        return;
      }
      const body = (await res.json()) as ErrorEnvelope;
      const code = body.error?.code;
      setFormError(
        code === "unauthenticated"
          ? "Email or password is incorrect."
          : code === "forbidden"
            ? "Please verify your email before signing in."
            : (body.error?.message ?? "Sign-in failed. Please try again."),
      );
    } catch {
      setFormError("Could not reach Hearth. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      data-testid="login-form"
      noValidate
      onSubmit={onSubmit}
      className="flex flex-col gap-5"
    >
      {formError ? (
        <p
          role="alert"
          data-testid="login-error"
          className="rounded-lg border border-error/30 bg-error-tint px-3.5 py-2.5 text-small font-medium text-[#8f2a25]"
        >
          {formError}
        </p>
      ) : null}

      <Field>
        <Label htmlFor="login-email">Email</Label>
        <Input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "login-email-error" : undefined}
          data-testid="login-email"
        />
        <FieldError id="login-email-error">{errors.email}</FieldError>
      </Field>

      <Field>
        <Label htmlFor="login-password">Password</Label>
        <Input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? "login-password-error" : undefined}
          data-testid="login-password"
        />
        <FieldError id="login-password-error">{errors.password}</FieldError>
      </Field>

      <Button
        type="submit"
        variant="brand"
        size="lg"
        disabled={submitting}
        data-testid="login-submit"
        className="mt-1 w-full"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
