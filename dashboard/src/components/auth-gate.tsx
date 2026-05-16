"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getStoredUser, hasRole, type AuthUser, type Role } from "@/lib/auth";

/** Client-side route guard. Renders children once the stored user satisfies
 *  `minRole`; otherwise redirects to /login with a ?next= param so the user
 *  lands back where they wanted after signing in.
 *
 *  Why client-side rather than middleware: the JWT lives in localStorage to
 *  keep CSRF surface small. Middleware can't read localStorage, so the gate
 *  has to run in the browser. The cost is a tiny flash of "checking…" — it
 *  only happens once per tab.
 */
export function AuthGate({
  children,
  minRole = "viewer",
  fallback = null,
}: {
  children: React.ReactNode;
  minRole?: Role;
  fallback?: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    setUser(stored);
    setChecked(true);
    if (!stored) {
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/login?next=${next}`);
    } else if (!hasRole(stored, minRole)) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
    }
  }, [router, pathname, minRole]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">
        Checking session…
      </div>
    );
  }
  if (!user || !hasRole(user, minRole)) return <>{fallback}</>;
  return <>{children}</>;
}
