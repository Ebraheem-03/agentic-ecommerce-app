import type { Metadata } from "next";
import { SellerDashboardView } from "@/components/seller/SellerDashboardView";

export const metadata: Metadata = {
  title: "Maker dashboard · Hearth",
};

export default function SellerPage(): JSX.Element {
  return (
    <section data-testid="seller-dashboard-page" className="py-8 sm:py-10">
      <header className="mb-8">
        <p className="text-caption font-medium uppercase tracking-wide text-accent-text">Sell on Hearth</p>
        <h1 className="mt-1 font-display text-h1 font-semibold text-text">Maker dashboard</h1>
      </header>
      <SellerDashboardView />
    </section>
  );
}
