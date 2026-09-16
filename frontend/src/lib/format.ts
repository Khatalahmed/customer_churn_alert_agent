/**
 * Formatting. One module, because "how many decimals does a probability get?"
 * must have exactly one answer across six screens.
 *
 * The rule throughout: show the precision the number actually carries. A
 * churn probability measured on 35 events does not deserve four decimals, and
 * printing 0.132384728 tells the reader the system cannot tell what matters.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { RiskLevel } from "@/types/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 0.1324 -> "13.2%" */
export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** 0.1324 -> "13%" for dense tables where a decimal adds nothing. */
export function percentShort(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Percentage POINTS, signed: -9.1 -> "−9.1 pp". Never confuse with percent(). */
export function points(value: number, digits = 1): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)} pp`;
}

export function money(value: number, currency = "Rs"): string {
  const symbol = currency === "Rs" ? "₹" : currency;
  const rounded = Math.round(value);
  return `${symbol}${rounded.toLocaleString("en-IN")}`;
}

/** Signed money, for expected values that can be negative. */
export function moneySigned(value: number, currency = "Rs"): string {
  const sign = value < 0 ? "−" : "";
  return `${sign}${money(Math.abs(value), currency)}`;
}

export function lift(value: number): string {
  return `${value.toFixed(1)}×`;
}

export function ratio(a: number, b: number): string {
  return `${a} / ${b}`;
}

export function decimal(value: number, digits = 3): string {
  return value.toFixed(digits);
}

export function compact(value: number): string {
  return value.toLocaleString("en-IN");
}

/** "2026-08-04 06:30:00" -> "4 Aug 2026" */
export function day(value: string): string {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** "2026-08-04 06:30:00" -> "4 Aug 2026, 06:30" */
export function moment(value: string): string {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return `${day(value)}, ${date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function duration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Turn "resolve_open_ticket" into "Resolve open ticket". */
export function humanise(value: string): string {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export const riskStyles: Record<RiskLevel, { text: string; chip: string; dot: string }> = {
  HIGH: {
    text: "text-[var(--high)]",
    chip: "bg-[var(--high-soft)] text-[var(--high)] border-[var(--high-border)]",
    dot: "bg-[var(--high)]",
  },
  MEDIUM: {
    text: "text-[var(--medium)]",
    chip: "bg-[var(--medium-soft)] text-[var(--medium)] border-[var(--medium-border)]",
    dot: "bg-[var(--medium)]",
  },
  LOW: {
    text: "text-[var(--low)]",
    chip: "bg-[var(--low-soft)] text-[var(--low)] border-[var(--low-border)]",
    dot: "bg-[var(--low)]",
  },
};
