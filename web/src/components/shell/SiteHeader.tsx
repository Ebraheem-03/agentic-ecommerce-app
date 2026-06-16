import Link from "next/link";
import { HearthMark } from "@/components/HearthMark";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AccountMenu } from "@/components/shell/AccountMenu";
import { MobileNav } from "@/components/shell/MobileNav";
import { CartIcon, SearchIcon } from "@/components/shell/icons";
import { PRIMARY_NAV } from "@/components/shell/nav-links";
import { getCurrentUser } from "@/lib/current-user";
import { Button } from "@/components/ui/button";

/**
 * Global header — sticky, token-truthful port of the hi-fi `.site-header`.
 * Server component: resolves the signed-in user for the auth-state slot. Wires
 * the `home-nav` / `home-search-entry` / `home-cart-link` test-ids (these are
 * stable wherever the shell renders, per the registry).
 */
export async function SiteHeader(): Promise<JSX.Element> {
  const user = await getCurrentUser();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur-md backdrop-saturate-150">
      <div className="mx-auto flex h-[72px] max-w-[1200px] items-center gap-6 px-4 sm:px-8">
        <Link
          href="/"
          aria-label="Hearth home"
          className="inline-flex items-center gap-3"
        >
          <HearthMark size={30} title="" />
          <span className="font-display text-2xl font-semibold tracking-tight text-text">
            Hearth
          </span>
        </Link>

        <nav
          data-testid="home-nav"
          aria-label="Primary"
          className="ml-2 hidden items-center gap-7 lg:flex"
        >
          {PRIMARY_NAV.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-small font-medium text-text-muted no-underline transition-colors hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3 sm:gap-3.5">
          <Link
            href="/search"
            data-testid="home-search-entry"
            className="hidden items-center gap-2.5 rounded-full border border-border bg-surface-muted px-4 py-2 text-small text-text-muted no-underline transition-colors hover:text-text md:flex"
          >
            <SearchIcon />
            <span className="hidden lg:inline">Ask Hearth, or search makers &amp; goods…</span>
            <span className="lg:hidden">Search</span>
          </Link>

          <Link
            href="/cart"
            data-testid="home-cart-link"
            aria-label="Cart"
            className="relative inline-flex items-center gap-2 text-small font-medium text-text no-underline"
          >
            <CartIcon />
          </Link>

          <ThemeToggle />

          {user ? (
            <AccountMenu user={user} />
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Button asChild variant="ghost" size="sm" data-testid="nav-sign-in">
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild variant="brand" size="sm" data-testid="nav-register">
                <Link href="/register">Join</Link>
              </Button>
            </div>
          )}

          <MobileNav links={PRIMARY_NAV} user={user} />
        </div>
      </div>
    </header>
  );
}
