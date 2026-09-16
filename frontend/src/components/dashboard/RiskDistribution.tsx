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

// Custom tooltip with glassmorphism
function CustomTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border-strong)",
        borderRadius: 10,
        padding: "8px 12px",
        boxShadow: "var(--shadow-lg)",
      }}
    >
      <p style={{ fontSize: 11, color: "var(--text-subtle)", marginBottom: 4 }}>
        Churn probability from {label}
      </p>
      <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", fontVariantNumeric: "tabular-nums" }}>
        {Number(payload[0].value).toLocaleString("en-IN")} customers
      </p>
    </div>
  );
}

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
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -16 }}>
          <defs>
            {/* Safe zone gradient */}
            <linearGradient id="safeGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#c7d2fe" />
            </linearGradient>
            {/* Risk zone gradient */}
            <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#dc2626" />
              <stop offset="100%" stopColor="#f87171" />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border-strong)" }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--surface-2)" }} />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.label}
                fill={entry.shortlisted ? "url(#riskGrad)" : "url(#safeGrad)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
