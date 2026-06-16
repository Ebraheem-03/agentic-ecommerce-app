import { cn } from "@/lib/cn";
import type { StockState } from "@/lib/api-types";

/**
 * Token-truthful stock pill — mirrors the hi-fi `.badge badge-success/-warning`.
 * Conveys state with BOTH a colour and a label (not colour alone) for a11y.
 */
const COPY: Record<StockState, { label: string; tone: string; dot: string }> = {
  in_stock: {
    label: "In stock",
    tone: "bg-success-tint text-[#2c5b41]",
    dot: "bg-success",
  },
  low_stock: {
    label: "Low stock",
    tone: "bg-warning-tint text-[#7a560f]",
    dot: "bg-warning",
  },
  out_of_stock: {
    label: "Sold out",
    tone: "bg-error-tint text-[#8a2f24]",
    dot: "bg-error",
  },
};

export function StockBadge({
  stock,
  className,
}: {
  stock: StockState;
  className?: string;
}): JSX.Element {
  const { label, tone, dot } = COPY[stock];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-caption font-medium",
        tone,
        className,
      )}
    >
      <span className={cn("inline-block h-[7px] w-[7px] rounded-full", dot)} aria-hidden="true" />
      {label}
    </span>
  );
}
