"use client";

import * as React from "react";
import {
  Activity,
  Bell,
  BookOpen,
  Database,
  LayoutDashboard,
  MessageSquare,
  Settings,
  Sparkles,
  TrendingUp,
  Truck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  badge?: string | number;
}

const PRIMARY: NavItem[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "operations", label: "Operations", icon: Activity },
  { id: "logistics", label: "Logistics", icon: Truck },
  { id: "sellers", label: "Sellers", icon: Users },
  { id: "forecast", label: "Forecast", icon: TrendingUp },
  { id: "alerts", label: "Anomalies", icon: Bell, badge: "•" },
];

const SECONDARY: NavItem[] = [
  { id: "ask", label: "Ask AI", icon: MessageSquare },
  { id: "narratives", label: "Briefings", icon: BookOpen },
  { id: "data", label: "Data", icon: Database },
  { id: "data-health", label: "Data Health", icon: Activity },
];

interface SidebarProps {
  active?: string;
  onSelect?: (id: string) => void;
}

export function Sidebar({ active = "overview", onSelect }: SidebarProps) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden md:flex h-screen shrink-0 flex-col",
        "w-[60px] xl:w-[220px] transition-[width] duration-300",
        "border-r border-sidebar-border bg-sidebar/80 backdrop-blur-xl"
      )}
      aria-label="Primary navigation"
    >
      {/* Brand mark */}
      <div className="flex h-14 items-center gap-2.5 px-3 xl:px-4 border-b border-sidebar-border/80">
        <div
          className={cn(
            "relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
            "ring-1 ring-inset ring-primary/30 bg-[color:var(--surface-2)]",
            "shadow-[0_0_24px_-6px_oklch(0.795_0.135_232/0.55)]"
          )}
        >
          <Sparkles
            className="h-4 w-4 text-primary"
            strokeWidth={2.2}
            aria-hidden
          />
        </div>
        <div className="hidden xl:block min-w-0">
          <div className="text-display text-[0.82rem] font-semibold tracking-tight truncate text-brand-gradient">
            Olist DAI
          </div>
          <div className="text-[0.6rem] text-muted-foreground tracking-[0.12em] uppercase">
            Ops Console
          </div>
        </div>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 xl:px-3">
        <SectionLabel>Workspace</SectionLabel>
        <ul className="space-y-0.5">
          {PRIMARY.map((item) => (
            <NavRow
              key={item.id}
              item={item}
              isActive={active === item.id}
              onClick={() => onSelect?.(item.id)}
            />
          ))}
        </ul>

        <div className="my-3 hairline" />

        <SectionLabel>Insights</SectionLabel>
        <ul className="space-y-0.5">
          {SECONDARY.map((item) => (
            <NavRow
              key={item.id}
              item={item}
              isActive={active === item.id}
              onClick={() => onSelect?.(item.id)}
            />
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border/80 p-2 xl:p-3">
        <NavRow
          item={{ id: "settings", label: "Settings", icon: Settings }}
          isActive={active === "settings"}
          onClick={() => onSelect?.("settings")}
        />
      </div>
    </aside>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="hidden xl:block px-2 mb-1.5 text-[0.6rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
      {children}
    </div>
  );
}

function NavRow({
  item,
  isActive,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-current={isActive ? "page" : undefined}
        className={cn(
          "group/nav relative flex w-full items-center gap-2.5 rounded-md",
          "px-2 py-1.5 xl:px-2.5 xl:py-2",
          "text-[0.78rem] font-medium transition-all duration-150",
          isActive
            ? "bg-[color:var(--surface-2)] text-foreground ring-1 ring-inset ring-foreground/10"
            : "text-muted-foreground hover:bg-[color:var(--surface-1)] hover:text-foreground"
        )}
      >
        {isActive && (
          <span
            aria-hidden
            className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-primary"
          />
        )}
        <Icon
          className={cn(
            "h-4 w-4 shrink-0 transition-colors",
            isActive ? "text-primary" : "text-muted-foreground group-hover/nav:text-foreground"
          )}
          strokeWidth={2.1}
        />
        <span className="hidden xl:inline truncate">{item.label}</span>
        {item.badge != null && (
          <span
            className={cn(
              "ml-auto hidden xl:inline-flex h-1.5 w-1.5 rounded-full",
              isActive ? "bg-primary" : "bg-muted-foreground/40"
            )}
            aria-hidden
          />
        )}
      </button>
    </li>
  );
}
