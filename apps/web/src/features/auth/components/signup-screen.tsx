"use client";

import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ShieldLogo } from "@/components/shield-logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";

import { useSignup } from "../api";

export function SignupScreen() {
  const router = useRouter();
  const signup = useSignup();
  const [orgName, setOrgName] = React.useState("");
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!orgName.trim() || !name.trim() || !email.trim() || !password) {
      setError("Fill in every field.");
      return;
    }
    if (password.length < 10) {
      setError("Password must be at least 10 characters.");
      return;
    }
    setError(null);
    signup.mutate(
      { org_name: orgName.trim(), name: name.trim(), email: email.trim(), password },
      {
        onSuccess: (session) => {
          toast.success(`Welcome, ${session.user.name.split(" ")[0]}. Your organisation is ready.`);
          router.replace("/");
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-background px-6 py-6 sm:px-10">
      <div className="flex items-center justify-between">
        <ShieldLogo />
        <ThemeToggle />
      </div>
      <div className="flex flex-1 items-center justify-center py-10">
        <div className="w-full max-w-[380px]">
          <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.025em]">Create your organisation</h1>
          <p className="mt-1.5 text-[13.5px] text-muted-foreground">
            This creates your organisation and your owner account in one step.
          </p>
          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="org-name">Organisation name</Label>
              <Input id="org-name" placeholder="Verdant Pay" className="h-10" value={orgName} onChange={(e) => setOrgName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" placeholder="Priya Nair" className="h-10" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="you@company.com"
                className="h-10"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                className="h-10"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">At least 10 characters.</p>
            </div>
            {error && <FieldError>{error}</FieldError>}
            <Button type="submit" size="lg" className="w-full" disabled={signup.isPending}>
              {signup.isPending ? "Creating..." : "Create organisation"}
              {!signup.isPending && <ArrowRightIcon />}
            </Button>
          </form>
          <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
