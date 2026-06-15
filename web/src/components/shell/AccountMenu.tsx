"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { UserOut } from "@/lib/api-types";

/**
 * Signed-in account slot in the header. Shows the user's initial; the menu
 * exposes account links and sign-out (which hits the logout route handler and
 * refreshes server components so the shell flips back to signed-out).
 */
export function AccountMenu({ user }: { user: UserOut }): JSX.Element {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const initial = (user.display_name || user.email).trim().charAt(0).toUpperCase();

  function signOut(): void {
    startTransition(async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      router.refresh();
    });
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        data-testid="nav-account-menu"
        aria-label={`Account menu for ${user.display_name}`}
        className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-brand-tint font-display text-small font-semibold text-brand-strong outline-none transition-colors hover:bg-brand-tint/70 focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        {initial}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>
          <span className="block text-small font-medium text-text">
            {user.display_name}
          </span>
          <span className="block truncate text-caption text-text-muted">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/orders")}>
          Your orders
        </DropdownMenuItem>
        {user.role === "seller" ? (
          <DropdownMenuItem onSelect={() => router.push("/seller")}>
            Seller dashboard
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          data-testid="nav-sign-out"
          disabled={pending}
          onSelect={(e) => {
            e.preventDefault();
            signOut();
          }}
        >
          {pending ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
