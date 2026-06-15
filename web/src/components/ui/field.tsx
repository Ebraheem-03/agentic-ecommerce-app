import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Lightweight form field helpers on Hearth tokens. We don't pull in
 * react-hook-form for the auth forms — native validation + controlled state is
 * the simpler correct fit (ADR-0035 leaves rhf optional). These compose the
 * shadcn `Label` / `Input` into an accessible field: the label is tied to the
 * control, the error is announced and referenced via `aria-describedby`.
 */

export function Field({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}): JSX.Element {
  return <div className={cn("flex flex-col gap-1.5", className)}>{children}</div>;
}

export function FieldHint({
  id,
  children,
}: {
  id?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <p id={id} className="text-caption text-text-muted">
      {children}
    </p>
  );
}

/**
 * Inline validation error. Renders nothing when there's no message. `id` ties
 * it to the field via `aria-describedby`; `role="alert"` announces it.
 */
export function FieldError({
  id,
  children,
  ...rest
}: {
  id?: string;
  children?: ReactNode;
} & Record<`data-${string}`, string>): JSX.Element | null {
  if (!children) return null;
  return (
    <p
      id={id}
      role="alert"
      className="flex items-center gap-1.5 text-caption font-medium text-error"
      {...rest}
    >
      {children}
    </p>
  );
}
