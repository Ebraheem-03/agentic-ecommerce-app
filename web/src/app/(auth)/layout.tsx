import type { ReactNode } from "react";
import Link from "next/link";
import { HearthMark } from "@/components/HearthMark";
import { ThemeToggle } from "@/components/ThemeToggle";

/**
 * Minimal chrome for auth surfaces: brand lockup + theme toggle over a calm,
 * centered single-column. No global nav so the focus stays on the form.
 */
export default function AuthLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-[72px] max-w-[1100px] items-center justify-between px-4 sm:px-8">
          <Link href="/" aria-label="Hearth home" className="inline-flex items-center gap-3">
            <HearthMark size={28} title="" />
            <span className="font-display text-xl font-semibold tracking-tight text-text">
              Hearth
            </span>
          </Link>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="flex flex-1 items-center justify-center px-4 py-12">
        {children}
      </main>
    </div>
  );
}
