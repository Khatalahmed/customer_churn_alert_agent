import Link from "next/link";
import { Search } from "lucide-react";

import { Card, Empty, ErrorPanel, PageHeader, Table, Td, Th } from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { compact, percent } from "@/lib/format";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const params = await searchParams;
  const query = params.q ?? "";
  const page = Math.max(1, Number(params.page ?? 1) || 1);
  const result = await attempt(api.customers(query, PAGE_SIZE, (page - 1) * PAGE_SIZE));

  if (isError(result)) {
    return (
      <>
        <PageHeader title="Customers" />
        <ErrorPanel message={result.error} />
      </>
    );
  }

  const pages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Customers"
        description={`Every customer the model scored at this analysis time — ${compact(result.total)} of them. Risk levels and recommendations are computed per customer, on the page.`}
      />

      {/* Search bar */}
      <form className="mb-5 flex gap-2" action="/customers">
        <label className="relative flex-1 max-w-md">
          <span className="sr-only">Search customers</span>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-subtle)]"
            aria-hidden
          />
          <input
            name="q"
            defaultValue={query}
            placeholder="Search by name or customer id"
            aria-label="Search customers"
            className="w-full rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] py-2.5 pl-10 pr-3 text-[13px] text-[var(--text)] outline-none transition-all placeholder:text-[var(--text-subtle)] focus:border-[var(--accent-deep)] focus:shadow-[0_0_0_3px_rgba(99,102,241,0.15)]"
          />
        </label>
        <button
          type="submit"
          className="rounded-[var(--radius-control)] px-4 py-2.5 text-[13px] font-semibold text-white transition-all hover:opacity-90 hover:shadow-[0_0_16px_rgba(99,102,241,0.35)]"
          style={{ background: "var(--accent-grad)" }}
        >
          Search
        </button>
        {query ? (
          <Link
            href="/customers"
            className="self-center rounded-[var(--radius-control)] border border-[var(--border)] px-3 py-2.5 text-[12px] text-[var(--text-subtle)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-muted)]"
            style={{ background: "var(--surface)" }}
          >
            Clear
          </Link>
        ) : null}
      </form>

      {result.customers.length === 0 ? (
        <Empty
          title="No customers match this search"
          body={
            query
              ? `Nothing matched "${query}". Only customers active at the analysis time are scored.`
              : "No customers were scored at this analysis time."
          }
        />
      ) : (
        <Card padded={false} className="overflow-hidden">
          <Table>
            <thead>
              <tr>
                <Th>Customer</Th>
                <Th>ID</Th>
                <Th align="right">Churn probability</Th>
                <Th align="right">Rank</Th>
              </tr>
            </thead>
            <tbody>
              {result.customers.map((customer, index) => (
                <tr key={customer.user_id} className="transition-colors hover:bg-[var(--surface-2)]">
                  <Td>
                    <Link
                      href={`/customers/${customer.user_id}`}
                      className="font-semibold transition-colors hover:text-[var(--accent)]"
                    >
                      {customer.full_name}
                    </Link>
                  </Td>
                  <Td className="tnum text-[var(--text-subtle)]">#{customer.user_id}</Td>
                  <Td align="right" className="tnum font-semibold">
                    {percent(customer.churn_probability)}
                  </Td>
                  <Td align="right" className="tnum text-[var(--text-subtle)]">
                    {(page - 1) * PAGE_SIZE + index + 1}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {pages > 1 ? (
        <nav className="mt-5 flex items-center gap-3 text-[12px]" aria-label="Pagination">
          {page > 1 ? (
            <Link
              href={`/customers?q=${encodeURIComponent(query)}&page=${page - 1}`}
              className="rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-medium transition-all hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]"
            >
              ← Previous
            </Link>
          ) : null}
          <span className="tnum text-[var(--text-subtle)]">
            Page {page} of {pages}
          </span>
          {page < pages ? (
            <Link
              href={`/customers?q=${encodeURIComponent(query)}&page=${page + 1}`}
              className="rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 font-medium transition-all hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]"
            >
              Next →
            </Link>
          ) : null}
        </nav>
      ) : null}
    </>
  );
}
