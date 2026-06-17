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

// Base for resolving OG/canonical URLs. Override in prod via NEXT_PUBLIC_SITE_URL.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Hearth — Agentic AI Commerce",
    template: "%s · Hearth",
  },
  description:
    "A concierge agentic-commerce demo. Tell Ember what you're furnishing, gifting, or mending — recommendations come with reasons. Warm, crafted, and accessible.",
  applicationName: "Hearth",
  keywords: ["handmade", "agentic commerce", "AI concierge", "makers", "marketplace"],
  openGraph: {
    type: "website",
    siteName: "Hearth",
    title: "Hearth — the hearth for well-made things",
    description:
      "Shoppable by conversation. Ember knows every maker in the catalogue and recommends with reasons — never hype.",
    url: siteUrl,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Hearth — Agentic AI Commerce",
    description:
      "A concierge agentic-commerce demo. Recommendations with reasons, from real makers.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#b5512f",
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
