import type { Metadata } from "next";
import { Button } from "@/components/Button";
import { HearthMark, HearthLockup } from "@/components/HearthMark";
import { ThemeToggle } from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "Hearth — Design Tokens",
  description: "Token specimen: colors, type scale, components. Review surface.",
};

/* --- Swatch data. `varName` drives the rendered fill; `hex` is a label only.
   No hex is applied as a style here — fills resolve through the CSS vars. ---- */
type Swatch = { name: string; varName: string; hex: string; ink?: "light" | "dark" };

const brand: Swatch[] = [
  { name: "brand", varName: "--brand", hex: "#B5512F" },
  { name: "brand-strong", varName: "--brand-strong", hex: "#933E22" },
  { name: "brand-tint", varName: "--brand-tint", hex: "#F6E7DF", ink: "dark" },
  { name: "accent", varName: "--accent", hex: "#E08A3C", ink: "dark" },
  { name: "accent-strong", varName: "--accent-strong", hex: "#C5722B" },
  { name: "accent-text", varName: "--accent-text", hex: "#9A5418" },
  { name: "accent-tint", varName: "--accent-tint", hex: "#FCEEDD", ink: "dark" },
];

const neutrals: Swatch[] = [
  { name: "n-50", varName: "--n-50", hex: "#FAF8F6", ink: "dark" },
  { name: "n-100", varName: "--n-100", hex: "#F3EFEB", ink: "dark" },
  { name: "n-200", varName: "--n-200", hex: "#E7E0D9", ink: "dark" },
  { name: "n-300", varName: "--n-300", hex: "#D4C9BF", ink: "dark" },
  { name: "n-400", varName: "--n-400", hex: "#A99C8F", ink: "dark" },
  { name: "n-500", varName: "--n-500", hex: "#7C6F62" },
  { name: "n-600", varName: "--n-600", hex: "#5E5247" },
  { name: "n-700", varName: "--n-700", hex: "#433A31" },
  { name: "n-800", varName: "--n-800", hex: "#2C261F" },
  { name: "n-900", varName: "--n-900", hex: "#1B1611" },
];

const semantic: Swatch[] = [
  { name: "success", varName: "--success", hex: "#3E7C5A" },
  { name: "success-tint", varName: "--success-tint", hex: "#E4F0E8", ink: "dark" },
  { name: "warning", varName: "--warning", hex: "#C58A1E" },
  { name: "warning-tint", varName: "--warning-tint", hex: "#FBF0D8", ink: "dark" },
  { name: "error", varName: "--error", hex: "#C23B34" },
  { name: "error-tint", varName: "--error-tint", hex: "#FBE6E4", ink: "dark" },
  { name: "info", varName: "--info", hex: "#3F6E86" },
  { name: "info-tint", varName: "--info-tint", hex: "#E2EDF1", ink: "dark" },
];

type TypeRow = {
  token: string;
  cls: string;
  family: "Fraunces" | "Outfit";
  meta: string;
};

const typeRows: TypeRow[] = [
  { token: "display", cls: "font-display text-display", family: "Fraunces", meta: "56 / 3.5rem · 600" },
  { token: "h1", cls: "font-display text-h1", family: "Fraunces", meta: "40 / 2.5rem · 600" },
  { token: "h2", cls: "font-display text-h2", family: "Fraunces", meta: "30 / 1.875rem · 600" },
  { token: "h3", cls: "font-display text-h3", family: "Fraunces", meta: "24 / 1.5rem · 600" },
  { token: "h4", cls: "font-sans text-h4 font-medium", family: "Outfit", meta: "20 / 1.25rem · 500" },
  { token: "body-lg", cls: "font-sans text-body-lg", family: "Outfit", meta: "18 / 1.125rem · 400" },
  { token: "body", cls: "font-sans text-body", family: "Outfit", meta: "16 / 1rem · 400" },
  { token: "small", cls: "font-sans text-small", family: "Outfit", meta: "14 / 0.875rem · 400" },
  { token: "caption", cls: "font-sans text-caption font-medium", family: "Outfit", meta: "12 / 0.75rem · 500" },
];

function SwatchCard({ s }: { s: Swatch }): JSX.Element {
  const inkClass = s.ink === "dark" ? "text-n-900" : "text-n-50";
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div
        className={`flex h-20 items-end p-2.5 ${inkClass}`}
        style={{ backgroundColor: `var(${s.varName})` }}
      >
        <span className="text-caption font-medium tracking-wide">{s.hex}</span>
      </div>
      <div className="px-2.5 py-2">
        <code className="text-small text-text">{s.name}</code>
      </div>
    </div>
  );
}

