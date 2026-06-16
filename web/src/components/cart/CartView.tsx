"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { CartItemOut, CartOut } from "@/lib/api-types";
import {
  formatPrice,
  getCart,
  removeCartLine,
  ShopError,
  updateCartLine,
} from "@/lib/shop-client";
import { Button } from "@/components/ui/button";
import { ProductThumb } from "@/components/shop/ProductThumb";

/**
 * The cart surface — real line items with OPTIMISTIC qty steppers and remove.
 * Each mutation updates local state immediately, then reconciles with the mock
 * `/cart` route (PATCH/DELETE); a server rejection rolls the line back and
 * surfaces the canonical error. Subtotal + currency recompute from the lines.
 *
 * Wires cart-line-item / cart-line-title / cart-line-qty / cart-line-remove /
 * cart-subtotal / cart-empty-state / cart-checkout-cta.
 */
export function CartView(): JSX.Element {
  const [cart, setCart] = useState<CartOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    getCart()
      .then((c) => active && setCart(c))
      .catch(
        (e: unknown) =>
          active &&
          setError(e instanceof Error ? e.message : "Could not load your cart."),
      );
    return () => {
      active = false;
    };
  }, []);

  const markPending = (id: string, on: boolean): void => {
    setPending((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  /** Optimistically recompute the whole cart from a transformed line list. */
  const recompute = (lines: CartItemOut[]): CartOut => ({
    id: cart?.id ?? "cart_mock",
    status: cart?.status ?? "open",
    items: lines,
    subtotal_minor: lines.reduce((n, l) => n + l.line_total_minor, 0),
    currency: cart?.currency ?? "USD",
    item_count: lines.reduce((n, l) => n + l.qty, 0),
    updated_at: new Date().toISOString(),
  });

  const setQty = async (line: CartItemOut, qty: number): Promise<void> => {
    if (qty < 1 || !cart) return;
    const prev = cart;
    setError(null);
    markPending(line.id, true);
    // Optimistic.
    setCart(
      recompute(
        cart.items.map((l) =>
          l.id === line.id
            ? { ...l, qty, line_total_minor: l.unit_price_minor * qty }
            : l,
        ),
      ),
    );
    try {
      const fresh = await updateCartLine(line.id, { qty });
      setCart(fresh);
    } catch (e: unknown) {
      setCart(prev); // roll back
      setError(
        e instanceof ShopError ? e.body.message : "Could not update the cart.",
      );
    } finally {
      markPending(line.id, false);
    }
  };

  const remove = async (line: CartItemOut): Promise<void> => {
    if (!cart) return;
    const prev = cart;
    setError(null);
    markPending(line.id, true);
    setCart(recompute(cart.items.filter((l) => l.id !== line.id)));
    try {
      const fresh = await removeCartLine(line.id);
      setCart(fresh);
    } catch (e: unknown) {
      setCart(prev);
      setError(
        e instanceof ShopError ? e.body.message : "Could not remove that item.",
      );
    } finally {
      markPending(line.id, false);
    }
  };

  if (error && !cart) {
    return (
      <div role="alert" className="rounded-2xl border border-error/40 bg-error-tint/50 px-5 py-4 text-body text-[#8a2f24]">
        {error}
      </div>
    );
  }

  if (!cart) {
    return <p className="py-12 text-body text-text-muted">Loading your cart…</p>;
  }

  if (cart.items.length === 0) {
    return (
      <div
        data-testid="cart-empty-state"
        className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface px-6 py-12"
      >
        <h2 className="font-display text-h3 font-semibold text-text">Your cart is empty</h2>
        <p className="max-w-[48ch] text-body text-text-muted">
          Nothing here yet. Ask Ember for a recommendation, or browse the makers
          and goods on Hearth.
        </p>
        <Button asChild variant="primary">
          <Link href="/search">Ask Ember</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
      <ul className="flex flex-col gap-4" aria-label="Cart items">
        {cart.items.map((line) => {
          const busy = pending.has(line.id);
          return (
            <li
              key={line.id}
              data-testid="cart-line-item"
              className="flex gap-4 rounded-2xl border border-border bg-surface p-4"
            >
              <Link href={line.slug ? `/product/${line.slug}` : "#"} className="flex-none">
                <ProductThumb
                  alt={line.title}
                  className="h-[88px] w-[88px] rounded-xl"
                />
              </Link>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      href={line.slug ? `/product/${line.slug}` : "#"}
                      data-testid="cart-line-title"
                      className="block truncate font-display text-body font-semibold text-text hover:text-accent-strong"
                    >
                      {line.title}
                    </Link>
                    {line.option_value ? (
                      <span className="text-caption text-text-muted">{line.option_value}</span>
                    ) : null}
                  </div>
                  <span className="flex-none font-display text-body font-semibold text-text">
                    {formatPrice(line.line_total_minor, line.currency)}
                  </span>
                </div>

                {!line.in_stock ? (
                  <span className="self-start rounded-full bg-warning-tint px-2.5 py-1 text-caption font-medium text-[#7a560f]">
                    Low availability — checkout soon
                  </span>
                ) : null}

                <div className="mt-1 flex items-center justify-between gap-3">
                  {/* Qty stepper */}
                  <div
                    data-testid="cart-line-qty"
                    role="group"
                    aria-label={`Quantity for ${line.title}`}
                    className="inline-flex items-center rounded-lg border border-border bg-surface"
                  >
                    <button
                      type="button"
                      aria-label="Decrease quantity"
                      disabled={busy || line.qty <= 1}
                      onClick={() => void setQty(line, line.qty - 1)}
                      className="grid h-9 w-9 place-items-center text-text-muted transition-colors hover:text-text disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
                    >
                      &minus;
                    </button>
                    <span aria-live="polite" className="w-9 text-center text-small font-medium text-text">
                      {line.qty}
                    </span>
                    <button
                      type="button"
                      aria-label="Increase quantity"
                      disabled={busy}
                      onClick={() => void setQty(line, line.qty + 1)}
                      className="grid h-9 w-9 place-items-center text-text-muted transition-colors hover:text-text disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
                    >
                      +
                    </button>
                  </div>

                  <button
                    type="button"
                    data-testid="cart-line-remove"
                    disabled={busy}
                    onClick={() => void remove(line)}
                    className="text-small font-medium text-text-muted underline-offset-4 transition-colors hover:text-[#8a2f24] hover:underline disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Summary */}
      <aside className="h-fit rounded-2xl border border-border bg-surface p-6 lg:sticky lg:top-24">
        <h2 className="font-display text-h3 font-semibold text-text">Summary</h2>
        {error ? (
          <p role="alert" className="mt-3 rounded-lg bg-error-tint/60 px-3 py-2 text-small text-[#8a2f24]">
            {error}
          </p>
        ) : null}
        <dl className="mt-4 flex flex-col gap-2 text-body">
          <div className="flex items-center justify-between">
            <dt className="text-text-muted">
              Subtotal · {cart.item_count} item{cart.item_count === 1 ? "" : "s"}
            </dt>
            <dd data-testid="cart-subtotal" className="font-medium text-text">
              {formatPrice(cart.subtotal_minor, cart.currency)}
            </dd>
          </div>
          <div className="flex items-center justify-between text-text-muted">
            <dt>Shipping</dt>
            <dd>Calculated at checkout</dd>
          </div>
        </dl>
        <Button
          asChild
          variant="primary"
          size="lg"
          className="mt-6 w-full"
          data-testid="cart-checkout-cta"
        >
          <Link href="/checkout">Proceed to checkout</Link>
        </Button>
        <p className="mt-3 text-caption text-text-muted">
          Ember walks you through checkout and pauses for your approval before any
          charge.
        </p>
      </aside>
    </div>
  );
}
