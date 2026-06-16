"use client";

import { useState } from "react";
import type {
  OrderDetail,
  ReturnOut,
  ReturnReason,
} from "@/lib/api-types";
import { createReturn, formatPrice, ShopError } from "@/lib/shop-client";
import { Button } from "@/components/ui/button";

/**
 * Return-request UI for a delivered order. The buyer selects items + a reason and
 * submits → `POST /orders/{id}/returns`. Models the HITL path: a return on an
 * out-of-window order lands in `hitl_pending` (the agent-assisted human-in-the-
 * loop deferral) and surfaces `order-status-hitl-pending` instead of a clean
 * acknowledgement.
 *
 * Wires order-status-return-cta / order-status-return-panel / order-status-hitl-pending.
 */

const REASONS: { value: ReturnReason; label: string }[] = [
  { value: "damaged", label: "Arrived damaged" },
  { value: "not_as_described", label: "Not as described" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "no_longer_needed", label: "No longer needed" },
  { value: "arrived_late", label: "Arrived too late" },
  { value: "other", label: "Other" },
];

export function ReturnPanel({ order }: { order: OrderDetail }): JSX.Element {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState<ReturnReason>("damaged");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ReturnOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (id: string): void => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submit = async (): Promise<void> => {
    setError(null);
    if (selected.size === 0) {
      setError("Choose at least one item to return.");
      return;
    }
    setSubmitting(true);
    try {
      const items = order.items
        .filter((it) => selected.has(it.id))
        .map((it) => ({ order_item_id: it.id, qty: it.qty }));
      const ret = await createReturn(order.id, { reason_code: reason, note: note || null, items });
      setResult(ret);
    } catch (e: unknown) {
      setError(e instanceof ShopError ? e.body.message : "Could not start the return.");
    } finally {
      setSubmitting(false);
    }
  };

  // Acknowledged states ----------------------------------------------------
  if (result) {
    if (result.status === "hitl_pending") {
      return (
        <div
          data-testid="order-status-hitl-pending"
          role="status"
          className="rounded-2xl border border-warning/40 bg-warning-tint/50 p-6"
        >
          <h3 className="font-display text-h3 font-semibold text-[#7a560f]">A person is reviewing this</h3>
          <p className="mt-2 max-w-[58ch] text-body text-[#7a560f]">
            This order is outside the standard return window, so Ember can&rsquo;t
            auto-approve it. I&rsquo;ve sent your request to a Hearth specialist —
            you&rsquo;ll hear back within a day. Reference {result.id}.
          </p>
        </div>
      );
    }
    return (
      <div role="status" className="rounded-2xl border border-success/40 bg-success-tint/50 p-6">
        <h3 className="font-display text-h3 font-semibold text-[#2c5b41]">Return requested</h3>
        <p className="mt-2 max-w-[58ch] text-body text-[#2c5b41]">
          We&rsquo;ve logged your return ({result.id}). Watch your email for the
          prepaid label and next steps.
        </p>
      </div>
    );
  }

  if (!open) {
    return (
      <Button
        variant="secondary"
        data-testid="order-status-return-cta"
        onClick={() => setOpen(true)}
      >
        Request a return
      </Button>
    );
  }

  return (
    <div
      data-testid="order-status-return-panel"
      className="flex flex-col gap-5 rounded-2xl border border-border bg-surface p-6"
    >
      <h3 className="font-display text-h3 font-semibold text-text">Request a return</h3>

      <fieldset className="flex flex-col gap-2.5">
        <legend className="text-caption font-medium uppercase tracking-wide text-text-muted">Items</legend>
        {order.items.map((it) => (
          <label key={it.id} className="flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-surface-muted px-4 py-3">
            <input
              type="checkbox"
              checked={selected.has(it.id)}
              onChange={() => toggle(it.id)}
              className="h-4 w-4 accent-[var(--accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong"
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-body text-text">{it.title_snapshot}</span>
              <span className="text-caption text-text-muted">Qty {it.qty}</span>
            </span>
            <span className="flex-none text-small font-medium text-text">
              {formatPrice(it.unit_price_minor * it.qty, order.currency)}
            </span>
          </label>
        ))}
      </fieldset>

      <label className="flex flex-col gap-1.5">
        <span className="text-caption font-medium uppercase tracking-wide text-text-muted">Reason</span>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value as ReturnReason)}
          className="h-11 rounded-lg border border-border bg-surface-muted px-3.5 text-body text-text focus-visible:border-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong/40"
        >
          {REASONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-caption font-medium uppercase tracking-wide text-text-muted">Anything to add? (optional)</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          className="resize-none rounded-lg border border-border bg-surface-muted px-3.5 py-2.5 text-body text-text placeholder:text-n-400 focus-visible:border-accent-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong/40"
          placeholder="Tell Ember what happened…"
        />
      </label>

      {error ? (
        <p role="alert" className="text-small text-[#8a2f24]">{error}</p>
      ) : null}

      <div className="flex gap-3">
        <Button variant="primary" disabled={submitting} onClick={() => void submit()}>
          {submitting ? "Sending…" : "Submit return"}
        </Button>
        <Button variant="ghost" disabled={submitting} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
