export interface Ticket {
  ticket_id: string;
  customer_reference: string;
  subject: string;
  category: string;
  priority: string;
  region: string;
  current_team: string;
  current_status: string;
  created_at: string;
  updated_at: string;
  promised_date: string | null;
  actual_resolution_date: string | null;
  sla_status: string;
  progress_state: string | null;
  date_status: string | null;
  risk: string | null;
  days_remaining: number | null;
  grounding_score: number | null;
}

export interface EventRecord {
  event_id: string;
  timestamp: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  region: string;
  team: string;
  old_status: string | null;
  new_status: string | null;
  message: string;
  dependency_id: string | null;
  vendor: string | null;
  approval_type: string | null;
  promised_date: string | null;
  is_duplicate: boolean;
  is_out_of_order: boolean;
  conflict_flag: boolean;
}

export interface TimelineEntry {
  index: number;
  event_id: string;
  timestamp: string;
  event_type: string;
  title: string;
  description: string;
  region: string;
  team: string;
  actor: string;
  flags: string[];
}

export interface Timeline {
  ticket_id: string;
  entries: TimelineEntry[];
  duplicates: string[];
  out_of_order: string[];
  conflicts: string[];
  total: number;
}

export interface Claim {
  category: string;
  text: string;
  evidence: string[];
  supported: boolean;
}

export interface EvidenceItem {
  event_id: string;
  event_type: string;
  timestamp: string;
  text: string;
  reason: string;
}

export interface ExplanationPayload {
  ticket_id: string;
  progress_state: string;
  effective_status: string;
  date_status: string | null;
  risk: string | null;
  grounding_score: number | null;
  grounding_breakdown: string[];
  explanation: string;
  claims: Claim[];
  evidence: EvidenceItem[];
  next_action: string | null;
  next_action_evidence: string[];
  promised_date: string | null;
  days_remaining: number | null;
  insufficient_evidence: boolean;
  conflicts: string[];
  model_version: string;
  rules_version: string;
  is_baseline: boolean;
  explanation_id?: number;
}

export interface DependencyInfo {
  dependency_id: string;
  title: string;
  kind: string;
  status: string;
  owner: string;
  created_at: string;
  completed_at: string | null;
  age_days: number | null;
  source_event_id: string;
  latest_update_message: string;
}

export interface ProgressResult {
  ticket_id: string;
  progress_state: string;
  effective_status: string;
  date_status: string | null;
  risk: string | null;
  days_remaining: number | null;
  overdue_days: number;
  promised_date: string | null;
  next_action: string | null;
  next_action_evidence: string[];
  reasons: string[];
  evidence_ids: string[];
  blockers: string[];
  waiting_on: string | null;
}

export interface DashboardMetrics {
  totals: Record<string, number>;
  states: Record<string, number>;
  status: Record<string, number>;
  regions: Record<string, number>;
  priorities: Record<string, number>;
  evaluation: Record<string, number> | null;
  avg_grounding_score: number | null;
}

export interface EvalSummary {
  has_run: boolean;
  num_cases?: number;
  prototype_mean_understanding?: number;
  baseline_mean_understanding?: number;
  baseline_followup_rate?: number;
  prototype_followup_rate?: number;
  understanding_improvement_pct?: number;
  followup_reduction_pct?: number;
  state_accuracy?: number;
  blocker_accuracy?: number;
  next_action_accuracy?: number;
  promised_date_accuracy?: number;
  grounding_accuracy?: number;
}

export interface EvalRow {
  case_id: string;
  ticket_id: string;
  expected_state: string;
  expected_date_status: string;
  difficulty: string;
  failure_case: string;
  baseline_explanation: string;
  prototype_explanation: string;
  baseline_understanding: number;
  prototype_understanding: number;
  baseline_followup: boolean;
  prototype_followup: boolean;
  state_match: boolean;
  blocker_match: boolean;
  next_action_match: boolean;
  date_match: boolean;
  grounding_score: number;
  grounding_ok: boolean;
}

export interface AuditRecord {
  audit_id: number;
  timestamp: string;
  actor: string;
  role: string;
  action: string;
  ticket_id: string | null;
  old_value: string | null;
  new_value: string | null;
  reason: string;
  source: string;
}

export interface ExplanationVersion {
  id: number;
  version: number;
  status: string;
  is_baseline: boolean;
  generated_at: string;
  state: string;
  score: number;
  source_version: number | null;
  reviewed_by?: string | null;
  published_at?: string | null;
}