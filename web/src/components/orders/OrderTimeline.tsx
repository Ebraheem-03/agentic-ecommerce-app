import type { OrderStatus } from "@/lib/api-types";

/**
 * Order status timeline — the contract's `OrderStatus` progression rendered as a
 * stepper. Cancelled orders short-circuit the happy path. Conveys state with a
 * label + a filled/hollow marker (not colour alone) for a11y.
 *
 * Wires order-status-timeline / order-status-step.
 */
const HAPPY_PATH: OrderStatus[] = ["placed", "packed", "shipped", "delivered"];

const LABEL: Record<OrderStatus, string> = {
  placed: "Placed",
  packed: "Packed",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export function OrderTimeline({ status }: { status: OrderStatus }): JSX.Element {
  if (status === "cancelled") {
    return (
      <div data-testid="order-status-timeline" className="rounded-xl border border-error/40 bg-error-tint/40 px-4 py-3">
        <span data-testid="order-status-step" className="text-small font-medium text-[#8a2f24]">
          This order was cancelled.
        </span>
      </div>
    );
  }

  const currentIndex = HAPPY_PATH.indexOf(status);

  return (
    <ol
      data-testid="order-status-timeline"
      aria-label="Order status timeline"
      className="flex flex-col gap-0 sm:flex-row sm:items-start sm:gap-0"
    >
      {HAPPY_PATH.map((step, i) => {
        const done = i <= currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <li
            key={step}
            data-testid="order-status-step"
            aria-current={isCurrent ? "step" : undefined}
            className="flex flex-1 items-center gap-3 sm:flex-col sm:items-center sm:gap-2 sm:text-center"
          >
            <div className="flex items-center sm:w-full sm:flex-col">
              <span
                className={`grid h-7 w-7 flex-none place-items-center rounded-full border-2 text-caption font-semibold ${
                  done
                    ? "border-accent-strong bg-accent-strong text-white"
                    : "border-border bg-surface text-text-muted"
                }`}
              >
                {done ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                ) : (
                  i + 1
                )}
              </span>
            </div>
            <span className={`text-small ${isCurrent ? "font-semibold text-text" : done ? "font-medium text-text" : "text-text-muted"}`}>
              {LABEL[step]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
