"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, ShieldCheck, X } from "lucide-react";

import { CommandHint } from "./CommandPalette";
import { SidebarNav } from "./Sidebar";
import { cn } from "@/lib/format";

export type SystemStatus =
  | { ok: true; customers: number; analysisTime: string }
  | { ok: false; message: string };

/**
 * The brand band across the top of every screen — the hostel dashboard's
 * gradient header, with its dot texture and blurred highlight, carrying the
 * product identity and the live state of the service.
 */
export function Topbar({ status }: { status: SystemStatus }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <header className="brand-band sticky top-0 z-30">
        <div className="relative z-10 flex h-[60px] items-center gap-3 px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation"
            className="rounded-[var(--radius-control)] border border-white/20 bg-white/10 p-2 text-white backdrop-blur-sm transition-colors hover:bg-white/20 lg:hidden"
          >
            <Menu className="h-4 w-4" aria-hidden />
          </button>

          <Link href="/dashboard" className="flex items-center gap-2.5 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-white backdrop-blur-sm">
              <ShieldCheck className="h-4 w-4" aria-hidden />
            </span>
            <span className="text-[14px] font-black tracking-tight text-white">ChurnGuard</span>
          </Link>

          <p className="hidden text-[12.5px] font-semibold text-indigo-100 lg:block">
            Customer churn early-warning
            <span className="mx-2 opacity-40">•</span>
            <span className="font-normal text-indigo-200/80">
              predict who leaves, verify why, price the fix
            </span>
          </p>

          <div className="ml-auto flex items-center gap-2.5">
            <CommandHint />
            <div
              className="flex items-center gap-2 rounded-[var(--radius-control)] border border-white/20 bg-white/10 px-3 py-2 backdrop-blur-sm"
              title={
                status.ok
                  ? `Scoring ${status.customers.toLocaleString("en-IN")} active customers as of ${status.analysisTime}`
                  : status.message
              }
            >
              <span className="relative flex h-2 w-2" aria-hidden>
                <span
                  className={cn(
                    "absolute inline-flex h-full w-full rounded-full opacity-60",
                    status.ok ? "animate-ping bg-emerald-300" : "bg-rose-300",
                  )}
                />
                <span
                  className={cn(
                    "relative inline-flex h-2 w-2 rounded-full",
                    status.ok ? "bg-emerald-300" : "bg-rose-400",
                  )}
                />
              </span>
              <span className="hidden text-[11.5px] font-bold text-white sm:inline">
                {status.ok ? "Service online" : "Service unreachable"}
              </span>
            </div>
          </div>
        </div>
      </header>

      {menuOpen ? (
        <div
          className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMenuOpen(false)}
          role="presentation"
        >
          <div
            className="h-full w-[260px] border-r border-[var(--border)] bg-[var(--surface)] p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-5 flex items-center justify-between">
              <span className="flex items-center gap-2.5">
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-xl text-white"
                  style={{ background: "var(--accent-grad)" }}
                >
                  <ShieldCheck className="h-4 w-4" aria-hidden />
                </span>
                <span className="text-[15px] font-black tracking-tight">ChurnGuard</span>
              </span>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close navigation"
                className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-2)]"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      ) : null}
    </>
  );
}
