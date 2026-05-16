"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { clearAuth, getStoredUser, type AuthUser } from "@/lib/auth";

const ROLE_TONE: Record<string, string> = {
  admin: "text-[color:var(--destructive)] bg-[color:var(--destructive)]/10",
  ops: "text-[color:var(--warning)] bg-[color:var(--warning)]/10",
  analyst: "text-primary bg-primary/10",
  viewer: "text-muted-foreground bg-muted",
};

/** Identity + sign-out pill for the topbar.
 *
 *  Reads the cached user from localStorage on mount; if no token is present
 *  we render a "Sign in" link instead. The localStorage read has to happen
 *  inside useEffect so it doesn't trip the SSR/CSR hydration mismatch — the
 *  server has no idea who the visitor is.
 */
export function UserMenu() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
    setMounted(true);
  }, []);

  function handleSignOut() {
    clearAuth();
    router.replace("/login");
  }

  if (!mounted) return null;
  if (!user) {
    return (
      <Button
        size="xs"
        variant="outline"
        onClick={() => router.push("/login")}
        className="gap-1.5"
      >
        <User className="h-3 w-3" strokeWidth={2.5} />
        Sign in
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "tabular rounded-md px-1.5 py-0.5 text-[0.62rem] font-semibold uppercase tracking-wider",
            ROLE_TONE[user.role] ?? "bg-muted text-muted-foreground",
          )}
          title={`Role: ${user.role}`}
        >
          {user.role}
        </span>
        <span className="hidden lg:inline text-[0.72rem] text-muted-foreground truncate max-w-[160px]">
          {user.display_name || user.email}
        </span>
      </div>
      <Button
        size="xs"
        variant="ghost"
        onClick={handleSignOut}
        className="px-1.5"
        title="Sign out"
      >
        <LogOut className="h-3 w-3" strokeWidth={2.5} />
      </Button>
    </div>
  );
}
