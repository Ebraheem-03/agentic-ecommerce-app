import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Foundation placeholder for shop routes whose full build lands in later
 * stories. Carries the screen's page-root test-id so the routes exist and are
 * navigable / assertable now, with on-brand chrome rather than a blank page.
 */
export function PlaceholderPage({
  testId,
  eyebrow,
  title,
  body,
  children,
}: {
  testId: string;
  eyebrow: string;
  title: string;
  body: string;
  children?: React.ReactNode;
}): JSX.Element {
  return (
    <div data-testid={testId} className="mx-auto max-w-[1200px] px-4 py-20 sm:px-8">
      <div className="mx-auto flex max-w-xl flex-col items-center gap-4 text-center">
        <span className="inline-flex items-center gap-2 text-caption font-medium uppercase tracking-wide text-accent-text before:inline-block before:h-px before:w-5 before:bg-accent-strong">
          {eyebrow}
        </span>
        <h1 className="font-display text-h1 font-semibold tracking-tight text-text">
          {title}
        </h1>
        <p className="text-body-lg text-text-muted">{body}</p>
        {children}
        <Button asChild variant="secondary" className="mt-2">
          <Link href="/">Back to home</Link>
        </Button>
      </div>
    </div>
  );
}
