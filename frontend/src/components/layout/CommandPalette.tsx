"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Search, User, Zap } from "lucide-react";

import { cn, percent } from "@/lib/format";

type Customer = { user_id: number; full_name: string; churn_probability: number };

const PAGES = [
  { label: "Overview", href: "/dashboard", hint: "What needs attention" },
  { label: "Worklist", href: "/worklist", hint: "Today's work queue" },
  { label: "Customers", href: "/customers", hint: "Search everyone scored" },
  { label: "Investigations", href: "/investigations", hint: "The agent's runs" },
  { label: "Analytics", href: "/analytics", hint: "Intervention economics" },
  { label: "Evaluations", href: "/evaluations", hint: "Model and agent reliability" },
];

const MIN_QUERY = 2;

/**
 * Command palette. Pages match locally; customers come from the search
 * endpoint, debounced, so typing a name does not fire a request per keystroke.
 *
 * State is reset where the state changes (in the open/close handler) rather
 * than in an effect watching it: an effect that immediately sets state causes
 * a second render pass for something the event already knew.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setCustomers([]);
    setCursor(0);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => {
          if (value) {
            setQuery("");
            setCustomers([]);
            setCursor(0);
          }
          return !value;
        });
      }
      if (event.key === "Escape") close();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const trimmed = query.trim();
  useEffect(() => {
    if (!open || trimmed.length < MIN_QUERY) return;
    let cancelled = false;
    const id = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/customers?q=${encodeURIComponent(trimmed)}&limit=6`);
        if (!response.ok || cancelled) return;
        const body = (await response.json()) as { customers: Customer[] };
        if (!cancelled) setCustomers(body.customers ?? []);
      } catch {
        // A dead search box is not an error worth showing: pages still match.
      }
    }, 160);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
    };
  }, [trimmed, open]);

  const results = useMemo(() => {
    const pages = PAGES.filter((page) =>
      `${page.label} ${page.hint}`.toLowerCase().includes(trimmed.toLowerCase()),
    ).map((page) => ({
      kind: "page" as const,
      href: page.href,
      label: page.label,
      hint: page.hint,
    }));

    // Stale results are filtered at render rather than cleared in an effect.
    const people =
      trimmed.length < MIN_QUERY
        ? []
        : customers.map((customer) => ({
            kind: "customer" as const,
            href: `/customers/${customer.user_id}`,
            label: customer.full_name,
            hint: `${percent(customer.churn_probability)} churn risk · #${customer.user_id}`,
          }));

    return [...pages, ...people];
  }, [trimmed, customers]);

  function go(href: string) {
    close();
    router.push(href);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}
      onClick={close}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="animate-scale-in w-full max-w-xl overflow-hidden rounded-[var(--radius-lg)]"
        style={{
          background: "rgba(10,10,20,0.92)",
          border: "1px solid var(--border-strong)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          boxShadow: "0 24px 80px rgba(0,0,0,0.7), 0 0 40px rgba(99,102,241,0.12)",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        {/* Search input row */}
        <div
          className="flex items-center gap-3 px-4"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <Search className="h-4 w-4 shrink-0 text-[var(--accent)]" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setCursor((c) => Math.min(c + 1, results.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setCursor((c) => Math.max(c - 1, 0));
              }
              if (event.key === "Enter" && results[cursor]) go(results[cursor].href);
            }}
            placeholder="Search customers, or jump to a page…"
            aria-label="Search"
            className="w-full bg-transparent py-4 text-[14px] text-[var(--text)] outline-none placeholder:text-[var(--text-subtle)]"
          />
          <kbd
            className="rounded-md border border-[var(--border-strong)] px-2 py-1 text-[10px] font-medium text-[var(--text-subtle)]"
            style={{ background: "var(--surface-2)" }}
          >
            esc
          </kbd>
        </div>

        {/* Results list */}
        <ul className="max-h-[320px] overflow-y-auto p-2">
          {results.length === 0 ? (
            <li className="flex flex-col items-center justify-center px-3 py-10 text-center">
              <div
                className="mb-3 flex h-9 w-9 items-center justify-center rounded-full"
                style={{ background: "var(--surface-2)" }}
              >
                <Search className="h-4 w-4 text-[var(--text-subtle)]" aria-hidden />
              </div>
              <p className="text-[12.5px] text-[var(--text-subtle)]">
                {trimmed.length < MIN_QUERY
                  ? "Type at least two characters to search customers."
                  : "No matches found."}
              </p>
            </li>
          ) : (
            results.map((result, index) => (
              <li key={`${result.kind}-${result.href}`}>
                <button
                  type="button"
                  onMouseEnter={() => setCursor(index)}
                  onClick={() => go(result.href)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-[var(--radius-control)] px-3 py-2.5 text-left transition-colors",
                    index === cursor
                      ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "text-[var(--text-muted)] hover:bg-[var(--surface-2)]",
                  )}
                >
                  <span
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                    style={{
                      background: index === cursor ? "rgba(99,102,241,0.2)" : "var(--surface-2)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    {result.kind === "customer" ? (
                      <User className="h-3.5 w-3.5" aria-hidden />
                    ) : (
                      <Zap className="h-3.5 w-3.5" aria-hidden />
                    )}
                  </span>
                  <span className={cn("flex-1 text-[13px] font-medium", index === cursor ? "text-[var(--text)]" : "")}>
                    {result.label}
                  </span>
                  <span className="text-[11px] text-[var(--text-subtle)]">{result.hint}</span>
                  {index === cursor && (
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden />
                  )}
                </button>
              </li>
            ))
          )}
        </ul>

        {/* Footer hint */}
        <div
          className="flex items-center gap-3 px-4 py-2.5"
          style={{ borderTop: "1px solid var(--border)", background: "var(--surface-2)" }}
        >
          <span className="text-[10.5px] text-[var(--text-subtle)]">
            <kbd className="rounded border border-[var(--border)] px-1 py-0.5 font-sans">↑↓</kbd>{" "}
            navigate
          </span>
          <span className="text-[10.5px] text-[var(--text-subtle)]">
            <kbd className="rounded border border-[var(--border)] px-1 py-0.5 font-sans">↵</kbd>{" "}
            select
          </span>
          <span className="text-[10.5px] text-[var(--text-subtle)]">
            <kbd className="rounded border border-[var(--border)] px-1 py-0.5 font-sans">esc</kbd>{" "}
            close
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Whether this is an Apple keyboard, read through useSyncExternalStore so the
 * server and the first client render agree (both say "Ctrl") and the real
 * value arrives without a state write inside an effect.
 */
const noop = () => () => {};
function useIsMac() {
  return useSyncExternalStore(
    noop,
    () => /Mac|iPhone|iPad/.test(navigator.platform),
    () => false,
  );
}

/** The affordance that tells people the palette exists. */
export function CommandHint() {
  const mac = useIsMac();
  return (
    <button
      type="button"
      onClick={() =>
        window.dispatchEvent(
          new KeyboardEvent("keydown", { key: "k", ctrlKey: !mac, metaKey: mac, bubbles: true }),
        )
      }
      className="flex items-center gap-2 rounded-[var(--radius-control)] border border-white/20 bg-white/10 px-3 py-2 text-[12px] font-semibold text-indigo-100 backdrop-blur-sm transition-all hover:bg-white/20 hover:text-white active:scale-95"
    >
      <Search className="h-3.5 w-3.5" aria-hidden />
      <span className="hidden sm:inline">Search</span>
      <kbd className="tnum rounded border border-white/25 bg-white/10 px-1.5 py-0.5 text-[10px] text-white">
        {mac ? "⌘K" : "Ctrl K"}
      </kbd>
    </button>
  );
}
