/**
 * Types for the FastAPI service in `churn/api.py`.
 *
 * These mirror the backend's payloads exactly. Where the backend can answer
 * "not produced yet", that is modelled as a union rather than optional
 * fields, so a screen cannot render a metric the pipeline never measured
 * without TypeScript objecting first.
 */

export type RiskLevel = "HIGH" | "MEDIUM" | "LOW";

/** Anything the backend may not have computed yet. */
export type Unavailable = {
  available: false;
  reason: string;
  how: string;
};

export type Maybe<T> = (T & { available: true }) | Unavailable;

export function isAvailable<T>(value: Maybe<T>): value is T & { available: true } {
  return value.available === true;
}

export type Health = {
  status: string;
  dataset_reference_time: string;
  analysis_time: string;
  active_customers: number;
  recently_contacted: number;
};

export type Evidence = {
  logins_prev_14_28d: number;
  logins_last_14d: number;
  total_orders: number;
  total_tickets: number;
  unresolved_serious_tickets: number;
  worst_review_rating: number;
};

/** One customer as the worklist and Customer 360 see them. */
export type CustomerView = {
  user_id: number;
  full_name: string;
  churn_probability: number;
  risk_level: RiskLevel;
  suggested_action: string;
  dissatisfaction: boolean;
  disengagement: boolean;
  evidence: Evidence;
  avg_order_value: number;
  orders_per_month: number;
  intervention: string;
  intervention_label: string;
  margin_at_risk: number;
  cost: number;
  expected_save: number;
  expected_value: number;
  value_range: [number, number];
  robust: boolean;
  worth_doing: boolean;
  break_even_margin: number;
  break_even_probability: number;
  /** Present only when a paid intervention was downgraded. */
  downgraded_from?: string;
  matched_fix?: string;
  matched_fix_break_even_margin?: number;
  matched_fix_break_even_probability?: number;
  contacted_recently?: boolean;
  currency: string;
};

export type Worklist = {
  analysis_time: string;
  customers: CustomerView[];
  worth_doing: number;
  expected_value_total: number;
  note: string;
};

export type Overview = {
  analysis_time: string;
  scored_customers: number;
  shortlist_size: number;
  risk_mix: Record<RiskLevel, number>;
  risk_mix_scope: string;
  margin_at_risk: number;
  intervention_cost: number;
  expected_value_total: number;
  worth_doing: number;
  probability_distribution: { from: number; to: number; count: number }[];
  currency: string;
  note: string;
};

export type CustomerSearch = {
  analysis_time: string;
  total: number;
  limit: number;
  offset: number;
  customers: { user_id: number; full_name: string; churn_probability: number }[];
};

export type TimelineEvent = {
  at: string;
  type: "order" | "ticket" | "review";
  label: string;
  tone: "good" | "bad" | "neutral";
  amount?: number;
  category?: string;
  status?: string;
  unresolved?: boolean;
  rating?: number;
  text?: string;
};

export type Timeline = {
  as_of: string;
  events: TimelineEvent[];
  logins_by_day: { at: string; count: number }[];
};

export type Explanation = Maybe<{
  basis: string;
  factors: {
    feature: string;
    label: string;
    value: number | null;
    contribution: number;
    direction: string;
  }[];
}>;

export type ToolCall = {
  tool: string;
  args: Record<string, unknown>;
  ok: boolean;
  ms: number;
};

export type Investigations = Maybe<{
  customers: (CustomerView & { reason: string })[];
  tool_calls: number;
  trace_available: boolean;
}>;

export type Investigation = Maybe<{
  customer: CustomerView & { reason: string };
  steps: ToolCall[];
  trace_available: boolean;
}>;

export type Evaluations = Maybe<{
  measured_at: string;
  horizon_days: number;
  test_cutoff: string;
  test_customers: number;
  test_churn: number;
  base_rate: number;
  cv_auc_mean: number;
  cv_auc_std: number;
  cv_auc_folds: number[];
  roc_auc: number;
  pr_auc: number;
  pr_auc_floor: number;
  pr_auc_lift: number;
  brier_raw: number;
  brier_calibrated: number;
  at_k: { k: number; precision: number; lift: number; recall: number }[];
  calibration: { bucket: string; predicted: number; observed: number; n: number }[];
  feature_importance: { feature: string; importance: number }[];
}>;

export type TrajectoryRule = { rule: string; passed: boolean; detail: string };

export type Reliability = Maybe<{
  customers: number;
  evidence: {
    checked: number;
    matched: number;
    fidelity: number;
    failures: Record<string, string[]>;
  };
  prose: {
    claims: number;
    supported: number;
    fidelity: number;
    coverage: number;
    unchecked_clauses: number;
    failures: Record<string, string[]>;
  };
  trajectory: {
    rules: TrajectoryRule[];
    passed: number;
    total: number;
    tool_calls: number;
    errors: number;
  };
}>;

export type Outcomes = Maybe<{
  analysis_time: string;
  horizon_days: number;
  treated: { n: number; churned: number; churn_rate: number; ci: [number, number] };
  control: { n: number; churned: number; churn_rate: number; ci: [number, number] };
  absolute_uplift_pp: number;
  relative_uplift: number | null;
  difference_ci_pp: [number, number];
  p_value: number;
  conclusive: boolean;
  power: {
    per_arm: number;
    base_rate: number;
    target_rate: number;
    alpha: number;
    power: number;
    assumptions: string;
    base_rate_from: string;
  };
}>;

export type Economics = Maybe<{
  currency: string;
  illustrative: boolean;
  note: string;
  assumptions: {
    margin_rate: number;
    monthly_survival: number;
    monthly_discount: number;
    value_horizon_months: number;
    uplift_uncertainty: number;
    present_value_of_1000_per_month: number;
    months_equivalent: number;
  };
  example_probability: number;
  interventions: {
    key: string;
    label: string;
    /** Assumed, never measured — the field name says so on purpose. */
    assumed_uplift: number;
    uplift_source: string;
    cost: number;
    break_even_margin: number | null;
  }[];
}>;
