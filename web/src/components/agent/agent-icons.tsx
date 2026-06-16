import type { SVGProps } from "react";

/** Icon set for the Ember concierge surface, ported from the hi-fi screens. */

export function EmberMark(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 64 64" aria-hidden="true" {...props}>
      <path
        d="M32 12 L50 23 C51.6 23.9,51.6 26.1,50 27 L33 37 C32.4 37.4,31.6 37.4,31 37 L14 27 C12.4 26.1,12.4 23.9,14 23 Z"
        fill="currentColor"
      />
      <path
        d="M32 30 L46 38.5 C47.4 39.3,47.4 41.2,46 42 L33 50 C32.4 50.4,31.6 50.4,31 50 L18 42 C16.6 41.2,16.6 39.3,18 38.5 Z"
        fill="currentColor"
        opacity=".5"
      />
    </svg>
  );
}

export function SendIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CitationIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M9 12h6M9 16h6M7 4h7l4 4v12H7z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CloseIcon(props: SVGProps<SVGSVGElement>): JSX.Element {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
      <path
        d="M6 6l12 12M18 6 6 18"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
