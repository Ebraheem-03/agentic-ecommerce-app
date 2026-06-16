import { Suspense } from "react";
import type { Metadata } from "next";
import { OrdersView } from "@/components/orders/OrdersView";

export const metadata: Metadata = {
  title: "Order status · Hearth",
};

export default function OrdersPage(): JSX.Element {
  return (
    <section data-testid="order-status-page" className="py-8 sm:py-10">
      <header className="mb-8">
        <p className="text-caption font-medium uppercase tracking-wide text-accent-text">Orders</p>
        <h1 className="mt-1 font-display text-h1 font-semibold text-text">Order status &amp; returns</h1>
      </header>
      <Suspense fallback={<p className="py-12 text-body text-text-muted">Loading…</p>}>
        <OrdersView />
      </Suspense>
    </section>
  );
}
