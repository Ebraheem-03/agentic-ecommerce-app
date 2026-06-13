"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/Button";

type Theme = "light" | "dark";

/**
 * Sets data-theme on <html>. Self-contained for the /tokens review surface — no
 * persistence layer or localStorage assumptions, so it stays test-friendly.
 */
export function ThemeToggle(): JSX.Element {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const next: Theme = theme === "light" ? "dark" : "light";

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
    >
      {theme === "light" ? "Dark theme" : "Light theme"}
    </Button>
  );
}
