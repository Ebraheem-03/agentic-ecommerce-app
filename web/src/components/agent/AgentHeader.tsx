import { cn } from "@/lib/cn";
import { EmberMark } from "@/components/agent/agent-icons";

/**
 * Concierge panel header — Ember's identity + grounded-presence line. Shared by
 * the desktop dock and the mobile sheet so the surface reads identically.
 * `as` lets the sheet render the name as the dialog title (h2) for a11y.
 */
export function AgentHeader({
  className,
  action,
}: {
  className?: string;
  /** Slot for a control on the right (e.g. the sheet's close button). */
  action?: React.ReactNode;
}): JSX.Element {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-border bg-gradient-to-b from-accent-tint to-surface px-[18px] py-4",
        className,
      )}
    >
      <span
        className="grid h-[34px] w-[34px] flex-none place-items-center rounded-[10px] bg-accent text-n-900"
        aria-hidden="true"
      >
        <EmberMark />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-display text-small font-semibold text-text">Ember · Hearth concierge</div>
        <div className="inline-flex items-center gap-1.5 text-caption text-text-muted">
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-success" aria-hidden="true" />
          Grounded in the live catalogue
        </div>
      </div>
      {action}
    </div>
  );
}
