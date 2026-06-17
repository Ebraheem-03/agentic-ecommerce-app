import { cn } from "@/lib/cn";

/**
 * Product image tile. When a real `src` is provided it renders an `<img>`
 * (lazy-loaded, `object-cover`) with the supplied `alt` text (a11y A8); the
 * `tone` gradient stays underneath as a graceful fallback while the asset loads
 * or when `src` is null (no real image yet). When neither `src` nor `alt` is
 * provided the tile is decorative.
 *
 * Images are remote (picsum/unsplash); we use a plain `<img>` rather than
 * `next/image` so the standalone server bundle needs no remote-loader config.
 */
export function ProductThumb({
  src,
  tone,
  alt,
  className,
  imgClassName,
  overlay,
  testId,
}: {
  /** Real product image URL (remote). null/undefined → tone-gradient fallback. */
  src?: string | null;
  tone?: string | null;
  alt?: string | null;
  className?: string;
  /** Extra classes on the `<img>` itself (e.g. `img-zoom` for hover scale). */
  imgClassName?: string;
  /** Optional badge text drawn over the swatch (e.g. "★ Picked"). */
  overlay?: string;
  /** Stable test anchor (e.g. `product-image` for the gallery hero). */
  testId?: string;
}): JSX.Element {
  const gradient = tone ?? "from-n-200 to-n-300";
  const hasImage = Boolean(src);
  return (
    <div
      data-testid={testId}
      className={cn(
        "relative grid place-items-center overflow-hidden bg-gradient-to-br",
        gradient,
        className,
      )}
      role={!hasImage && alt ? "img" : undefined}
      aria-label={!hasImage && alt ? alt : undefined}
      aria-hidden={!hasImage && !alt ? true : undefined}
    >
      {hasImage ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote asset; plain img keeps the standalone bundle loader-free
        <img
          src={src as string}
          alt={alt ?? ""}
          loading="lazy"
          decoding="async"
          className={cn(
            "absolute inset-0 h-full w-full object-cover",
            imgClassName,
          )}
        />
      ) : null}
      {overlay ? (
        <span className="absolute left-3 top-3 z-10 rounded-full bg-n-900/70 px-2.5 py-1 text-caption font-medium text-white backdrop-blur-sm">
          {overlay}
        </span>
      ) : null}
    </div>
  );
}
