// Mirrors the JSON from the FastAPI service (HazardReport.to_dict / Explanation.to_dict).

export type Method = "vector" | "keyword" | "hybrid";
export type Depth = 25 | 50 | 100;
export type Signal = "LOW" | "MODERATE" | "HIGH";
export type Source = "hazard" | "title" | "description";

export interface HazardLabel {
  category: string;
  evidence: string;
  source: Source;
}

export interface StandardViolation {
  standard: string | null;
  evidence: string;
  source: Source;
}

export interface Match {
  recall_id: number;
  rank: number;
  score: number;
  cosine: number;
  title: string;
  url: string;
  recall_date: string | null;
  labels: HazardLabel[];
  violations: StandardViolation[];
  relevant: boolean;
  hazard_text: string | null;
}

export interface CategoryStat {
  code: string;
  label: string;
  count: number;
  share: number;
  base_rate: number;
  lift: number;
  signal: Signal;
  recall_ids: number[];
}

export interface Term {
  term: string;
  matches: number;
  recall_ids: number[];
}

export interface Area {
  id: string;
  title: string;
  checks: string[];
  support: number;
  recall_ids: number[];
  terms: string[];
}

export interface StandardStat {
  standard: string;
  count: number;
  recall_ids: number[];
}

export interface HazardReport {
  query: string;
  method: Method;
  k: number;
  matches: Match[];
  relevant: number;
  relevance_floor: number;
  profile: CategoryStat[];
  overall_signal: Signal;
  signal_drivers: string[];
  insufficient_evidence: boolean;
  shared_terms: Term[];
  failure_terms: Term[];
  investigation_areas: Area[];
  standards: StandardStat[];
  taxonomy_version: number;
  analysis_version: number;
  disclaimer: string;
}

export interface Sentence {
  text: string;
  citations: number[];
}

export interface Explanation {
  summary: Sentence[];
  hazards: { category: string; sentences: Sentence[] }[];
  match_reasons: { recall_id: number; shared: string[]; different: string[] }[];
  investigation_notes: { area_id: string; sentence: Sentence }[];
  notice: string | null;
  generated: boolean;
  model: string | null;
  prompt_version: number;
  usage: { input_tokens: number; output_tokens: number; reasoning_tokens: number; cost_usd: number };
  validation: {
    first_try_clean: boolean;
    retries: number;
    fallback_used: boolean;
    dropped: { where: string; reason: string; text: string }[];
    error: string | null;
  };
  caveat: string;
  disclaimer: string;
}

export interface ExplainResponse {
  report: HazardReport;
  explanation: Explanation | null;
  notice: string | null;
}

export interface Query {
  query: string;
  k: Depth;
  method: Method;
}
