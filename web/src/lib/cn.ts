import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Hearth's type scale uses NAMED font-size tokens (`text-small`, `text-body`,
 * `text-h1`, …) rather than Tailwind's t-shirt sizes. tailwind-merge doesn't know
 * these are font sizes, so by default it buckets `text-small` with the
 * `text-{color}` group — which makes it CONFLICT with our color utilities
 * (`text-on-brand`, `text-n-900`, …) and silently drop whichever comes first.
 * That dropped the foreground color off every sized Button (e.g. the Clay `brand`
 * CTA fell back to inherited ink → a 3.57:1 contrast failure).
 *
 * Registering the named sizes in the `font-size` group separates them from
 * `text-color`, so a Button can carry BOTH `text-small` and `text-on-brand`.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        {
          text: [
            "display",
            "h1",
            "h2",
            "h3",
            "h4",
            "body-lg",
            "body",
            "small",
            "caption",
          ],
        },
      ],
    },
  },
});

/**
 * `cn` — the standard shadcn class merger. `clsx` resolves conditionals and
 * `tailwind-merge` collapses conflicting Tailwind utilities so a caller's
 * `className` always wins over a primitive's defaults.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
