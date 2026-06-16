import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

/**
 * Hearth text input — shadcn primitive on Hearth tokens. Mirrors the hi-fi
 * `.input` (screens.css): surface fill, border, ember focus ring. The
 * `aria-invalid` state paints the error border so forms can drive it from
 * validation without a separate class.
 */
export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "flex h-11 w-full rounded-lg border border-border bg-surface px-3.5 " +
            "text-body text-text placeholder:text-n-400 " +
            "transition-[border-color,box-shadow] duration-150 " +
            "focus-visible:outline-none focus-visible:border-accent-strong " +
            "focus-visible:ring-2 focus-visible:ring-accent-strong/40 " +
            "disabled:cursor-not-allowed disabled:opacity-50 " +
            "aria-[invalid=true]:border-error " +
            "aria-[invalid=true]:focus-visible:border-error " +
            "aria-[invalid=true]:focus-visible:ring-error/40",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";
