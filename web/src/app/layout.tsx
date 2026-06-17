import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import "./globals.css";

// §6 — fonts are SELF-HOSTED (next/font/local) so the production `next build`
// never reaches out to fonts.gstatic.com (build-time fetch is blocked in the
// Docker/CI sandbox — see docs/STATUS.md). Variable woff2 files live in ./fonts;
// the CSS-variable contract (--font-fraunces / --font-outfit, consumed in
// globals.css) is unchanged.

// Fraunces (display/headings + wordmark): variable, used at 400 + 600.
const fraunces = localFont({
  src: "./fonts/fraunces-latin-standard-normal.woff2",
  weight: "400 600",
  display: "swap",
  variable: "--font-fraunces",
});

// Outfit (UI / body): variable, used at 400 + 500.
const outfit = localFont({
  src: "./fonts/outfit-latin-wght-normal.woff2",
  weight: "400 500",
  display: "swap",
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: "Hearth — Agentic AI Commerce",
  description: "A concierge agentic-commerce demo. Warm, crafted, and accessible.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="en" className={`${fraunces.variable} ${outfit.variable}`}>
      <body>{children}</body>
    </html>
  );
}
