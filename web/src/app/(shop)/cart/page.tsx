import type { Metadata } from "next";
import { CartView } from "@/components/cart/CartView";

export const metadata: Metadata = {
  title: "Your cart · Hearth",
};

export default function CartPage(): JSX.Element {
  return (
    <section data-testid="cart-page" className="py-8 sm:py-10">
      <header className="mb-8">
        <p className="text-caption font-medium uppercase tracking-wide text-accent-text">Cart</p>
        <h1 className="mt-1 font-display text-h1 font-semibold text-text">Your cart</h1>
      </header>
      <CartView />
    </section>
  );
}
