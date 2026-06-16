"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type {
  AddressIn,
  CartOut,
  OrderDetail,
  PaymentStatus,
} from "@/lib/api-types";
import {
  checkout,
  confirmPayment,
  createPaymentIntent,
  formatPrice,
  getCart,
  ShopError,
} from "@/lib/shop-client";
import { Button } from "@/components/ui/button";
import { EmberMark } from "@/components/agent/agent-icons";

/**
 * Agentic checkout with the human-in-the-loop APPROVAL GATE — the signature
 * surface of this story. Ember drives checkout and PAUSES at the gate (the
 * LangGraph `interrupt()` moment): she lays out exactly what she's about to do
 * (items, ship-to, payment, total) and requires an explicit Approve / Cancel
 * before any money side-effect. On Approve she runs the two-step test-mode
 * payment: POST /orders (idempotent) → payment-intent → payment-confirm.
 *
 * The decline is the CONTRACT switch, surfaced to the human as a payment-method
 * choice: "Declined test card" sends `outcome="failed"` → 402 payment_declined;
 * the order stays placed/unpaid and Ember offers a graceful retry.
 *
 * Wires checkout-address-form / -line1 / -address-error / -payment-form /
 * -payment-error / -order-summary / -place-order (the Approve control) /
 * -confirmation.
 */

type Phase = "review" | "approval" | "processing" | "confirmed" | "declined";

type PaymentChoice = Extract<PaymentStatus, "captured" | "failed">;

const DEFAULT_ADDRESS: AddressIn = {
  name: "Maya Rowe",
  line1: "14 Kiln Lane",
  line2: "",
  city: "Bristol",
  region: "",
  postal_code: "BS1 4DJ",
  country: "GB",
};

