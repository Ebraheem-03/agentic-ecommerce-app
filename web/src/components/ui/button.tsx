import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/**
 * Hearth Button — shadcn pattern (Radix `Slot` + `cva`) on Hearth tokens.
 *
 * Variants follow the §5 accessibility math in docs/brand/palette-and-type.md:
 *  - `primary` (default): --accent (Ember) fill with DARK INK (--n-900, #1b1611
 *    in both themes). White-on-ember fails AA (2.7:1); dark-ink-on-ember passes
 *    AA+AAA (6.7:1). This is the canonical CTA / agent voice.
 *  - `brand`: --brand (Clay) fill with white (--on-brand, 5.0:1 in BOTH themes —
 *    Clay is too dark for the dark-theme ink-on-fill that suits Ember). Non-agent
 *    primary action.
 *  - `secondary`: outlined neutral surface, lower emphasis.
 *  - `ghost`: text-only.
 *
 * `asChild` renders the styles onto the child (e.g. a Next `<Link>`) via Slot.
 */
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium " +
    "select-none whitespace-nowrap " +
    "transition-[background-color,border-color,color,box-shadow] duration-150 " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand " +
    "focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
    "disabled:cursor-not-allowed disabled:opacity-50 " +
    "motion-reduce:transition-none",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-n-900 hover:bg-accent-strong disabled:hover:bg-accent",
        brand:
          "bg-brand text-on-brand hover:bg-brand-strong disabled:hover:bg-brand",
        secondary:
          "bg-surface text-text border border-border hover:bg-surface-muted " +
          "hover:border-n-300 disabled:hover:bg-surface disabled:hover:border-border",
        ghost:
          "bg-transparent text-text hover:bg-surface-muted disabled:hover:bg-transparent",
      },
      size: {
        sm: "h-9 px-3.5 text-small",
        md: "h-11 px-5 text-body",
        lg: "h-12 px-6 text-body-lg",
        icon: "h-11 w-11",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonVariant = NonNullable<
  VariantProps<typeof buttonVariants>["variant"]
>;
export type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    /** Render styles onto the child element (e.g. a link) instead of a button. */
    asChild?: boolean;
  };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        // Slot forwards type to its child; a native button defaults to "button".
        type={asChild ? type : (type ?? "button")}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
