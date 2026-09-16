"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

import { CommandHint } from "./CommandPalette";
import { SidebarNav } from "./Sidebar";
import { cn } from "@/lib/format";

export type SystemStatus =
  | { ok: true; customers: number; analysisTime: string }
  | { ok: false; message: string };

export function Topbar({ status }: { status: SystemStatus }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-[52px] items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)]/85 px-4 backdrop-blur">
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          aria-label="Open navigation"
          className="rounded-[var(--radius-control)] border border-[var(--border)] p-1.5 lg:hidden"
        >
          <Menu className="h-4 w-4" aria-hidden />
        </button>

        <Link href="/dashboard" className="flex items-center gap-2 lg:hidden">
          <span className="text-[13px] font-semibold tracking-tight">ChurnGuard</span>
        </Link>

        <div className="ml-auto flex items-center gap-3">
          <CommandHint />
          <div
            className="flex items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border)] px-2.5 py-1.5"
            title={
              status.ok
                ? `Scoring ${status.customers.toLocaleString("en-IN")} active customers as of ${status.analysisTime}`
                : status.message
            }
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                status.ok ? "bg-[var(--low)]" : "bg-[var(--high)]",
              )}
              aria-hidden
            />
            <span className="text-[11.5px] text-[var(--text-muted)]">
              {status.ok ? "Service online" : "Service unreachable"}
            </span>
          </div>
        </div>
      </header>

      {menuOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setMenuOpen(false)}
          role="presentation"
        >
          <div
            className="h-full w-[240px] border-r border-[var(--border)] bg-[var(--surface)] p-3"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between px-2">
              <span className="text-[14px] font-semibold tracking-tight">ChurnGuard</span>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Close navigation"
                className="rounded-md p-1"
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
