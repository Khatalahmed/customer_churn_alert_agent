"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { percent } from "@/lib/format";

/**
 * Predicted probability against what actually happened.
 *
 * The diagonal is the claim "when this model says 5%, five in a hundred
 * leave". Calibration is what lets a probability be multiplied by money, so
 * this chart is the licence for every rupee figure elsewhere in the product.
 */
export function CalibrationChart({
  rows,
}: {
  rows: { bucket: string; predicted: number; observed: number; n: number }[];
}) {
  const data = rows.map((row) => ({
    ...row,
    ideal: row.predicted,
  }));

  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="predicted"
            type="number"
            domain={["dataMin", "dataMax"]}
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickFormatter={(v: number) => percent(v, 1)}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickFormatter={(v: number) => percent(v, 1)}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--text)",
            }}
            formatter={(value, name) => [
              percent(Number(value), 2),
              String(name) === "observed" ? "actually churned" : "perfect calibration",
            ]}
            labelFormatter={(value) => `predicted ${percent(Number(value), 2)}`}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "var(--text-subtle)" }}
            formatter={(value) => (value === "observed" ? "Observed" : "Perfectly calibrated")}
          />
          <Line
            type="monotone"
            dataKey="ideal"
            stroke="var(--border-strong)"
            strokeDasharray="4 4"
            dot={false}
            strokeWidth={1.5}
          />
          <Line
            type="monotone"
            dataKey="observed"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--accent)" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
