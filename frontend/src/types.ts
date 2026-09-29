export type Case = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  notes: string;
  report_draft: string;
  report_author: "analyst" | "deterministic" | "model";
  evidence_count?: number;
  finding_count?: number;
};
export type Artifact = {
  id: string;
  case_id: string;
  name: string;
  sha256: string;
  size: number;
  kind: string;
  mime: string;
  role: string;
  parent_id: string | null;
  run_id: string | null;
  location: Record<string, unknown>;
  metadata: Record<string, unknown>;
  depth: number;
  created_at: string;
  duplicate?: boolean;
};
export type Finding = {
  id: string;
  fingerprint: string;
  artifact_id: string;
  source_sha256: string;
  analyzer: string;
  analyzer_version: string;
  title: string;
  interpretation: string;
  category: string;
  location: Record<string, unknown>;
  limitations: string;
  supporting: string[];
  contradictory: string;
  measurements: Record<string, unknown>;
  review: {
    status: "unreviewed" | "reviewed" | "inconclusive" | "false_positive";
    note: string;
  };
};
export type Job = {
  id: string;
  status: string;
  profile: string;
  artifact_ids: string[];
  completed: number;
  total: number;
  error?: string;
  created_at: string;
  cancel_requested: boolean;
  budget: Record<string, number>;
};
export type Result = {
  entropy?: number;
  windows?: { offset: number; length: number; entropy: number }[];
  histograms?: Record<string, number[]>;
  waveform?: { time: number; min: number; max: number }[];
  [key: string]: unknown;
};
export type Run = {
  id: string;
  job_id: string;
  artifact_id: string;
  analyzer: string;
  version: string;
  status: string;
  error?: string;
  result: Result;
  started_at: string;
  duration_seconds?: number;
  parameters: Record<string, unknown>;
};
export type Claim = { text: string; citations: string[] };
export type Message = {
  id: string;
  provider: string;
  question: string;
  created_at: string;
  content: {
    facts: Claim[];
    hypotheses: Claim[];
    actions: Claim[];
    notice: string;
  };
};
export type Snapshot = {
  case: Case;
  artifacts: Artifact[];
  findings: Finding[];
  jobs: Job[];
  runs: Run[];
  messages: Message[];
};
export type Provider = "deterministic" | "local" | "hosted";
export type Health = {
  version: string;
  analyzers: {
    id: string;
    name: string;
    kinds: string[];
    capability: { available: boolean };
    deep_only: boolean;
  }[];
  providers: Record<
    Provider,
    { available: boolean; label: string; model?: string }
  >;
  ml: { available: boolean };
  doctor: {
    versions: Record<string, string>;
    tools: Record<
      string,
      { available: boolean; purpose: string; path?: string }
    >;
  };
  limits: { upload_bytes: number; workers: number; queue: number };
};
export type Progress = {
  seq: number;
  stage: string;
  completed?: number;
  total?: number;
  time: string;
};