/** A stable idempotency key per checkout attempt, regenerated only on a fresh start. */
function newIdemKey(): string {
  return `idem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function CheckoutFlow(): JSX.Element {
  const [cart, setCart] = useState<CartOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>("review");
  const [address, setAddress] = useState<AddressIn>(DEFAULT_ADDRESS);
  const [addressError, setAddressError] = useState<string | null>(null);
  const [payChoice, setPayChoice] = useState<PaymentChoice>("captured");

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const idemKey = useRef<string>(newIdemKey());

  useEffect(() => {
    let active = true;
    getCart()
      .then((c) => active && setCart(c))
      .catch(
        (e: unknown) =>
          active &&
          setLoadError(e instanceof Error ? e.message : "Could not load your cart."),
      );
    return () => {
      active = false;
    };
  }, []);

  const total = useMemo(() => {
    if (!cart) return { subtotal: 0, tax: 0, total: 0 };
    const subtotal = cart.subtotal_minor;
    const tax = Math.round(subtotal * 0.08);
    return { subtotal, tax, total: subtotal + tax };
  }, [cart]);

  // ---- review → approval gate -------------------------------------------
  const openGate = (): void => {
    setAddressError(null);
    if (!address.name.trim() || !address.line1.trim() || !address.city.trim()) {
      setAddressError("Add a name, street, and city so Ember knows where to ship.");
      return;
    }
    setPhase("approval");
  };

  // ---- the gated, irreversible run --------------------------------------
  const approveAndPay = async (): Promise<void> => {
    if (!cart) return;
    setPaymentError(null);
    setPhase("processing");
    try {
      // Step 1: checkout (idempotent) — money side-effect begins only here.
      const placed = await checkout(
        { ship_address: address, idempotency_key: idemKey.current },
        idemKey.current,
      );
      setOrder(placed);
      // Step 2: intent.
      const intent = await createPaymentIntent(placed.id);
      // Step 3: confirm (deterministic decline switch).
      await confirmPayment(placed.id, {
        payment_id: intent.payment_id,
        outcome: payChoice,
      });
      setPhase("confirmed");
    } catch (e: unknown) {
      if (e instanceof ShopError && e.body.code === "payment_declined") {
        setPaymentError(e.body.message);
        setPhase("declined");
      } else {
        setPaymentError(
          e instanceof Error ? e.message : "Checkout failed. Please try again.",
        );
        setPhase("declined");
      }
    }
  };

  const retry = (): void => {
    setPaymentError(null);
    // Re-run against the same placed order (idempotent checkout returns it).
    setPhase("approval");
  };

  const cancelGate = (): void => {
    setPhase("review");
  };

  if (loadError) {
    return (
      <div role="alert" className="rounded-2xl border border-error/40 bg-error-tint/50 px-5 py-4 text-body text-[#8a2f24]">
        {loadError}
      </div>
    );
  }
  if (!cart) {
    return <p className="py-12 text-body text-text-muted">Loading checkout…</p>;
  }
  if (cart.items.length === 0 && phase === "review") {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface px-6 py-12">
        <h2 className="font-display text-h3 font-semibold text-text">Nothing to check out</h2>
        <p className="max-w-[48ch] text-body text-text-muted">
          Your cart is empty. Add something first, then Ember can take you through
          checkout.
        </p>
        <Button asChild variant="primary">
          <Link href="/search">Ask Ember</Link>
        </Button>
      </div>
    );
  }

  if (phase === "confirmed" && order) {
    return <Confirmation order={order} />;
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <div className="flex flex-col gap-6">
        <EmberSays phase={phase} payChoice={payChoice} />

        {/* Address */}
        <form
          data-testid="checkout-address-form"
          onSubmit={(e) => {
            e.preventDefault();
            openGate();
          }}
          className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6"
        >
          <h2 className="font-display text-h3 font-semibold text-text">Ship to</h2>
          <fieldset disabled={phase !== "review"} className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" value={address.name} onChange={(v) => setAddress((a) => ({ ...a, name: v }))} className="sm:col-span-2" />
            <Field testId="checkout-address-line1" label="Street address" value={address.line1} onChange={(v) => setAddress((a) => ({ ...a, line1: v }))} className="sm:col-span-2" />
            <Field label="City" value={address.city} onChange={(v) => setAddress((a) => ({ ...a, city: v }))} />
            <Field label="Postal code" value={address.postal_code} onChange={(v) => setAddress((a) => ({ ...a, postal_code: v }))} />
            <Field label="Country" value={address.country} onChange={(v) => setAddress((a) => ({ ...a, country: v }))} />
          </fieldset>
          {addressError ? (
            <p data-testid="checkout-address-error" role="alert" className="text-small text-[#8a2f24]">
              {addressError}
            </p>
          ) : null}
        </form>

        {/* Payment method */}
        <div data-testid="checkout-payment-form" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
          <h2 className="font-display text-h3 font-semibold text-text">Payment</h2>
          <p className="text-small text-text-muted">
            Test mode — no real card is charged. Choose a card to demo a successful
            charge or a decline.
          </p>
          <fieldset disabled={phase === "processing"} className="flex flex-col gap-2.5">
            <legend className="sr-only">Test payment method</legend>
            <PayOption checked={payChoice === "captured"} onChange={() => setPayChoice("captured")} title="Test card · succeeds" subtitle="•••• 4242 — confirms the charge" />
            <PayOption checked={payChoice === "failed"} onChange={() => setPayChoice("failed")} title="Test card · declined" subtitle="•••• 0002 — forces payment_declined (402)" />
          </fieldset>
          {paymentError && phase !== "declined" ? (
            <p data-testid="checkout-payment-error" role="alert" className="text-small text-[#8a2f24]">
              {paymentError}
            </p>
          ) : null}
        </div>

        {/* Decline state — graceful retry */}
        {phase === "declined" ? (
          <div data-testid="checkout-payment-error" role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-error/40 bg-error-tint/50 p-6">
            <h2 className="font-display text-h3 font-semibold text-[#8a2f24]">Payment didn&rsquo;t go through</h2>
            <p className="max-w-[52ch] text-body text-[#8a2f24]">
              {paymentError} Your order is held{order ? ` (${order.order_number})` : ""}
              {" "}but unpaid — nothing was charged. Pick a different card and Ember
              will try again.
            </p>
            <div className="flex gap-3">
              <Button variant="primary" onClick={retry}>Try payment again</Button>
              {order ? (
                <Button asChild variant="secondary">
                  <Link href={`/orders?id=${order.id}`}>View held order</Link>
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {/* Order summary + the APPROVAL GATE */}
      <aside className="h-fit lg:sticky lg:top-24">
        <div data-testid="checkout-order-summary" className="rounded-2xl border border-border bg-surface p-6">
          <h2 className="font-display text-h3 font-semibold text-text">Order summary</h2>
          <ul className="mt-4 flex flex-col gap-3">
            {cart.items.map((line) => (
              <li key={line.id} className="flex items-start justify-between gap-3 text-small">
                <span className="min-w-0">
                  <span className="block truncate text-text">{line.title}</span>
                  <span className="text-text-muted">
                    {line.option_value ? `${line.option_value} · ` : ""}Qty {line.qty}
                  </span>
                </span>
                <span className="flex-none font-medium text-text">
                  {formatPrice(line.line_total_minor, line.currency)}
                </span>
              </li>
            ))}
          </ul>
          <dl className="mt-4 flex flex-col gap-2 border-t border-border pt-4 text-small">
            <Row label="Subtotal" value={formatPrice(total.subtotal, cart.currency)} />
            <Row label="Estimated tax" value={formatPrice(total.tax, cart.currency)} />
            <Row label="Shipping" value="Free" />
            <div className="mt-1 flex items-center justify-between border-t border-border pt-3 text-body">
              <dt className="font-display font-semibold text-text">Total</dt>
              <dd className="font-display font-semibold text-text">
                {formatPrice(total.total, cart.currency)}
              </dd>
            </div>
          </dl>
        </div>

        {phase === "review" ? (
          <Button variant="primary" size="lg" className="mt-4 w-full" onClick={openGate}>
            Review with Ember
          </Button>
        ) : null}

        {phase === "approval" || phase === "processing" ? (
          <ApprovalGate
            address={address}
            itemCount={cart.item_count}
            total={formatPrice(total.total, cart.currency)}
            payLabel={payChoice === "failed" ? "Test card · declined (•••• 0002)" : "Test card · succeeds (•••• 4242)"}
            processing={phase === "processing"}
            onApprove={() => void approveAndPay()}
            onCancel={cancelGate}
          />
        ) : null}
      </aside>
    </div>
  );
}

/** Ember's checkout voice — keeps the gate conversation-first (ADR-0036). */
function EmberSays({ phase, payChoice }: { phase: Phase; payChoice: PaymentChoice }): JSX.Element {
  const line =
    phase === "approval" || phase === "processing"
      ? "Here's exactly what I'm about to do. I won't charge anything until you approve."
      : phase === "declined"
        ? "That card was declined — I stopped before anything went through. Want me to try another?"
        : payChoice === "failed"
          ? "I'll take you through checkout. Heads up: you've picked the declined test card, so I'll stop at the charge."
          : "I'll take you through checkout and pause for your approval before any charge.";
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-accent-strong/30 bg-accent-tint/50 p-4">
      <span className="grid h-9 w-9 flex-none place-items-center rounded-[10px] bg-accent text-n-900" aria-hidden="true">
        <EmberMark />
      </span>
      <div className="min-w-0">
        <div className="font-display text-small font-semibold text-text">Ember · Hearth concierge</div>
        <p className="mt-0.5 text-body leading-relaxed text-text">{line}</p>
      </div>
    </div>
  );
}

/** The human-in-the-loop gate. Approve is the only path to a money side-effect. */
function ApprovalGate({
  address,
  itemCount,
  total,
  payLabel,
  processing,
  onApprove,
  onCancel,
}: {
  address: AddressIn;
  itemCount: number;
  total: string;
  payLabel: string;
  processing: boolean;
  onApprove: () => void;
  onCancel: () => void;
}): JSX.Element {
  return (
    <div
      role="group"
      aria-label="Approve checkout"
      className="mt-4 rounded-2xl border-2 border-accent-strong bg-surface p-5 shadow-[0_8px_30px_-18px_rgba(27,22,17,.4)]"
    >
      <div className="flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text">
        <span className="inline-block h-[7px] w-[7px] rounded-full bg-accent-strong" aria-hidden="true" />
        Approval needed
      </div>
      <p className="mt-2 text-body font-medium text-text">Ember is ready to place your order</p>
      <dl className="mt-3 flex flex-col gap-2 text-small">
        <Row label="Items" value={`${itemCount} item${itemCount === 1 ? "" : "s"}`} />
        <Row label="Ship to" value={`${address.name}, ${address.city}`} />
        <Row label="Payment" value={payLabel} />
        <Row label="Total to charge" value={total} />
      </dl>
      <div className="mt-5 flex flex-col gap-2.5">
        <Button
          variant="primary"
          size="lg"
          data-testid="checkout-place-order"
          disabled={processing}
          onClick={onApprove}
          className="w-full"
        >
          {processing ? "Placing your order…" : "Approve & place order"}
        </Button>
        <Button variant="secondary" disabled={processing} onClick={onCancel} className="w-full">
          Cancel
        </Button>
      </div>
      <p className="mt-3 text-caption text-text-muted">
        Approving authorizes the charge above. Nothing is charged until you do.
      </p>
    </div>
  );
}

function Confirmation({ order }: { order: OrderDetail }): JSX.Element {
  return (
    <div
      data-testid="checkout-confirmation"
      className="mx-auto flex max-w-[560px] flex-col items-center gap-5 rounded-2xl border border-border bg-surface px-8 py-12 text-center"
    >
      <span className="grid h-14 w-14 place-items-center rounded-full bg-success-tint text-[#2c5b41]" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </span>
      <div>
        <h2 className="font-display text-h2 font-semibold text-text">Order placed</h2>
        <p className="mt-2 text-body text-text-muted">
          Ember placed order <span className="font-medium text-text">{order.order_number}</span>.
          A receipt is on its way. You can follow it from order status.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        <Button asChild variant="primary">
          <Link href={`/orders?id=${order.id}`}>Track your order</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link href="/search">Keep browsing</Link>
        </Button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  className,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  className?: string;
  testId?: string;
}): JSX.Element {
  return (
    <label className={`flex flex-col gap-1.5 ${className ?? ""}`}>
      <span className="text-caption font-medium uppercase tracking-wide text-text-muted">{label}</span>
      <input
        data-testid={testId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-lg border border-border bg-surface-muted px-3.5 text-body text-text placeholder:text-n-400 transition-colors focus-visible:border-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong/40 disabled:opacity-70"
      />
    </label>
  );
}

function PayOption({
  checked,
  onChange,
  title,
  subtitle,
}: {
  checked: boolean;
  onChange: () => void;
  title: string;
  subtitle: string;
}): JSX.Element {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 transition-colors ${
        checked ? "border-accent-strong bg-accent-tint/50" : "border-border bg-surface hover:border-n-300"
      }`}
    >
      <input
        type="radio"
        name="pay-method"
        checked={checked}
        onChange={onChange}
        className="mt-1 h-4 w-4 accent-[var(--accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
      />
      <span className="min-w-0">
        <span className="block text-body font-medium text-text">{title}</span>
        <span className="block text-caption text-text-muted">{subtitle}</span>
      </span>
    </label>
  );
}

function Row({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-text-muted">{label}</dt>
      <dd className="font-medium text-text">{value}</dd>
    </div>
  );
}
