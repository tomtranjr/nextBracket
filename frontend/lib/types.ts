// Hand-written mirror of backend/app/models.py. Keep the two in sync: a renamed or added
// field in a Pydantic model needs the same change here. Dates travel as ISO strings.

export type Sex = "M" | "F";

export interface Profile {
  age: number;
  sex: Sex;
  // The backend defaults this to false. The API rejects keys it does not know.
  is_afspecwar_eod?: boolean;
}

/** Raw results by event: reps, shuttles, or seconds. WHtR is in hundredths (0.49 is 49). */
export interface Results {
  values: Record<string, number>;
}

export type Category = "excellent" | "satisfactory" | "unsatisfactory";

export interface ComponentScore {
  component: string;
  event: string;
  result: number;
  points: number;
  max_points: number;
  // null when the component has no minimum (body composition).
  minimum_met: boolean | null;
  // The chart minimum in the same units as `result`. null when there is no minimum.
  minimum: number | null;
  // Distance from the minimum on a miss. null when met or no minimum.
  minimum_gap: number | null;
  // The top chart row (full points), in the same units as `result`.
  full_points_at: number;
  // Distance from the top row. null when the result already earns full points.
  full_points_gap: number | null;
}

/** The 2 km walk result. Pass/fail, no points (DAFMAN 36-2905 para 3.7.3). */
export interface WalkScore {
  result: number;
  max_time: number;
  passed: boolean;
  // Seconds over max_time on a fail. null on a pass.
  gap: number | null;
}

export interface ScoreReport {
  version: string;
  effective_date: string;
  components: ComponentScore[];
  // With any not-scored component, total and category are null.
  not_scored: string[];
  total: number | null;
  category: Category | null;
  missed_minimums: string[];
  // What total is out of before scaling: 100, or 50 for a walker (no cardio points).
  points_possible: number;
  // Set when the member walked. Cardio is then not in components.
  walk: WalkScore | null;
  // Rules the report applies that the regulation does not state outright.
  assumptions: string[];
}

export interface Bracket {
  threshold: number;
  points: number;
}

export interface EventTable {
  sex: Sex;
  age_min: number;
  // null means open-ended (60 and over).
  age_max: number | null;
  event: string;
  unit: string;
  higher_is_better: boolean;
  component_minimum: number | null;
  // Best result first, as printed in the charts.
  brackets: Bracket[];
}

export interface ComponentStandards {
  component: string;
  max_points: number;
  has_minimum: boolean;
  tables: EventTable[];
}

/** The 2 km walk maximum time for one sex and age band (DAFMAN 36-2905 Table 3.1). */
export interface WalkStandard {
  sex: Sex;
  age_min: number;
  // null means open-ended (60 and over).
  age_max: number | null;
  // Seconds. A time at or under this passes.
  max_time: number;
}

export interface StandardsTable {
  version: string;
  effective_date: string;
  passing_total: number;
  components: ComponentStandards[];
  // The walk row for the profile. null when `event` asked for a scored event only.
  walk: WalkStandard | null;
}

export interface EventChange {
  component: string;
  event: string;
  unit: string;
  // null when the member gave no result for this component.
  from_result: number | null;
  to_result: number;
  // to_result - from_result: negative when lower is better.
  delta: number | null;
  from_points: number;
  to_points: number;
}

export type PlanOptionKind = "single_event" | "quick_wins" | "balanced";

export interface PlanOption {
  kind: PlanOptionKind;
  changes: EventChange[];
  projected_total: number;
}

export type PlanStatus = "already_met" | "options" | "impossible";

export interface PlanResult {
  version: string;
  effective_date: string;
  target: number;
  status: PlanStatus;
  current_total: number;
  max_total: number;
  assumed_components: string[];
  options: PlanOption[];
}

export interface ScoreRequest {
  profile: Profile;
  results: Results;
  // Omit to use the newest standards in force today.
  version?: string | null;
}

export interface PlanRequest {
  profile: Profile;
  // Composite points, 0 to 100.
  target: number;
  current?: Results | null;
  version?: string | null;
}

export interface StandardsRequest {
  profile: Profile;
  // Omit for every event.
  event?: string | null;
  version?: string | null;
}

export interface VersionInfo {
  version: string;
  effective_date: string;
  source: string;
}

export interface VersionsResponse {
  default: string;
  versions: VersionInfo[];
}
