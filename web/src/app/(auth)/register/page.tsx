import Link from "next/link";
import type { Metadata } from "next";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RegisterForm } from "@/components/auth/RegisterForm";

export const metadata: Metadata = {
  title: "Create your account — Hearth",
};

export default function RegisterPage(): JSX.Element {
  return (
    <div data-testid="register-page" className="w-full max-w-md">
      <Card className="shadow-[0_1px_2px_rgba(27,22,17,.04),0_18px_44px_-22px_rgba(27,22,17,.18)]">
        <CardHeader className="text-center">
          <CardTitle>Join Hearth</CardTitle>
          <CardDescription>
            A marketplace for well-made things, shoppable by conversation.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <RegisterForm />
          <p className="text-center text-small text-text-muted">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand-strong hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
