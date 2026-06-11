import type { SVGProps } from "react";

/**
 * Hearth logo mark — Concept 2 "Keystone".
 * Two interlocking rounded planes that nest like cupped hands / a sheltering wedge.
 *
 * Duotone per docs/brand/palette-and-type.md §1 hand-off:
 *   outer plane (the shelter)   → var(--brand)  (Clay)
 *   inner plane (the held thing) → var(--accent) (Ember)
 * The accent hue carries the separation, so the source SVG's opacity:0.45 is dropped.
 *
 * Geometry is a faithful port of docs/brand/assets/hearth-logo-mark.svg.
 */
export type HearthMarkProps = SVGProps<SVGSVGElement> & {
  /** Pixel size for the square mark. Defaults to 32. */
  size?: number;
  /** Accessible label; pass "" together with aria-hidden for decorative use. */
  title?: string;
};

export function HearthMark({
  size = 32,
  title = "Hearth",
  ...props
}: HearthMarkProps): JSX.Element {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      role="img"
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      {/* outer plane (the shelter) */}
      <path
        d="M32 8 L54 21 C56 22.2, 56 25, 54 26.2 L34 38 C32.8 38.7, 31.2 38.7, 30 38 L10 26.2 C8 25, 8 22.2, 10 21 Z"
        fill="var(--brand)"
      />
      {/* inner plane (the held thing) */}
      <path
        d="M32 28 L50 38.5 C52 39.7, 52 42.5, 50 43.7 L34 53 C32.8 53.7, 31.2 53.7, 30 53 L14 43.7 C12 42.5, 12 39.7, 14 38.5 Z"
        fill="var(--accent)"
      />
    </svg>
  );
}

/**
 * Lockup: mark + "Hearth" wordmark in Fraunces 600 (§6 wordmark treatment).
 * Wordmark color is var(--text); the mark owns the duotone.
 */
export type HearthLockupProps = {
  /** Mark height in px; wordmark scales relative to it. Defaults to 32. */
  size?: number;
  className?: string;
};

export function HearthLockup({
  size = 32,
  className,
}: HearthLockupProps): JSX.Element {
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", gap: "0.5em" }}
    >
      <HearthMark size={size} title="" />
      <span
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 600,
          fontSize: `${size * 0.85}px`,
          letterSpacing: "-0.01em",
          color: "var(--text)",
          lineHeight: 1,
        }}
      >
        Hearth
      </span>
    </span>
  );
}
