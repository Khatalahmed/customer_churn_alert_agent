import Link from "next/link";

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
        title="Customers"
        description={`Every customer the model scored at this analysis time — ${compact(result.total)} of them. Risk levels and recommendations are computed per customer, on the page.`}
      />

      <form className="mb-4 flex gap-2" action="/customers">
        <input
          name="q"
          defaultValue={query}
          placeholder="Search by name or customer id"
          aria-label="Search customers"
          className="w-full max-w-sm rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] outline-none placeholder:text-[var(--text-subtle)] focus:border-[var(--border-strong)]"
        />
        <button
          type="submit"
          className="rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[12.5px] font-medium transition-colors hover:border-[var(--border-strong)]"
        >
          Search
        </button>
        {query ? (
          <Link
            href="/customers"
            className="self-center text-[12px] text-[var(--text-subtle)] hover:text-[var(--text)]"
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
              ? `Nothing matched “${query}”. Only customers active at the analysis time are scored.`
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
                      className="font-medium hover:text-[var(--accent)]"
                    >
                      {customer.full_name}
                    </Link>
                  </Td>
                  <Td className="tnum text-[var(--text-subtle)]">#{customer.user_id}</Td>
                  <Td align="right" className="tnum font-medium">
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
        <nav className="mt-4 flex items-center gap-3 text-[12px]" aria-label="Pagination">
          {page > 1 ? (
            <Link
              href={`/customers?q=${encodeURIComponent(query)}&page=${page - 1}`}
              className="rounded-[var(--radius-control)] border border-[var(--border)] px-2.5 py-1.5 hover:border-[var(--border-strong)]"
            >
              Previous
            </Link>
          ) : null}
          <span className="tnum text-[var(--text-subtle)]">
            Page {page} of {pages}
          </span>
          {page < pages ? (
            <Link
              href={`/customers?q=${encodeURIComponent(query)}&page=${page + 1}`}
              className="rounded-[var(--radius-control)] border border-[var(--border)] px-2.5 py-1.5 hover:border-[var(--border-strong)]"
            >
              Next
            </Link>
          ) : null}
        </nav>
      ) : null}
    </>
  );
}