function SwatchGroup({
  heading,
  items,
}: {
  heading: string;
  items: Swatch[];
}): JSX.Element {
  return (
    <div>
      <h3 className="mb-3 text-h3 text-text">{heading}</h3>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3">
        {items.map((s) => (
          <SwatchCard key={s.name} s={s} />
        ))}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="space-y-6">
      <h2 className="text-h2 text-text">{title}</h2>
      {children}
    </section>
  );
}

export default function TokensPage(): JSX.Element {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12 md:px-8 md:py-16">
      {/* Header */}
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
        <HearthLockup size={36} />
        <div className="flex items-center gap-3">
          <span className="text-small text-text-muted">US-E2-04 · token specimen</span>
          <ThemeToggle />
        </div>
      </header>

      <div className="mb-14 max-w-prose">
        <h1 className="text-h1 text-text">Design tokens</h1>
        <p className="mt-3 text-body-lg text-text-muted">
          The Hearth color, type, and component system. Toggle the theme to verify
          both light and dark roles. Every swatch fill resolves through a CSS
          variable, not a hard-coded value.
        </p>
      </div>

      <div className="space-y-16">
        {/* Colors */}
        <Section title="Color">
          <SwatchGroup heading="Brand" items={brand} />
          <SwatchGroup heading="Neutrals" items={neutrals} />
          <SwatchGroup heading="Semantic" items={semantic} />
        </Section>

        {/* Surface roles */}
        <Section title="Surface & text roles">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-surface p-5">
              <p className="text-h4 text-text">Surface</p>
              <p className="mt-1 text-body text-text-muted">
                Muted secondary text on a raised surface.
              </p>
              <div className="mt-4 rounded-lg bg-surface-muted p-3 text-small text-text">
                surface-muted panel
              </div>
            </div>
            <div className="rounded-xl border border-border bg-bg p-5">
              <p className="text-h4 text-text">Background</p>
              <p className="mt-1 text-body text-text-muted">
                Primary text and muted text on app background.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-md bg-brand-tint px-2.5 py-1 text-small text-n-900">
                  brand-tint badge
                </span>
                <span className="rounded-md bg-accent-tint px-2.5 py-1 text-small text-n-900">
                  accent-tint badge
                </span>
              </div>
            </div>
          </div>
        </Section>

        {/* Typography */}
        <Section title="Typography">
          <div className="space-y-5">
            {typeRows.map((r) => (
              <div
                key={r.token}
                className="flex flex-col gap-1 border-b border-border pb-5 last:border-0 md:flex-row md:items-baseline md:gap-6"
              >
                <div className="w-40 shrink-0 pt-1">
                  <code className="text-small text-text">{r.token}</code>
                  <p className="text-caption text-text-muted">
                    {r.family} · {r.meta}
                  </p>
                </div>
                <p className={`${r.cls} text-text`}>
                  The fox jumps the hearth
                </p>
              </div>
            ))}
          </div>
        </Section>

        {/* Buttons */}
        <Section title="Buttons">
          <div className="space-y-8 rounded-xl border border-border bg-surface p-6">
            <div className="space-y-3">
              <p className="text-h4 text-text">primary — agent CTA (ember + dark ink)</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="primary">Add to cart</Button>
                <Button variant="primary" size="sm">Small</Button>
                <Button variant="primary" size="lg">Large</Button>
                <Button variant="primary" disabled>Disabled</Button>
              </div>
            </div>
            <div className="space-y-3">
              <p className="text-h4 text-text">brand — clay + white</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="brand">Continue</Button>
                <Button variant="brand" size="sm">Small</Button>
                <Button variant="brand" disabled>Disabled</Button>
              </div>
            </div>
            <div className="space-y-3">
              <p className="text-h4 text-text">secondary & ghost</p>
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="secondary">Save for later</Button>
                <Button variant="ghost">Cancel</Button>
                <Button variant="secondary" disabled>Disabled</Button>
              </div>
            </div>
            <p className="text-small text-text-muted">
              Tab to a button to see the focus-visible ring (brand clay).
            </p>
          </div>
        </Section>

        {/* Logo */}
        <Section title="Logo — Keystone">
          <div className="flex flex-wrap items-end gap-10 rounded-xl border border-border bg-surface p-8">
            <div className="flex flex-col items-center gap-3">
              <HearthMark size={72} />
              <code className="text-caption text-text-muted">mark</code>
            </div>
            <div className="flex flex-col items-center gap-3">
              <HearthLockup size={48} />
              <code className="text-caption text-text-muted">lockup</code>
            </div>
            <div className="flex flex-col items-center gap-3">
              <HearthMark size={28} />
              <code className="text-caption text-text-muted">small</code>
            </div>
          </div>
        </Section>
      </div>

      <footer className="mt-16 border-t border-border pt-6 text-small text-text-muted">
        Hearth design system · tokens from docs/brand/palette-and-type.md
      </footer>
    </main>
  );
}
