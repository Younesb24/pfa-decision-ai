"use client";

import { Suspense, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { login, setAuth } from "@/lib/auth";

const DEMO_USERS = [
  { email: "admin@pfa.local", password: "admin123", role: "admin" },
  { email: "ops@pfa.local", password: "ops123", role: "ops" },
  { email: "analyst@pfa.local", password: "analyst123", role: "analyst" },
  { email: "viewer@pfa.local", password: "viewer123", role: "viewer" },
];

// useSearchParams must live under a Suspense boundary so Next can prerender
// the page shell without bailing out to client-side rendering. The wrapper
// at the bottom of this file provides that boundary.
function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/";

  const [email, setEmail] = useState("ops@pfa.local");
  const [password, setPassword] = useState("ops123");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await login(email, password);
      setAuth(res.access_token, res.user);
      router.replace(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  function quickFill(u: (typeof DEMO_USERS)[number]) {
    setEmail(u.email);
    setPassword(u.password);
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <Card className="w-full max-w-md p-8 space-y-6">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            PFA Decision AI
          </div>
          <h1 className="text-2xl font-semibold">Sign in</h1>
          <p className="text-sm text-muted-foreground">
            Operator console for the Olist marketplace.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium" htmlFor="password">
              Password
            </label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="text-sm text-red-500 bg-red-500/10 rounded-md px-3 py-2">
              {error}
            </div>
          )}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="border-t pt-4 space-y-2">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Demo users
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {DEMO_USERS.map((u) => (
              <button
                key={u.email}
                type="button"
                onClick={() => quickFill(u)}
                className="text-left rounded-md border px-2 py-1.5 hover:bg-accent transition-colors"
              >
                <div className="font-mono">{u.role}</div>
                <div className="text-muted-foreground truncate">{u.email}</div>
              </button>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
