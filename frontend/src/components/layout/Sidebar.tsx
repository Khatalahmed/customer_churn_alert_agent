"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  Radar,
  Users,
} from "lucide-react";

import { cn } from "@/lib/format";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/worklist", label: "Worklist", icon: ListChecks },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/investigations", label: "Investigations", icon: Radar },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/evaluations", label: "Evaluations", icon: FlaskConical },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 py-[7px] text-[13px] transition-colors",
              active
                ? "bg-[var(--surface-2)] font-medium text-[var(--text)]"
                : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
            )}
          >
            <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar({ analysisTime }: { analysisTime?: string }) {
  return (
    <aside className="hidden w-[218px] shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] px-3 py-4 lg:flex">
      <Link href="/dashboard" className="mb-5 flex items-center gap-2 px-2.5">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--accent)] text-[12px] font-bold text-white">
          C
        </span>
        <span className="text-[14px] font-semibold tracking-tight">ChurnGuard</span>
      </Link>
      <SidebarNav />
      <div className="mt-auto px-2.5 pt-6">
        <p className="text-[10.5px] uppercase tracking-wide text-[var(--text-subtle)]">
          Analysis time
        </p>
        <p className="tnum mt-1 text-[11.5px] text-[var(--text-muted)]">
          {analysisTime ?? "unavailable"}
        </p>
        <p className="mt-2 text-[10.5px] leading-relaxed text-[var(--text-subtle)]">
          Every figure on screen is computed as of this moment, using only data from before it.
        </p>
      </div>
    </aside>
  );
}
