"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpDown, Check, Search } from "lucide-react";

import { Badge, Empty, RiskBadge, Table, Td, Th } from "@/components/ui/primitives";
import { cn, money, moneySigned, percent } from "@/lib/format";
import type { CustomerView } from "@/types/api";

type Filter = "all" | "HIGH" | "MEDIUM" | "LOW" | "worth" | "not-worth";
type Sort = "expected_value" | "churn_probability" | "margin_at_risk" | "risk";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "HIGH", label: "High risk" },
  { key: "MEDIUM", label: "Medium risk" },
  { key: "LOW", label: "Low risk" },
  { key: "worth", label: "Positive expected value" },
  { key: "not-worth", label: "Not worth acting on" },
];

const SORTS: { key: Sort; label: string }[] = [
  { key: "expected_value", label: "Highest expected value" },
  { key: "churn_probability", label: "Highest churn probability" },
  { key: "margin_at_risk", label: "Highest margin at risk" },
  { key: "risk", label: "Risk level" },
];

const RISK_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;

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

  return (
    <div>
      {!dense ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1" role="group" aria-label="Filter worklist">
            {FILTERS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                aria-pressed={filter === option.key}
                className={cn(
                  "rounded-[var(--radius-control)] border px-2.5 py-1.5 text-[12px] transition-colors",
                  filter === option.key
                    ? "border-[var(--border-strong)] bg-[var(--surface-2)] font-medium text-[var(--text)]"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
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
                className="w-[190px] rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] py-1.5 pl-8 pr-2.5 text-[12px] outline-none placeholder:text-[var(--text-subtle)] focus:border-[var(--border-strong)]"
              />
            </label>
            <label className="flex items-center gap-1.5 text-[12px] text-[var(--text-subtle)]">
              <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
              <span className="sr-only">Sort by</span>
              <select
                value={sort}
                onChange={(event) => setSort(event.target.value as Sort)}
                className="rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[12px] text-[var(--text)] outline-none focus:border-[var(--border-strong)]"
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
        <div className="overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)]">
          <div className="max-h-[70vh] overflow-auto">
            <Table>
              <thead>
                <tr>
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
                {rows.map((customer) => (
                  <tr
                    key={customer.user_id}
                    className="group transition-colors hover:bg-[var(--surface-2)]"
                  >
                    <Td>
                      <Link
                        href={`/customers/${customer.user_id}`}
                        className="font-medium hover:text-[var(--accent)]"
                      >
                        {customer.full_name}
                      </Link>
                      <div className="tnum text-[11px] text-[var(--text-subtle)]">
                        #{customer.user_id}
                      </div>
                    </Td>
                    <Td>
                      <RiskBadge level={customer.risk_level} />
                    </Td>
                    <Td align="right" className="tnum font-medium">
                      {percent(customer.churn_probability)}
                    </Td>
                    <Td className="text-[var(--text-muted)]">{primarySignal(customer)}</Td>
                    <Td>
                      <span>{customer.intervention_label}</span>
                      {customer.downgraded_from ? (
                        <div className="text-[11px] text-[var(--text-subtle)]">
                          downgraded from {customer.downgraded_from.replace(/_/g, " ")}
                        </div>
                      ) : null}
                    </Td>
                    <Td align="right" className="tnum text-[var(--text-muted)]">
                      {money(customer.margin_at_risk, currency)}
                    </Td>
                    <Td align="right" className="tnum font-medium">
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
        <p className="mt-2.5 text-[11.5px] text-[var(--text-subtle)]">
          Showing {rows.length} of {customers.length}. &ldquo;Marginal&rdquo; means the action stops
          paying if the assumed uplift is half what we expect.
        </p>
      ) : null}
    </div>
  );
}
