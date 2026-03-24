// Core types
export type WorkflowStatus =
  | "pending"
  | "planning"
  | "in_progress"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type TaskStatus =
  | "pending"
  | "blocked"
  | "ready"
  | "in_progress"
  | "verifying"
  | "passed"
  | "failed"
  | "skipped"
  | "cancelled";

export interface Workflow {
  id: string;
  spec_id?: string;
  status: WorkflowStatus;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  replan_count: number;
  total_cost_usd: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  created_at: string;
  completed_at?: string | null;
  spec_yaml?: string;
  spec_metadata?: Record<string, unknown>;
  workspace_dir?: string;
  input_context?: Record<string, unknown>[];
  template_name?: string;
  plan_checker_score?: number | null;
  plan_judge_score?: number | null;
  plan_quality?: {
    checker?: { score: number; valid: boolean; issues: string[] };
    judge?: { score: number; approved: boolean; issues: { task_id: string; severity: string; reason: string; suggestion: string }[] } | null;
  } | null;
}

export type WorkstreamStatus = "pending" | "in_progress" | "completed" | "failed" | "cancelled";

export interface Workstream {
  id: string;
  workflow_id: string;
  name: string;
  description: string;
  status: string;
  task_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface VerificationTestResult {
  name: string;
  passed: boolean;
  error_message?: string;
}

export interface VerificationFeedback {
  attempt: number;
  score: number;
  passed: boolean;
  feedback?: string;
  verifier_type: string;
  suggested_improvements: string[];
  test_results: VerificationTestResult[];
}

export interface TaskResult {
  output: string;
  token_usage: number;
  wall_seconds: number;
  artifacts?: Record<string, string>;
  [key: string]: unknown;
}

export interface Task {
  id: string;
  workstream_id: string;
  workflow_id: string;
  title: string;
  description: string;
  status: string;
  assigned_agent_id?: string;
  acceptance_criteria_ids: string[];
  verification_strategy: string;
  skeleton_tests: unknown[];
  result?: TaskResult;
  attempt: number;
  max_retries: number;
  priority: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  attempt_feedback: VerificationFeedback[];
  output?: string;
  error?: string;
}

export interface Agent {
  id: string;
  name: string;
  transport: string;
  description: string;
  endpoint: string;
  capabilities: string[];
  max_concurrency: number;
  max_context_tokens: number;
  budget?: Record<string, unknown>;
  mcp_servers: unknown[];
  integration?: string;
  prompt_template?: string;
  model_override?: string;
}

export interface UsageRecord {
  id: number;
  workflow_id: string;
  task_id?: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  source: string;
  created_at: string;
}

export interface Learning {
  id: string;
  content: string;
  keywords: string[];
  source_workflow_id?: string;
  source_task_id?: string;
  agent_id?: string;
  success_count: number;
  retrieval_count: number;
  created_at: string;
}

// P9: Schedule types

export interface Schedule {
  id: string;
  name: string;
  cron_expression: string;
  workflow_description: string;
  provider: string;
  model: string;
  active: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ScheduleExecution {
  id: number;
  schedule_id: string;
  workflow_id?: string;
  status: string;
  started_at: string;
  completed_at?: string;
  error?: string;
}

// P11: Credential, Preset & Integration types

export interface IntegrationTestCheck {
  passed: boolean;
  message: string;
}

export interface IntegrationTestResult {
  passed: boolean;
  success: boolean;
  message: string;
  error?: string;
  checks: IntegrationTestCheck[];
  details?: Record<string, unknown>;
}

export interface Credential {
  id: string;
  integration_name: string;
  env_var_name: string;
  value: string;
  created_at: string;
  updated_at: string;
}

export interface AgentPreset {
  id: string;
  name: string;
  description: string;
  integration?: string;
  prompt_template: string;
  model_override: string;
  capabilities: string[];
  max_context_tokens: number;
  budget?: Record<string, unknown>;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
}

// Extension types

export interface Extension {
  name: string;
  type: "integration" | "template" | "agent";
  version: string;
  author: string;
  description: string;
  tags: string[];
  domain_tags: string[];
  category: string;
  use_cases: string[];
  installed: boolean;
  cost_tier?: number;
  required_env?: { name: string; description: string; link: string }[];
  prefill?: string;
  requires?: string[];
  capabilities?: string[];
  integration?: string;
  model_override?: string;
  prompt_template?: string;
}

// P7/P8: Integration types

export interface Integration {
  name: string;
  description: string;
  category: string;
  domain_tags: string[];
  transport: string;
  author: string;
  version: string;
  source: string;
  cost_tier: number;
  server_count: number;
  available: boolean;
  required_env: string[];
  missing_env: string[];
}

export interface LibraryIntegration {
  name: string;
  description: string;
  category: string;
  domain_tags: string[];
  author: string;
  version: string;
  cost_tier: number;
  install_count: number;
  servers: { name: string; transport: string; required_env: string[]; env?: Record<string, string>; args?: string[] }[];
}

// P10: Export types

export interface SharedLink {
  token: string;
  workflow_id: string;
  created_at: string;
  expires_at?: string;
  url: string;
}

// P13: Performance snapshot types

export interface PerformanceSnapshot {
  id: number;
  workflow_id: string;
  provider: string;
  model: string;
  task_type: string;
  total_tasks: number;
  passed_tasks: number;
  pass_rate: number;
  avg_cost: number;
  total_cost: number;
  quality_score: number;
  created_at: string;
}

// P12: Marketplace types

export type StudioItemStatus = "draft" | "published" | "installed";

export interface MarketplaceTemplate {
  name: string;
  title: string;
  description: string;
  category: "builtin" | "community" | "user";
  author: string;
  version: string;
  tags: string[];
  install_count: number;
  source?: string;
  spec_yaml?: string;
  status?: StudioItemStatus;
  owner_id?: string;
  forked_from?: string;
  installed_from?: string;
  pricing_tier?: string;
  export_ready?: boolean;
  source_workflow_id?: string;
}

export interface MarketplaceAgent {
  name: string;
  description: string;
  category: "community" | "user";
  author: string;
  version: string;
  tags: string[];
  preset_data: Record<string, unknown>;
  install_count: number;
  source?: string;
  status?: StudioItemStatus;
  owner_id?: string;
  forked_from?: string;
  installed_from?: string;
  pricing_tier?: string;
}

// P15b: Personal dashboard types

export interface UserPreferences {
  default_provider?: string;
  default_model?: string;
  integration_preferences?: string[];
}

export interface UserGoal {
  id: string;
  user_id: string;
  title: string;
  description: string;
  status: string;
  target_date?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface UserRole {
  id: string;
  user_id: string;
  title: string;
  department: string;
  context: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserOutcome {
  id: string;
  user_id: string;
  workflow_id: string;
  goal_id?: string;
  outcome_type: string;
  summary: string;
  quality_score: number;
  created_at: string;
}

// P18: Community Publishing types

export type CommunityPublicationStatus = "pending_review" | "published" | "flagged" | "removed";

export interface CommunityPublication {
  id: string;
  artifact_type: "template" | "integration" | "bundle";
  artifact_id: string;
  author_id: string;
  author_name: string;
  status: CommunityPublicationStatus;
  published_at: string | null;
  title: string;
  description: string;
  tags: string[];
  category: string;
  version: string;
  install_count: number;
  flag_count: number;
  rating_avg: number;
  rating_count: number;
  bundle_id: string | null;
  source_url: string | null;
  bundle_manifest?: {
    title: string;
    description: string;
    items: Array<{
      artifact_type: string;
      artifact_id: string;
      role: "primary" | "required" | "optional";
    }>;
    sample_output?: {
      description: string;
      files: Array<{
        filename: string;
        content_type: string;
        preview: string;
        size_bytes: number;
      }>;
    };
  };
}

export interface QualityGateResult {
  gate_name: string;
  passed: boolean;
  message: string;
  severity: "error" | "warning" | "info";
}

// Timeline types

export interface TimelineEvent {
  type: string;
  category: "planning" | "execution" | "verification" | "completion";
  title: string;
  detail?: string;
  timestamp: string;
  task_id?: string;
  status?: string;
}

// DAG types

export interface DAGNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface DAGEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

// Agent spec (used in TaskDetailPanel)

export interface AgentSpec {
  id: string;
  name: string;
  [key: string]: unknown;
}

// SSE event types

export interface WorkflowSSEEvent {
  type: string;
  data: Record<string, unknown>;
  [key: string]: unknown;
}

// Personal dashboard types

export interface PersonalDashboard {
  workflows: {
    total: number;
    completed: number;
    failed: number;
    in_progress: number;
  };
  total_cost_usd: number;
  total_tokens: number;
  [key: string]: unknown;
}
