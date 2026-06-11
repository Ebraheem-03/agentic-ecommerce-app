import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * Hearth Button.
 *
 * Variants follow the §5 accessibility math in docs/brand/palette-and-type.md:
 *  - `primary` (default): --accent (Ember) fill with DARK INK (#1b1611). This is
 *    the canonical CTA and the agent's voice. White-on-ember fails AA (2.7:1);
 *    dark-ink-on-ember passes AA+AAA (6.7:1) in BOTH themes, so the ink is the
 *    fixed --n-900 token rather than the theme-dependent --text/--on-accent.
 *  - `brand`: --brand (Clay) fill with white (--on-accent passes at 5.0:1 in
 *    light; brand fill carries white on dark too). Use for non-agent primary
 *    actions.
 *  - `secondary`: outlined neutral surface for lower-emphasis actions.
 *  - `ghost`: text-only, no fill.
 */
export type ButtonVariant = "primary" | "brand" | "secondary" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
};

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium " +
  "select-none cursor-pointer whitespace-nowrap " +
  "transition-[background-color,border-color,color,box-shadow] duration-150 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
  "disabled:cursor-not-allowed disabled:opacity-50 " +
  "motion-reduce:transition-none";

const VARIANTS: Record<ButtonVariant, string> = {
  // Ember fill, dark ink. --n-900 is #1b1611 in both themes (the spec ink).
  primary:
    "bg-accent text-n-900 hover:bg-accent-strong " +
    "disabled:hover:bg-accent",
  // Clay fill, white ink.
  brand:
    "bg-brand text-on-accent hover:bg-brand-strong " +
    "disabled:hover:bg-brand",
  // Neutral outline.
  secondary:
    "bg-surface text-text border border-border " +
    "hover:bg-surface-muted hover:border-n-300 " +
    "disabled:hover:bg-surface disabled:hover:border-border",
  // Text only.
  ghost:
    "bg-transparent text-text hover:bg-surface-muted " +
    "disabled:hover:bg-transparent",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-9 px-3.5 text-small",
  md: "h-11 px-5 text-body",
  lg: "h-12 px-6 text-body-lg",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  children,
  ...props
}: ButtonProps): JSX.Element {
  const classes = [BASE, VARIANTS[variant], SIZES[size], className]
    .filter(Boolean)
    .join(" ");

  return (
    // eslint-disable-next-line react/button-has-type
    <button type={type} className={classes} {...props}>
      {children}
    </button>
  );
}
