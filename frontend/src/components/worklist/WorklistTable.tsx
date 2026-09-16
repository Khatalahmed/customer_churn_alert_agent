"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, Search, SlidersHorizontal, Sparkles } from "lucide-react";

import { Badge, Empty, RiskBadge, Table, Td, Th } from "@/components/ui/primitives";
import { ContactBar } from "./ContactBar";
import { cn, money, moneySigned, percent } from "@/lib/format";
import type { CustomerView } from "@/types/api";

type Filter = "all" | "HIGH" | "MEDIUM" | "LOW" | "worth" | "not-worth";
type Sort = "expected_value" | "churn_probability" | "margin_at_risk" | "risk";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "HIGH", label: "High risk" },
  { key: "MEDIUM", label: "Medium risk" },
  { key: "LOW", label: "Low risk" },
  { key: "worth", label: "Positive EV" },
  { key: "not-worth", label: "No action" },
];

const SORTS: { key: Sort; label: string }[] = [
  { key: "expected_value", label: "Highest expected value" },
  { key: "churn_probability", label: "Highest churn probability" },
  { key: "margin_at_risk", label: "Highest margin at risk" },
  { key: "risk", label: "Risk level" },
];

const RISK_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;

// Map each filter to a border/text highlight colour when active
/* The selected pill goes solid and lifts, the way the hostel's building
   filter does; the risk filters keep their own colour so the control still
   says which risk you are looking at. */
const FILTER_ACTIVE: Record<Filter, string> = {
  all: "linear-gradient(135deg,#4f46e5,#7c3aed)",
  HIGH: "linear-gradient(135deg,#dc2626,#ef4444)",
  MEDIUM: "linear-gradient(135deg,#b45309,#f59e0b)",
  LOW: "linear-gradient(135deg,#047857,#10b981)",
  worth: "linear-gradient(135deg,#047857,#10b981)",
  "not-worth": "linear-gradient(135deg,#475569,#64748b)",
};

/** The primary signal behind a verdict, in the fewest words that stay true. */
function primarySignal(customer: CustomerView): string {
  const open = customer.evidence.unresolved_serious_tickets;
  const worst = customer.evidence.worst_review_rating;
  const parts: string[] = [];
  if (open > 0) parts.push(`${open} unresolved ${open === 1 ? "complaint" : "complaints"}`);
  if (worst >= 1 && worst <= 2) parts.push(`${worst}-star review`);
  if (customer.disengagement) parts.push("logins falling");
  return parts.length ? parts.join(" · ") : "no qualifying evidence";
}

