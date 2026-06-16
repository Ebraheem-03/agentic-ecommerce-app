"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Field, FieldError, FieldHint } from "@/components/ui/field";
import { cn } from "@/lib/cn";
import type { ErrorEnvelope, RegisterRequest } from "@/lib/api-types";
import {
  validateEmail,
  validatePassword,
  validateRequired,
} from "@/lib/validation";

type Role = RegisterRequest["role"];

interface FieldErrors {
  display_name?: string;
  email?: string;
  password?: string;
}

const ROLES: { value: Role; label: string; hint: string }[] = [
  { value: "buyer", label: "I'm here to shop", hint: "Discover makers and buy with the concierge." },
  { value: "seller", label: "I'm a maker", hint: "Open a shop and list your work." },
];

/**
 * Create-account form. Same flow as login: client validation → POST to
 * `/api/auth/register` (sets the session cookie; the seeded persona is verified)
 * → navigate + refresh. Role is a buyer/seller choice per the contract's
 * `RegisterRequest.role`.
 */
export function RegisterForm(): JSX.Element {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("buyer");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const next: FieldErrors = {
      display_name: validateRequired(displayName, "Name") ?? undefined,
      email: validateEmail(email) ?? undefined,
      password: validatePassword(password) ?? undefined,
    };
    setErrors(next);
    return !next.display_name && !next.email && !next.password;
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload: RegisterRequest = {
        display_name: displayName.trim(),
        email: email.trim(),
        password,
        role,
      };
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        router.push("/");
        router.refresh();
        return;
      }
      const body = (await res.json()) as ErrorEnvelope;
      const code = body.error?.code;
      if (code === "email_taken") {
        setErrors((prev) => ({ ...prev, email: "That email is already registered." }));
      } else {
        setFormError(body.error?.message ?? "Sign-up failed. Please try again.");
      }
    } catch {
      setFormError("Could not reach Hearth. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      data-testid="register-form"
      noValidate
      onSubmit={onSubmit}
      className="flex flex-col gap-5"
    >
      {formError ? (
        <p
          role="alert"
          data-testid="register-error"
          className="rounded-lg border border-error/30 bg-error-tint px-3.5 py-2.5 text-small font-medium text-[#8f2a25]"
        >
          {formError}
        </p>
      ) : null}

      <Field>
        <Label htmlFor="register-name">Name</Label>
        <Input
          id="register-name"
          name="display_name"
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          aria-invalid={errors.display_name ? true : undefined}
          aria-describedby={errors.display_name ? "register-name-error" : undefined}
          data-testid="register-name"
        />
        <FieldError id="register-name-error">{errors.display_name}</FieldError>
      </Field>

      <Field>
        <Label htmlFor="register-email">Email</Label>
        <Input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "register-email-error" : undefined}
          data-testid="register-email"
        />
        <FieldError id="register-email-error">{errors.email}</FieldError>
      </Field>

      <Field>
        <Label htmlFor="register-password">Password</Label>
        <Input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={
            errors.password ? "register-password-error" : "register-password-hint"
          }
          data-testid="register-password"
        />
        {errors.password ? (
          <FieldError id="register-password-error">{errors.password}</FieldError>
        ) : (
          <FieldHint id="register-password-hint">At least 8 characters.</FieldHint>
        )}
      </Field>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-small font-medium text-text">
          What brings you to Hearth?
        </legend>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {ROLES.map((r) => {
            const selected = role === r.value;
            return (
              <label
                key={r.value}
                className={cn(
                  "flex cursor-pointer flex-col gap-1 rounded-xl border p-3.5 transition-colors",
                  selected
                    ? "border-brand bg-brand-tint"
                    : "border-border bg-surface hover:bg-surface-muted",
                )}
              >
                <span className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="role"
                    value={r.value}
                    checked={selected}
                    onChange={() => setRole(r.value)}
                    className="h-4 w-4 accent-brand"
                    data-testid={`register-role-${r.value}`}
                  />
                  <span className="text-small font-medium text-text">{r.label}</span>
                </span>
                <span className="pl-6 text-caption text-text-muted">{r.hint}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <Button
        type="submit"
        variant="brand"
        size="lg"
        disabled={submitting}
        data-testid="register-submit"
        className="mt-1 w-full"
      >
        {submitting ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
