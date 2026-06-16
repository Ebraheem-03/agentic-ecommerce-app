"use client";

import Link from "next/link";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MenuIcon } from "@/components/shell/icons";
import type { NavLink } from "@/components/shell/nav-links";
import type { UserOut } from "@/lib/api-types";

/**
 * Compact nav for narrow viewports — a Radix menu behind a hamburger. Keeps the
 * same primary links plus auth entries. Radix owns the keyboard/focus behavior.
 */
export function MobileNav({
  links,
  user,
}: {
  links: readonly NavLink[];
  user: UserOut | null;
}): JSX.Element {
  const [open, setOpen] = useState(false);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        aria-label="Open menu"
        data-testid="nav-mobile-trigger"
        className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface text-text outline-none transition-colors hover:bg-surface-muted focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-bg md:hidden"
      >
        <MenuIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        {links.map((link) => (
          <DropdownMenuItem key={link.href} asChild>
            <Link href={link.href}>{link.label}</Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        {user ? (
          <>
            <DropdownMenuItem asChild>
              <Link href="/orders">Your orders</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/api/auth/logout">Sign out</Link>
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem asChild>
              <Link href="/login">Sign in</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/register">Create account</Link>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