export function WorklistTable({
  customers,
  currency,
  dense = false,
}: {
  customers: CustomerView[];
  currency: string;
  dense?: boolean;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("expected_value");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number[]>([]);

  function toggle(userId: number) {
    setSelected((current) =>
      current.includes(userId)
        ? current.filter((id) => id !== userId)
        : [...current, userId],
    );
  }

  const rows = useMemo(() => {
    let result = customers;
    if (filter === "worth") result = result.filter((c) => c.worth_doing);
    else if (filter === "not-worth") result = result.filter((c) => !c.worth_doing);
    else if (filter !== "all") result = result.filter((c) => c.risk_level === filter);

    const q = query.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (c) => c.full_name.toLowerCase().includes(q) || String(c.user_id).includes(q),
      );
    }
    return [...result].sort((a, b) =>
      sort === "risk"
        ? RISK_ORDER[a.risk_level] - RISK_ORDER[b.risk_level] ||
          b.churn_probability - a.churn_probability
        : b[sort] - a[sort],
    );
  }, [customers, filter, sort, query]);

  const names = Object.fromEntries(customers.map((c) => [c.user_id, c.full_name]));

  return (
    <div>
      {!dense ? (
        <ContactBar selected={selected} names={names} onClear={() => setSelected([])} />
      ) : null}
      {!dense ? (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          {/* Filter pills */}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter worklist">
            {FILTERS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                aria-pressed={filter === option.key}
                className={cn(
                  "rounded-full px-3.5 py-1.5 text-[12px] font-bold transition-all duration-200 active:scale-95",
                  filter === option.key
                    ? "scale-105 border border-transparent text-white shadow-[var(--shadow-accent)]"
                    : "border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text-muted)] hover:-translate-y-0.5 hover:border-[var(--accent)] hover:text-[var(--accent)]",
                )}
                style={
                  filter === option.key ? { background: FILTER_ACTIVE[option.key] } : undefined
                }
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            {/* Search */}
            <label className="relative">
              <span className="sr-only">Search this worklist</span>
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-subtle)]"
                aria-hidden
              />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter by name or id"
                className="w-[200px] rounded-[var(--radius-control)] border border-[var(--border)] py-1.5 pl-8 pr-2.5 text-[12px] text-[var(--text)] outline-none transition-all placeholder:text-[var(--text-subtle)] focus:border-[var(--accent-deep)] focus:shadow-[0_0_0_2px_rgba(99,102,241,0.15)]"
                style={{ background: "var(--surface)" }}
              />
            </label>

            {/* Sort */}
            <label className="flex items-center gap-1.5 text-[12px] text-[var(--text-subtle)]">
              <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />
              <span className="sr-only">Sort by</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as Sort)}
                className="rounded-[var(--radius-control)] border border-[var(--border)] px-2.5 py-1.5 text-[12px] text-[var(--text)] outline-none transition-colors focus:border-[var(--accent-deep)]"
                style={{ background: "var(--surface)" }}
              >
                {SORTS.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      ) : null}

      {rows.length === 0 ? (
        <Empty
          title="No customers match these filters"
          body="Clear the filter or search to see the rest of the worklist."
        />
      ) : (
        <div
          className="overflow-hidden rounded-[var(--radius-card)]"
          style={{ border: "1px solid var(--border)", background: "var(--surface)" }}
        >
          <div className="max-h-[70vh] overflow-auto">
            <Table>
              <thead>
                <tr>
                  {!dense ? (
                    <Th className="w-[44px]">
                      <span className="sr-only">Select</span>
                    </Th>
                  ) : null}
                  <Th>Customer</Th>
                  <Th>Risk</Th>
                  <Th align="right">P(churn)</Th>
                  <Th>Primary signal</Th>
                  <Th>Recommended action</Th>
                  <Th align="right">Margin at risk</Th>
                  <Th align="right">Expected value</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((customer, index) => (
                  <tr
                    key={customer.user_id}
                    className={cn(
                      "group relative transition-colors hover:bg-[var(--surface-2)]",
                      // The first row under the current sort is the one to act
                      // on first; saying so is the table's whole job.
                      index === 0 && !dense && "top-pick",
                    )}
                  >
                    {/* Left accent bar for HIGH risk rows */}
                    {customer.risk_level === "HIGH" && (
                      <td
                        aria-hidden
                        className="absolute left-0 top-[1px] bottom-[1px] w-[3px]"
                        style={{ background: "var(--high-vivid)", opacity: 0.6 }}
                      />
                    )}
                    {!dense ? (
                      <Td className="w-[44px]">
                        <input
                          type="checkbox"
                          checked={selected.includes(customer.user_id)}
                          onChange={() => toggle(customer.user_id)}
                          aria-label={`Select ${customer.full_name}`}
                          className="h-4 w-4 cursor-pointer accent-[var(--accent)]"
                        />
                      </Td>
                    ) : null}
                    <Td>
                      <Link
                        href={`/customers/${customer.user_id}`}
                        className="font-semibold transition-colors hover:text-[var(--accent)]"
                      >
                        {customer.full_name}
                      </Link>
                      <div className="tnum text-[11px] text-[var(--text-subtle)]">
                        #{customer.user_id}
                      </div>
                      {index === 0 && !dense ? (
                        <span className="mt-1.5 inline-flex whitespace-nowrap items-center gap-1 rounded-full border border-[var(--border-accent)] bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-[var(--accent)]">
                          <Sparkles className="h-2.5 w-2.5" aria-hidden />
                          Act first
                        </span>
                      ) : null}
                    </Td>
                    <Td>
                      <RiskBadge level={customer.risk_level} />
                    </Td>
                    <Td align="right" className="tnum font-semibold">
                      {percent(customer.churn_probability)}
                    </Td>
                    <Td className="text-[var(--text-muted)]">{primarySignal(customer)}</Td>
                    <Td>
                      <span className="text-[var(--text)]">{customer.intervention_label}</span>
                      {customer.downgraded_from ? (
                        <div className="text-[11px] text-[var(--text-subtle)]">
                          downgraded from {customer.downgraded_from.replace(/_/g, " ")}
                        </div>
                      ) : null}
                    </Td>
                    <Td align="right" className="tnum text-[var(--text-muted)]">
                      {money(customer.margin_at_risk, currency)}
                    </Td>
                    <Td align="right" className="tnum font-semibold">
                      {moneySigned(customer.expected_value, currency)}
                    </Td>
                    <Td>
                      {customer.worth_doing ? (
                        <Badge tone={customer.robust ? "good" : "warn"}>
                          <Check className="h-3 w-3" aria-hidden />
                          {customer.robust ? "Worth doing" : "Marginal"}
                        </Badge>
                      ) : (
                        <Badge tone="neutral">No action</Badge>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </div>
      )}

      {!dense ? (
        <p className="mt-3 text-[11.5px] text-[var(--text-subtle)]">
          Showing {rows.length} of {customers.length}. &ldquo;Marginal&rdquo; means the action stops
          paying if the assumed uplift is half what we expect.
        </p>
      ) : null}
    </div>
  );
}
