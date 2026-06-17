"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type {
  FulfilStatus,
  NudgeOut,
  SellerDashboard,
  SellerFulfilItem,
} from "@/lib/api-types";
import {
  acceptNudge,
  fulfilOrderItem,
  formatPrice,
  getSellerDashboard,
  ShopError,
} from "@/lib/shop-client";
import { Button } from "@/components/ui/button";
import { StockBadge } from "@/components/shop/StockBadge";
import { EmberMark } from "@/components/agent/agent-icons";

/**
 * The maker dashboard — the seller/merchandising view. Three surfaces:
 *  - listings/inventory snapshot (stock signal per listing),
 *  - orders awaiting fulfilment (mark fulfilled/cancelled),
 *  - the agent-generated MERCHANDISING NUDGES (Echo's merch agent, mocked):
 *    a grounded headline + rationale + an audited, reversible accept.
 *
 * Wires seller-dashboard-onboarding / -orders / -fulfil / -nudge / -nudge-reason
 * / -nudge-accept / -publish-audit.
 */
export function SellerDashboardView(): JSX.Element {
  const [data, setData] = useState<SellerDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getSellerDashboard()
      .then((d) => active && setData(d))
      .catch((e: unknown) => active && setError(e instanceof Error ? e.message : "Could not load the dashboard."));
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return <div role="alert" className="rounded-2xl border border-error/40 bg-error-tint/50 px-5 py-4 text-body text-[#8a2f24]">{error}</div>;
  }
  if (!data) return <p className="py-12 text-body text-text-muted">Loading your dashboard…</p>;

  return (
    <div className="flex flex-col gap-10">
      {/* Store header / onboarding marker */}
      <div data-testid="seller-dashboard-onboarding" className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-surface p-6">
        <div>
          <p className="text-caption font-medium uppercase tracking-wide text-text-muted">Your store</p>
          <h2 className="mt-1 font-display text-h2 font-semibold text-text">{data.store_name}</h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-success-tint px-3 py-1.5 text-small font-medium text-[#2c5b41]">
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" aria-hidden="true" />
          Active
        </span>
      </div>

      {/* Merchandising nudges — the signature seller-agent surface */}
      <section aria-labelledby="nudges-heading" className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-accent text-n-900" aria-hidden="true"><EmberMark /></span>
          <h3 id="nudges-heading" className="font-display text-h3 font-semibold text-text">Ember&rsquo;s merchandising nudges</h3>
        </div>
        <p className="-mt-1 max-w-[64ch] text-small text-text-muted">
          Grounded suggestions from your live catalogue data. Accepting one is
          audited and reversible — nothing changes your listings without your say.
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          {data.nudges.map((n) => (
            <NudgeCard key={n.id} nudge={n} />
          ))}
        </div>
      </section>

      {/* Orders to fulfil */}
      <section aria-labelledby="fulfil-heading" className="flex flex-col gap-4">
        <h3 id="fulfil-heading" className="font-display text-h3 font-semibold text-text">Orders to fulfil</h3>
        <div data-testid="seller-dashboard-orders" className="overflow-hidden rounded-2xl border border-border bg-surface">
          {data.order_items.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.order_items.map((item) => (
                <FulfilRow key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className="px-5 py-8 text-center text-small text-text-muted">
              No order lines to fulfil right now.
            </p>
          )}
        </div>
      </section>

      {/* Listings / inventory snapshot */}
      <section aria-labelledby="listings-heading" className="flex flex-col gap-4">
        <h3 id="listings-heading" className="font-display text-h3 font-semibold text-text">Listings &amp; inventory</h3>
        <div className="overflow-hidden rounded-2xl border border-border bg-surface">
          <table className="w-full text-left text-small">
            <thead className="border-b border-border bg-surface-muted text-caption uppercase tracking-wide text-text-muted">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">Product</th>
                <th scope="col" className="px-5 py-3 font-medium">Price</th>
                <th scope="col" className="px-5 py-3 font-medium">On hand</th>
                <th scope="col" className="px-5 py-3 font-medium">Stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.listings.length > 0 ? (
                data.listings.map((l) => (
                  <tr key={l.product_id}>
                    <th scope="row" className="px-5 py-3 font-medium text-text">
                      <Link href={`/product/${l.slug}`} className="hover:text-accent-strong">{l.title}</Link>
                    </th>
                    <td className="px-5 py-3 text-text">{formatPrice(l.price_minor, l.currency)}</td>
                    <td className="px-5 py-3 text-text">{l.qty_on_hand}</td>
                    <td className="px-5 py-3"><StockBadge stock={l.stock} /></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-small text-text-muted">
                    No listings to show yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function NudgeCard({ nudge }: { nudge: NudgeOut }): JSX.Element {
  const [state, setState] = useState<NudgeOut>(nudge);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const accept = async (): Promise<void> => {
    setError(null);
    setBusy(true);
    try {
      const updated = await acceptNudge(state.id);
      setState(updated);
    } catch (e: unknown) {
      setError(e instanceof ShopError ? e.body.message : "Could not accept the nudge.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article data-testid="seller-dashboard-nudge" className="flex flex-col gap-3 rounded-2xl border border-accent-strong/25 bg-accent-tint/30 p-5">
      <h4 className="font-display text-body font-semibold text-text">{state.headline}</h4>
      <p data-testid="seller-dashboard-nudge-reason" className="text-small leading-relaxed text-text-muted">
        <span className="font-semibold text-accent-text">Why: </span>{state.reason}
      </p>
      {state.product_title ? (
        <Link href={`/product/${state.slug}`} className="text-caption font-medium text-accent-text underline-offset-4 hover:underline">
          {state.product_title}
        </Link>
      ) : null}
      {error ? <p role="alert" className="text-caption text-[#8a2f24]">{error}</p> : null}
      {state.accepted ? (
        <div data-testid="seller-dashboard-publish-audit" role="status" className="inline-flex items-center gap-2 self-start rounded-full bg-success-tint px-3 py-1.5 text-caption font-medium text-[#2c5b41]">
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" aria-hidden="true" />
          Accepted · logged to your activity (reversible)
        </div>
      ) : (
        <Button
          variant="primary"
          size="sm"
          data-testid="seller-dashboard-nudge-accept"
          disabled={busy}
          onClick={() => void accept()}
          className="self-start"
        >
          {busy ? "Applying…" : "Accept nudge"}
        </Button>
      )}
    </article>
  );
}

const FULFIL_TONE: Record<FulfilStatus, string> = {
  pending: "bg-warning-tint text-[#7a560f]",
  fulfilled: "bg-success-tint text-[#2c5b41]",
  cancelled: "bg-error-tint text-[#8a2f24]",
};

function FulfilRow({ item }: { item: SellerFulfilItem }): JSX.Element {
  const [state, setState] = useState<SellerFulfilItem>(item);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = async (status: FulfilStatus): Promise<void> => {
    setError(null);
    setBusy(true);
    const prev = state;
    setState({ ...state, fulfil_status: status }); // optimistic
    try {
      const updated = await fulfilOrderItem(state.id, { fulfil_status: status });
      setState(updated);
    } catch (e: unknown) {
      setState(prev);
      setError(e instanceof ShopError ? e.body.message : "Could not update fulfilment.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text">{state.title_snapshot}</span>
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-caption font-medium capitalize ${FULFIL_TONE[state.fulfil_status]}`}>
            {state.fulfil_status}
          </span>
        </div>
        <span className="text-caption text-text-muted">
          {state.order_number} · {Object.values(state.options_snapshot).join(" · ")} · Qty {state.qty}
        </span>
        {error ? <span role="alert" className="mt-1 block text-caption text-[#8a2f24]">{error}</span> : null}
      </div>
      {state.fulfil_status === "pending" ? (
        <div className="flex gap-2">
          <Button variant="primary" size="sm" data-testid="seller-dashboard-fulfil" disabled={busy} onClick={() => void set("fulfilled")}>
            Mark fulfilled
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => void set("cancelled")}>
            Cancel
          </Button>
        </div>
      ) : (
        <span className="text-caption text-text-muted">{formatPrice(state.unit_price_minor * state.qty, state.currency)}</span>
      )}
    </li>
  );
}
