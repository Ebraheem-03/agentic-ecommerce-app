import { cn } from "@/lib/cn";

/**
 * Placeholder product image — a token-gradient swatch standing in for the real
 * asset pipeline (not yet wired). When `alt` is provided the swatch is a
 * meaningful `img` with that alt text (a11y A8); otherwise it is decorative.
 * `tone` is a Tailwind gradient pair from the catalogue fixture.
 */
export function ProductThumb({
  tone,
  alt,
  className,
  overlay,
  testId,
}: {
  tone?: string | null;
  alt?: string | null;
  className?: string;
  /** Optional badge text drawn over the swatch (e.g. "★ Picked"). */
  overlay?: string;
  /** Stable test anchor (e.g. `product-image` for the gallery hero). */
  testId?: string;
}): JSX.Element {
  const gradient = tone ?? "from-n-200 to-n-300";
  return (
    <div
      data-testid={testId}
      className={cn(
        "relative grid place-items-center overflow-hidden bg-gradient-to-br",
        gradient,
        className,
      )}
      role={alt ? "img" : undefined}
      aria-label={alt ?? undefined}
      aria-hidden={alt ? undefined : true}
    >
      {overlay ? (
        <span className="absolute left-3 top-3 rounded-full bg-n-900/70 px-2.5 py-1 text-caption font-medium text-white backdrop-blur-sm">
          {overlay}
        </span>
      ) : null}
    </div>
  );
}
