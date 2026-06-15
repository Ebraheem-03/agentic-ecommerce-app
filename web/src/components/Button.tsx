/**
 * Back-compat re-export. The Button now lives in the shadcn-on-tokens primitive
 * layer (`@/components/ui/button`, ADR-0035). Existing imports of
 * `@/components/Button` continue to resolve here. Prefer importing from
 * `@/components/ui/button` in new code.
 */
export {
  Button,
  buttonVariants,
  type ButtonProps,
  type ButtonVariant,
  type ButtonSize,
} from "@/components/ui/button";
