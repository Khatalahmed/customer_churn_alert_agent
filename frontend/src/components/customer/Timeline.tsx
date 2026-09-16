"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Package, MessageSquare, Star } from "lucide-react";

import { Card, CardHeader, Empty } from "@/components/ui/primitives";
import { cn, day, money } from "@/lib/format";
import type { Timeline as TimelineData, TimelineEvent } from "@/types/api";

const ICONS = { order: Package, ticket: MessageSquare, review: Star } as const;

function LoginActivity({ logins }: { logins: { at: string; count: number }[] }) {
  if (logins.length === 0) return null;
  return (
    <div className="h-[110px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={logins} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
          <defs>
            <linearGradient id="logins" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="at"
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            tickFormatter={(value: string) => day(value)}
            minTickGap={40}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--text-subtle)" }}
            tickLine={false}
            axisLine={false}
            width={44}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--text)",
            }}
            labelFormatter={(value) => day(String(value))}
            formatter={(value) => [`${Number(value)} login${Number(value) === 1 ? "" : "s"}`, ""]}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="var(--accent)"
            strokeWidth={1.5}
            fill="url(#logins)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function eventDetail(event: TimelineEvent): string {
  if (event.type === "order") return money(event.amount ?? 0);
  if (event.type === "review") return `${event.rating}★`;
  return event.status ?? "";
}

export function CustomerTimeline({ timeline }: { timeline: TimelineData }) {
  const recent = [...timeline.events].reverse().slice(0, 14);

  return (
    <Card>
      <CardHeader
        title="Customer trajectory"
        description={`Everything observable before ${day(timeline.as_of)} — the history the model and the agent both worked from.`}
      />

      {timeline.logins_by_day.length > 0 ? (
        <>
          <p className="mb-1.5 text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
            Login activity
          </p>
          <LoginActivity logins={timeline.logins_by_day} />
        </>
      ) : null}

      <p className="mb-2 mt-5 text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
        Recent events
      </p>

      {recent.length === 0 ? (
        <Empty title="No recorded activity" body="This customer has no orders, tickets or reviews before the analysis time." />
      ) : (
        <ol className="relative space-y-0 border-l border-[var(--border)] pl-4">
          {recent.map((event, index) => {
            const Icon = ICONS[event.type];
            return (
              <li key={`${event.at}-${index}`} className="relative py-2">
                <span
                  className={cn(
                    "absolute -left-[21px] top-3 flex h-3.5 w-3.5 items-center justify-center rounded-full border bg-[var(--surface)]",
                    event.tone === "bad"
                      ? "border-[var(--high)]"
                      : event.tone === "good"
                        ? "border-[var(--low)]"
                        : "border-[var(--border-strong)]",
                  )}
                  aria-hidden
                >
                  <Icon
                    className={cn(
                      "h-2 w-2",
                      event.tone === "bad"
                        ? "text-[var(--high)]"
                        : event.tone === "good"
                          ? "text-[var(--low)]"
                          : "text-[var(--text-subtle)]",
                    )}
                  />
                </span>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[12.5px]">
                    {event.label}
                    {event.unresolved ? (
                      <span className="ml-1.5 text-[11px] text-[var(--high)]">still open</span>
                    ) : null}
                  </span>
                  <span className="tnum shrink-0 text-[11px] text-[var(--text-subtle)]">
                    {eventDetail(event)} · {day(event.at)}
                  </span>
                </div>
                {event.text ? (
                  <p className="mt-0.5 text-[11.5px] italic text-[var(--text-subtle)]">
                    &ldquo;{event.text}&rdquo;
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}

      {timeline.events.length > recent.length ? (
        <p className="mt-3 text-[11px] text-[var(--text-subtle)]">
          Showing the {recent.length} most recent of {timeline.events.length} events.
        </p>
      ) : null}
    </Card>
  );
}
