import type { SVGProps } from "react";

/** Small shared icon set for the shell, ported from the hi-fi screens. */

export function SearchIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function CartIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M6 7h13l-1.2 9.5a2 2 0 0 1-2 1.7H9.2a2 2 0 0 1-2-1.7L6 7Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path d="M9 7a3 3 0 0 1 6 0" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

export function MenuIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M4 7h16M4 12h16M4 17h16"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
