import Link from "next/link";
import { HearthMark } from "@/components/HearthMark";

interface FootCol {
  heading: string;
  links: { href: string; label: string }[];
}

const FOOT_COLS: FootCol[] = [
  {
    heading: "Shop",
    links: [
      { href: "/search", label: "All goods" },
      { href: "/search?view=collections", label: "Collections" },
      { href: "/search?view=makers", label: "Makers" },
      { href: "/search?view=gifts", label: "Gift guide" },
    ],
  },
  {
    heading: "Sell",
    links: [
      { href: "/seller", label: "Open a shop" },
      { href: "/seller", label: "Seller dashboard" },
      { href: "/seller", label: "Maker handbook" },
    ],
  },
  {
    heading: "Hearth",
    links: [
      { href: "/orders", label: "Track an order" },
      { href: "/returns", label: "Returns & policy" },
      { href: "/", label: "About" },
    ],
  },
];

/** Global footer — token-truthful port of the hi-fi `.site-footer`. */
export function SiteFooter(): JSX.Element {
  return (
    <footer className="mt-16 border-t border-border bg-surface-muted">
      <div className="mx-auto max-w-[1200px] px-4 pb-10 pt-12 sm:px-8">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div className="flex flex-col gap-4">
            <span className="inline-flex items-center gap-3">
              <HearthMark size={28} title="" />
              <span className="font-display text-xl font-semibold tracking-tight text-text">
                Hearth
              </span>
            </span>
            <p className="max-w-[34ch] text-small text-text-muted">
              A marketplace for well-made things, shoppable by conversation.
            </p>
          </div>
          {FOOT_COLS.map((col) => (
            <div key={col.heading}>
              <h5 className="mb-3.5 text-caption font-medium uppercase tracking-wide text-text-muted">
                {col.heading}
              </h5>
              {col.links.map((link, i) => (
                <Link
                  key={`${link.href}-${i}`}
                  href={link.href}
                  className="block py-1.5 text-small text-text no-underline hover:underline"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>
        <div className="mt-9 flex flex-col gap-2 border-t border-border pt-5 text-caption text-text-muted sm:flex-row sm:justify-between">
          <span>© 2026 Hearth. Made with care.</span>
          <span>Privacy · Terms · Maker policy</span>
        </div>
      </div>
    </footer>
  );
}
