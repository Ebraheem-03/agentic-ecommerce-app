import Link from "next/link";
import { Button } from "@/components/Button";
import { HearthLockup } from "@/components/HearthMark";

export default function HomePage(): JSX.Element {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center px-6 py-16">
      <HearthLockup size={40} />
      <h1 className="mt-8 text-h1 text-text">A concierge that actually shops for you.</h1>
      <p className="mt-4 max-w-prose text-body-lg text-text-muted">
        Hearth is an agentic-commerce demo. The scaffold is live; the full
        application arrives over the coming weeks. Design tokens land first so
        every screen after this is built on the same warm, accessible foundation.
      </p>
      <div className="mt-8">
        <Link href="/tokens">
          <Button variant="primary">View the design tokens</Button>
        </Link>
      </div>
    </main>
  );
}
