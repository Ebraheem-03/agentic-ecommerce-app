"use client";

import { useMemo, useState } from "react";
import type { ProductDetail, ProductVariant } from "@/lib/api-types";
import { addToCart, formatPrice, ShopError } from "@/lib/shop-client";
import { Button } from "@/components/ui/button";
import { StockBadge } from "@/components/shop/StockBadge";
import { cn } from "@/lib/cn";

/**
 * Product buy box — variant pickers, quantity stepper, and add-to-cart with an
 * OPTIMISTIC confirmation. On add we show `product-add-confirmation` immediately,
 * then call `POST /cart/items`; if the server rejects (e.g. `out_of_stock`) we
 * roll the confirmation back and surface `product-out-of-stock`. Selecting an
 * out-of-stock variant also surfaces the OOS notice and disables the add.
 *
 * Wires product-qty / product-add-to-cart / product-add-confirmation /
 * product-out-of-stock.
 */

type AddState = "idle" | "adding" | "added";

/** Group variants by their option dimension (Glaze, Size, …). */
function groupVariants(variants: ProductVariant[]): Map<string, ProductVariant[]> {
  const groups = new Map<string, ProductVariant[]>();
  for (const v of variants) {
    const list = groups.get(v.option_name) ?? [];
    list.push(v);
    groups.set(v.option_name, list);
  }
  return groups;
}

export function ProductBuyBox({ product }: { product: ProductDetail }): JSX.Element {
  const groups = useMemo(() => groupVariants(product.variants), [product.variants]);

  // Default selection: first in-stock variant per group, else the first.
  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [name, list] of groups) {
      const inStock = list.find((v) => v.stock !== "out_of_stock");
      init[name] = (inStock ?? list[0])?.id ?? "";
    }
    return init;
  });

  const [qty, setQty] = useState(1);
  const [addState, setAddState] = useState<AddState>("idle");
  const [oosNotice, setOosNotice] = useState<string | null>(null);

  // The variant the current selection resolves to (single-dimension fixture).
  const activeVariant = useMemo<ProductVariant | undefined>(() => {
    const ids = Object.values(selected);
    return product.variants.find((v) => ids.includes(v.id));
  }, [selected, product.variants]);

  const isOos = activeVariant?.stock === "out_of_stock";

  const onAdd = async (): Promise<void> => {
    if (!activeVariant || isOos || addState === "adding") return;
    setOosNotice(null);
    // Optimistic: flash the confirmation first.
    setAddState("added");
    try {
      await addToCart({ variant_id: activeVariant.id, qty });
      // Keep the confirmation; clear it after a beat.
      window.setTimeout(() => setAddState("idle"), 2600);
    } catch (err) {
      // Roll back the optimistic confirmation and surface the reason.
      setAddState("idle");
      if (err instanceof ShopError && err.body.code === "out_of_stock") {
        setOosNotice(
          "That option just sold out. Pick another below, or ask Ember for the closest in-stock match.",
        );
      } else {
        setOosNotice(
          err instanceof Error ? err.message : "Could not add to cart. Please try again.",
        );
      }
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-baseline gap-3">
        <span data-testid="product-price" className="font-display text-h2 font-semibold text-text">
          {formatPrice(product.price_cents, product.currency)}
        </span>
        <StockBadge stock={activeVariant?.stock ?? product.stock} />
      </div>

      <p className="max-w-[60ch] text-body text-text-muted">{product.description}</p>

      {/* Variant pickers */}
      {Array.from(groups).map(([name, list]) => (
        <fieldset key={name} className="flex flex-col gap-2">
          <legend className="text-caption font-medium uppercase tracking-wide text-text-muted">
            {name}
          </legend>
          <div className="flex flex-wrap gap-2">
            {list.map((v) => {
              const isSelected = selected[name] === v.id;
              const vOos = v.stock === "out_of_stock";
              return (
                <button
                  key={v.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => {
                    setSelected((s) => ({ ...s, [name]: v.id }));
                    setOosNotice(null);
                    setAddState("idle");
                  }}
                  className={cn(
                    "rounded-full border px-3.5 py-1.5 text-small transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong",
                    isSelected
                      ? "border-accent-strong bg-accent-tint text-text"
                      : "border-border bg-surface text-text-muted hover:border-n-300 hover:text-text",
                    // Sold-out: strikethrough + the "· sold out" suffix signal
                    // unavailability WITHOUT dimming the text below AA contrast
                    // (opacity-60 dropped --text-muted to 2.91:1, axe wcag143).
                    vOos && "line-through",
                  )}
                >
                  {v.option_value}
                  {vOos ? <span className="ml-1.5 no-underline">· sold out</span> : null}
                </button>
              );
            })}
          </div>
        </fieldset>
      ))}

      {/* Quantity + add */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-2">
          <span id="qty-label" className="text-caption font-medium uppercase tracking-wide text-text-muted">
            Quantity
          </span>
          <div
            role="group"
            aria-labelledby="qty-label"
            className="inline-flex items-center rounded-lg border border-border bg-surface"
          >
            <button
              type="button"
              aria-label="Decrease quantity"
              onClick={() => setQty((n) => Math.max(1, n - 1))}
              disabled={qty <= 1}
              className="grid h-11 w-11 place-items-center text-text-muted transition-colors hover:text-text disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
            >
              &minus;
            </button>
            <input
              data-testid="product-qty"
              type="number"
              min={1}
              value={qty}
              aria-label="Quantity"
              onChange={(e) => setQty(Math.max(1, Math.floor(Number(e.target.value) || 1)))}
              className="h-11 w-12 border-x border-border bg-surface text-center text-body text-text [appearance:textfield] focus-visible:outline-none [&::-webkit-inner-spin-button]:appearance-none"
            />
            <button
              type="button"
              aria-label="Increase quantity"
              onClick={() => setQty((n) => n + 1)}
              className="grid h-11 w-11 place-items-center text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
            >
              +
            </button>
          </div>
        </div>

        <Button
          type="button"
          variant="primary"
          size="lg"
          data-testid="product-add-to-cart"
          onClick={onAdd}
          disabled={isOos || addState === "adding"}
          className="flex-1 min-w-[200px]"
        >
          {isOos
            ? "Sold out"
            : `Add to cart · ${formatPrice(product.price_cents * qty, product.currency)}`}
        </Button>
      </div>

      {/* Inline confirmation */}
      {addState === "added" ? (
        <div
          data-testid="product-add-confirmation"
          role="status"
          className="inline-flex items-center gap-2 self-start rounded-full bg-success-tint px-3.5 py-2 text-small font-medium text-[#2c5b41]"
        >
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" aria-hidden="true" />
          Added to cart
        </div>
      ) : null}

      {/* OOS / failure notice (registered state). Always present when a chosen
          variant is OOS, or after a server-side out_of_stock rejection. */}
      {isOos || oosNotice ? (
        <div
          data-testid="product-out-of-stock"
          role="alert"
          className="rounded-[12px] border border-warning/40 bg-warning-tint/60 px-3.5 py-2.5 text-small leading-relaxed text-[#7a560f]"
        >
          {oosNotice ??
            "This option is sold out. Pick another above, or ask Ember for the closest in-stock match."}
        </div>
      ) : null}
    </div>
  );
}
