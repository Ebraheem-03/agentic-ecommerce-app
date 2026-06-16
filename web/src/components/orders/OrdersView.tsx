"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type {
  OrderDetail,
  OrderStatus,
  OrderSummary,
  PaymentStatus,
} from "@/lib/api-types";
import { formatPrice, getOrder, listOrders } from "@/lib/shop-client";
import { Button } from "@/components/ui/button";
import { ProductThumb } from "@/components/shop/ProductThumb";
import { OrderTimeline } from "@/components/orders/OrderTimeline";
import { ReturnPanel } from "@/components/orders/ReturnPanel";

/**
 * Order status surface — a list of my orders + an order detail with a status
 * timeline, payment status, and the per-item snapshot. A deep-linkable `?id=`
 * opens the detail; from a delivered (eligible) order the buyer can start a
 * return (the HITL path is in `ReturnPanel`).
 *
 * Wires order-status-summary / order-status-not-found (+ the timeline / return
 * anchors inside the child components).
 */

const STATUS_TONE: Record<OrderStatus, string> = {
  placed: "bg-accent-tint text-accent-text",
  packed: "bg-accent-tint text-accent-text",
  shipped: "bg-brand-tint text-brand-strong",
  delivered: "bg-success-tint text-[#2c5b41]",
  cancelled: "bg-error-tint text-[#8a2f24]",
};

const PAY_TONE: Record<PaymentStatus, string> = {
  pending: "bg-warning-tint text-[#7a560f]",
  authorized: "bg-warning-tint text-[#7a560f]",
  captured: "bg-success-tint text-[#2c5b41]",
  failed: "bg-error-tint text-[#8a2f24]",
  refunded: "bg-n-200 text-text-muted",
};

const PAY_LABEL: Record<PaymentStatus, string> = {
  pending: "Payment pending",
  authorized: "Payment authorized",
  captured: "Paid",
  failed: "Payment failed",
  refunded: "Refunded",
};

