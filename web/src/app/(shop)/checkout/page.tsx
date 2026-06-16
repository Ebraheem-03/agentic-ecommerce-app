import type { Metadata } from "next";
import { CheckoutFlow } from "@/components/checkout/CheckoutFlow";

export const metadata: Metadata = {
  title: "Checkout with Ember · Hearth",
};

export default function CheckoutPage(): JSX.Element {
  return (
    <section data-testid="checkout-page" className="py-8 sm:py-10">
      <header className="mb-8">
        <p className="text-caption font-medium uppercase tracking-wide text-accent-text">Checkout</p>
        <h1 className="mt-1 font-display text-h1 font-semibold text-text">
          Checkout, with Ember
        </h1>
        <p className="mt-2 max-w-[60ch] text-body text-text-muted">
          Ember handles the steps and pauses for your approval before any charge —
          a human-in-the-loop gate, not a one-click surprise.
        </p>
      </header>
      <CheckoutFlow />
    </section>
  );
}
