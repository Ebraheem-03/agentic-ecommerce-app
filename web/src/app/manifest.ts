import type { MetadataRoute } from "next";

/**
 * Web app manifest (Next file-based `manifest` convention → `/manifest.webmanifest`).
 * Names + theme/background mirror the brand tokens (warm surface --bg #faf8f6,
 * Clay theme #b5512f). Icons reference the file-based `app/icon`.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Hearth — Agentic AI Commerce",
    short_name: "Hearth",
    description:
      "A concierge agentic-commerce demo for well-made, handmade things.",
    start_url: "/",
    display: "standalone",
    background_color: "#faf8f6",
    theme_color: "#b5512f",
    icons: [
      { src: "/icon", sizes: "32x32", type: "image/png" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
