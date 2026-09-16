"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  Radar,
  ShieldCheck,
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
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2.5 text-[13px] font-semibold transition-all duration-200",
              active
                ? "text-white shadow-[var(--shadow-accent)]"
                : "text-[var(--text-muted)] hover:-translate-y-0.5 hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
            )}
            style={active ? { background: "var(--accent-grad)" } : undefined}
          >
            <Icon className="h-[16px] w-[16px]" strokeWidth={2} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar({ analysisTime }: { analysisTime?: string }) {
  return (
    <aside className="hidden w-[232px] shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] px-4 py-5 lg:flex">
      <Link href="/dashboard" className="mb-6 flex items-center gap-2.5 px-1">
        <span
          className="flex h-9 w-9 items-center justify-center rounded-[14px] text-white shadow-[var(--shadow-accent)]"
          style={{ background: "var(--accent-grad)" }}
        >
          <ShieldCheck className="h-[18px] w-[18px]" strokeWidth={2.2} aria-hidden />
        </span>
        <span>
          <span className="block text-[15px] font-black leading-tight tracking-tight">
            ChurnGuard
          </span>
          <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--text-subtle)]">
            Retention OS
          </span>
        </span>
      </Link>

      <SidebarNav />

      <div className="mt-auto rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] p-3.5">
        <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[var(--text-subtle)]">
          Analysis time
        </p>
        <p className="tnum mt-1.5 text-[12px] font-bold text-[var(--text-muted)]">
          {analysisTime ?? "unavailable"}
        </p>
        <p className="mt-2 text-[10.5px] leading-relaxed text-[var(--text-subtle)]">
          Every figure on screen is computed as of this moment, using only data from before it.
        </p>
      </div>
    </aside>
  );
}
