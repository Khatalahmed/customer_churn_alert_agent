"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { percent } from "@/lib/format";

/**
 * The shape of risk across everyone scored.
 *
 * This chart exists to make one point the metric cards cannot: almost the
 * entire customer base sits at a very low probability, and the shortlist is
 * the thin tail on the right. Without it, "13% risk" looks small; with it,
 * that 13% is visibly the top of the distribution.
 */
export function RiskDistribution({
  bins,
  cutoff,
}: {
  bins: { from: number; to: number; count: number }[];
  cutoff: number;
}) {
  const data = bins.map((bin) => ({
    label: percent(bin.from, 1),
    from: bin.from,
    count: bin.count,
    shortlisted: bin.from >= cutoff,
  }));

  return (
    <div className="h-[196px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--text)",
            }}
            formatter={(value) => [`${Number(value).toLocaleString("en-IN")} customers`, ""]}
            labelFormatter={(label) => `Churn probability from ${String(label)}`}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.label}
                fill={entry.shortlisted ? "var(--high)" : "var(--border-strong)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
