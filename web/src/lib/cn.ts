import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * `cn` — the standard shadcn class merger. `clsx` resolves conditionals and
 * `tailwind-merge` collapses conflicting Tailwind utilities so a caller's
 * `className` always wins over a primitive's defaults.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