function StatusBadge({ status }: { status: OrderStatus }): JSX.Element {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-caption font-medium capitalize ${STATUS_TONE[status]}`}>
      {status}
    </span>
  );
}

export function OrdersView(): JSX.Element {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id");

  if (id) return <OrderDetailView id={id} onBack={() => router.push("/orders")} />;
  return <OrdersList />;
}

function OrdersList(): JSX.Element {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listOrders()
      .then((o) => active && setOrders(o))
      .catch((e: unknown) => active && setError(e instanceof Error ? e.message : "Could not load orders."));
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return <div role="alert" className="rounded-2xl border border-error/40 bg-error-tint/50 px-5 py-4 text-body text-[#8a2f24]">{error}</div>;
  }
  if (!orders) return <p className="py-12 text-body text-text-muted">Loading your orders…</p>;
  if (orders.length === 0) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface px-6 py-12">
        <h2 className="font-display text-h3 font-semibold text-text">No orders yet</h2>
        <p className="max-w-[48ch] text-body text-text-muted">When you place an order, it shows up here with live status.</p>
        <Button asChild variant="primary"><Link href="/search">Start shopping</Link></Button>
      </div>
    );
  }

  return (
    <ul data-testid="order-status-summary" className="flex flex-col gap-3">
      {orders.map((o) => (
        <li key={o.id}>
          <Link
            href={`/orders?id=${o.id}`}
            className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-surface p-5 transition-colors hover:border-accent-strong/60 hover:bg-accent-tint/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <span className="font-display text-body font-semibold text-text">{o.order_number}</span>
                <StatusBadge status={o.status} />
              </div>
              <span className="mt-1 block text-caption text-text-muted">
                {new Date(o.placed_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
                {" · "}{o.item_count} item{o.item_count === 1 ? "" : "s"}
              </span>
            </div>
            <span className="flex-none font-display text-body font-semibold text-text">
              {formatPrice(o.total_minor, o.currency)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function OrderDetailView({ id, onBack }: { id: string; onBack: () => void }): JSX.Element {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "notfound" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setStatus("loading");
    getOrder(id)
      .then((o) => {
        if (!active) return;
        setOrder(o);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (!active) return;
        if (typeof e === "object" && e && "status" in e && (e as { status: number }).status === 404) {
          setStatus("notfound");
        } else {
          setErrorMsg(e instanceof Error ? e.message : "Could not load that order.");
          setStatus("error");
        }
      });
    return () => {
      active = false;
    };
  }, [id]);

  if (status === "loading") return <p className="py-12 text-body text-text-muted">Loading order…</p>;
  if (status === "notfound") {
    return (
      <div data-testid="order-status-not-found" className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface px-6 py-12">
        <h2 className="font-display text-h3 font-semibold text-text">We couldn&rsquo;t find that order</h2>
        <p className="max-w-[48ch] text-body text-text-muted">The order may belong to another account, or the link is out of date.</p>
        <Button variant="secondary" onClick={onBack}>Back to my orders</Button>
      </div>
    );
  }
  if (status === "error" || !order) {
    return <div role="alert" className="rounded-2xl border border-error/40 bg-error-tint/50 px-5 py-4 text-body text-[#8a2f24]">{errorMsg}</div>;
  }

  const latestPayment = order.payments[order.payments.length - 1];

  return (
    <div className="flex flex-col gap-8">
      <button onClick={onBack} className="self-start text-small font-medium text-text-muted underline-offset-4 hover:text-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong">
        &larr; All orders
      </button>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-h2 font-semibold text-text">{order.order_number}</h2>
          <p className="mt-1 text-caption text-text-muted">
            Placed {new Date(order.placed_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={order.status} />
          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-caption font-medium ${PAY_TONE[latestPayment?.status ?? "pending"]}`}>
            {PAY_LABEL[latestPayment?.status ?? "pending"]}
          </span>
        </div>
      </div>

      {/* Timeline */}
      <div className="rounded-2xl border border-border bg-surface p-6">
        <OrderTimeline status={order.status} />
      </div>

      {/* Items */}
      <div className="rounded-2xl border border-border bg-surface p-6">
        <h3 className="font-display text-h3 font-semibold text-text">Items</h3>
        <ul className="mt-4 flex flex-col gap-4">
          {order.items.map((it) => (
            <li key={it.id} className="flex gap-4">
              <ProductThumb alt={it.title_snapshot} className="h-16 w-16 flex-none rounded-xl" />
              <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
                <div className="min-w-0">
                  {it.slug ? (
                    <Link href={`/product/${it.slug}`} className="block truncate font-display text-body font-semibold text-text hover:text-accent-strong">
                      {it.title_snapshot}
                    </Link>
                  ) : (
                    <span className="block truncate font-display text-body font-semibold text-text">{it.title_snapshot}</span>
                  )}
                  <span className="text-caption text-text-muted">
                    {Object.values(it.options_snapshot).join(" · ")}
                    {Object.keys(it.options_snapshot).length ? " · " : ""}
                    {it.store_name_snapshot} · Qty {it.qty}
                  </span>
                </div>
                <span className="flex-none font-medium text-text">
                  {formatPrice(it.unit_price_minor * it.qty, order.currency)}
                </span>
              </div>
            </li>
          ))}
        </ul>
        <dl className="mt-5 flex flex-col gap-2 border-t border-border pt-4 text-small">
          <Row label="Subtotal" value={formatPrice(order.subtotal_minor, order.currency)} />
          <Row label="Tax" value={formatPrice(order.tax_minor, order.currency)} />
          <Row label="Shipping" value={order.shipping_minor === 0 ? "Free" : formatPrice(order.shipping_minor, order.currency)} />
          <div className="mt-1 flex items-center justify-between border-t border-border pt-3 text-body">
            <dt className="font-display font-semibold text-text">Total</dt>
            <dd className="font-display font-semibold text-text">{formatPrice(order.total_minor, order.currency)}</dd>
          </div>
        </dl>
      </div>

      {/* Returns (delivered + eligible) */}
      {order.status === "delivered" ? (
        <div className="flex flex-col gap-4">
          <h3 className="font-display text-h3 font-semibold text-text">Returns</h3>
          <ReturnPanel order={order} />
        </div>
      ) : null}
    </div>
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
