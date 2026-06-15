import Link from "next/link";
import type { Metadata } from "next";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in — Hearth",
};

export default function LoginPage(): JSX.Element {
  return (
    <div data-testid="login-page" className="w-full max-w-md">
      <Card className="shadow-[0_1px_2px_rgba(27,22,17,.04),0_18px_44px_-22px_rgba(27,22,17,.18)]">
        <CardHeader className="text-center">
          <CardTitle>Welcome back</CardTitle>
          <CardDescription>
            Sign in to pick up where you left off with your concierge.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <LoginForm />
          <p className="text-center text-small text-text-muted">
            New to Hearth?{" "}
            <Link href="/register" className="font-medium text-brand-strong hover:underline">
              Create an account
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
