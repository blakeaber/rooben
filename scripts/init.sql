-- Rooben dashboard schema
-- Source of truth for fresh installs. Matches the production schema.

CREATE TABLE IF NOT EXISTS workflows (
    id              TEXT PRIMARY KEY,
    spec_id         TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    total_tasks     INTEGER NOT NULL DEFAULT 0,
    completed_tasks INTEGER NOT NULL DEFAULT 0,
    failed_tasks    INTEGER NOT NULL DEFAULT 0,
    replan_count    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS workstreams (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    task_ids        JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workstreams_workflow ON workstreams(workflow_id);

CREATE TABLE IF NOT EXISTS tasks (
    id                  TEXT PRIMARY KEY,
    workstream_id       TEXT NOT NULL REFERENCES workstreams(id),
    workflow_id         TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    structured_prompt   JSONB,
    status              TEXT NOT NULL DEFAULT 'pending',
    assigned_agent_id   TEXT,
    acceptance_criteria_ids JSONB NOT NULL DEFAULT '[]',
    verification_strategy TEXT NOT NULL DEFAULT 'llm_judge',
    skeleton_tests      JSONB NOT NULL DEFAULT '[]',
    result              JSONB,
    attempt             INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 3,
    priority            INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    attempt_feedback    JSONB NOT NULL DEFAULT '[]',
    linear_issue_id     TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    output              TEXT,
    error               TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_workflow ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on  TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on)
);

CREATE TABLE IF NOT EXISTS workflow_usage (
    id              SERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    task_id         TEXT REFERENCES tasks(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(12, 8) NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'agent',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_workflow ON workflow_usage(workflow_id);
CREATE INDEX IF NOT EXISTS idx_usage_task ON workflow_usage(task_id);

-- P6.5: Spec persistence columns
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS spec_yaml TEXT;
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS spec_metadata JSONB;

-- P16.5: Template provenance
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS template_name TEXT;

-- P6.5: Agent introspection tables
CREATE TABLE IF NOT EXISTS agents (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    transport          TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    endpoint           TEXT NOT NULL DEFAULT '',
    capabilities       JSONB NOT NULL DEFAULT '[]',
    max_concurrency    INTEGER NOT NULL DEFAULT 1,
    max_context_tokens INTEGER NOT NULL DEFAULT 200000,
    budget             JSONB,
    mcp_servers        JSONB NOT NULL DEFAULT '[]',
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_agents (
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    agent_id    TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    PRIMARY KEY (workflow_id, agent_id)
);

CREATE TABLE IF NOT EXISTS shared_links (
    token           TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_shared_links_workflow ON shared_links(workflow_id);

-- P9: Schedules
CREATE TABLE IF NOT EXISTS schedules (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    cron_expression       TEXT NOT NULL,
    workflow_description  TEXT NOT NULL,
    provider              TEXT DEFAULT 'anthropic',
    model                 TEXT DEFAULT 'claude-sonnet-4-20250514',
    active                BOOLEAN DEFAULT true,
    last_run_at           TIMESTAMPTZ,
    next_run_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schedule_executions (
    id              SERIAL PRIMARY KEY,
    schedule_id     TEXT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    workflow_id     TEXT REFERENCES workflows(id),
    status          TEXT DEFAULT 'pending',
    started_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_schedule_executions_schedule ON schedule_executions(schedule_id);

-- P10: Workspace & input context
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS workspace_dir TEXT;
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS input_context JSONB DEFAULT '[]';

-- P11: Integration credentials
CREATE TABLE IF NOT EXISTS credentials (
    id              TEXT PRIMARY KEY,
    integration_name TEXT NOT NULL,
    env_var_name    TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,
    credential_type TEXT NOT NULL DEFAULT 'integration',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (integration_name, env_var_name)
);
CREATE INDEX IF NOT EXISTS idx_credentials_integration ON credentials(integration_name);
CREATE INDEX IF NOT EXISTS idx_credentials_type ON credentials(credential_type);

-- P11: Agent behavior customization
ALTER TABLE agents ADD COLUMN IF NOT EXISTS integration TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS prompt_template TEXT DEFAULT '';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS model_override TEXT DEFAULT '';

-- P11: Agent configuration presets
CREATE TABLE IF NOT EXISTS agent_presets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL DEFAULT '',
    integration     TEXT,
    prompt_template TEXT DEFAULT '',
    model_override  TEXT DEFAULT '',
    capabilities    JSONB NOT NULL DEFAULT '[]',
    max_context_tokens INTEGER NOT NULL DEFAULT 200000,
    budget          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- P12: Marketplace ecosystem
CREATE TABLE IF NOT EXISTS marketplace_templates (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT 'user',
    author          TEXT NOT NULL DEFAULT '',
    version         TEXT NOT NULL DEFAULT '1.0.0',
    tags            JSONB NOT NULL DEFAULT '[]',
    spec_yaml       TEXT NOT NULL DEFAULT '',
    install_count   INTEGER NOT NULL DEFAULT 0,
    source_workflow_id TEXT,
    status          TEXT NOT NULL DEFAULT 'published',
    owner_id        TEXT,
    forked_from     TEXT,
    installed_from  TEXT,
    pricing_tier    TEXT NOT NULL DEFAULT 'free',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_templates_status ON marketplace_templates(status);
CREATE INDEX IF NOT EXISTS idx_marketplace_templates_owner ON marketplace_templates(owner_id);

CREATE TABLE IF NOT EXISTS marketplace_agents (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT 'user',
    author          TEXT NOT NULL DEFAULT '',
    version         TEXT NOT NULL DEFAULT '1.0.0',
    tags            JSONB NOT NULL DEFAULT '[]',
    preset_data     JSONB NOT NULL DEFAULT '{}',
    install_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'published',
    owner_id        TEXT,
    forked_from     TEXT,
    installed_from  TEXT,
    pricing_tier    TEXT NOT NULL DEFAULT 'free',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_agents_status ON marketplace_agents(status);
CREATE INDEX IF NOT EXISTS idx_marketplace_agents_owner ON marketplace_agents(owner_id);

-- P13: Performance snapshots for trend data
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id              SERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    total_tasks     INTEGER NOT NULL DEFAULT 0,
    passed_tasks    INTEGER NOT NULL DEFAULT 0,
    pass_rate       NUMERIC(5, 3) NOT NULL DEFAULT 0,
    avg_cost        NUMERIC(12, 8) NOT NULL DEFAULT 0,
    total_cost      NUMERIC(12, 8) NOT NULL DEFAULT 0,
    quality_score   NUMERIC(5, 3) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perf_snapshots_workflow ON performance_snapshots(workflow_id);
CREATE INDEX IF NOT EXISTS idx_perf_snapshots_model ON performance_snapshots(provider, model);

-- P14: A2A task ID → workflow ID mapping
CREATE TABLE IF NOT EXISTS a2a_task_map (
    task_id         TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- P15b: Default preset flag
ALTER TABLE agent_presets ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT false;

-- P15b: Goals, Roles, Outcomes
CREATE TABLE IF NOT EXISTS user_goals (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'active',
    target_date DATE,
    tags        JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_goals_user ON user_goals(user_id);

CREATE TABLE IF NOT EXISTS user_roles (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    department  TEXT NOT NULL DEFAULT '',
    context     TEXT NOT NULL DEFAULT '',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);

CREATE TABLE IF NOT EXISTS user_outcomes (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    workflow_id   TEXT NOT NULL,
    goal_id       TEXT,
    outcome_type  TEXT NOT NULL DEFAULT 'workflow_completion',
    summary       TEXT NOT NULL DEFAULT '',
    quality_score NUMERIC(5, 3) NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_outcomes_user ON user_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_user_outcomes_goal ON user_outcomes(goal_id);

-- P19: Waitlist (GTM launch readiness)
CREATE TABLE IF NOT EXISTS waitlist (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL DEFAULT '',
    referral_source TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- P18: Community Publishing
CREATE TABLE IF NOT EXISTS community_publications (
    id              TEXT PRIMARY KEY,
    artifact_type   TEXT NOT NULL,
    artifact_id     TEXT NOT NULL,
    author_id       TEXT NOT NULL,
    author_name     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending_review',
    published_at    TIMESTAMPTZ,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    tags            JSONB NOT NULL DEFAULT '[]',
    category        TEXT NOT NULL DEFAULT 'general',
    version         TEXT NOT NULL DEFAULT '1.0.0',
    automated_checks_passed BOOLEAN NOT NULL DEFAULT FALSE,
    review_notes    TEXT,
    install_count   INTEGER NOT NULL DEFAULT 0,
    flag_count      INTEGER NOT NULL DEFAULT 0,
    rating_sum      REAL NOT NULL DEFAULT 0,
    rating_count    INTEGER NOT NULL DEFAULT 0,
    bundle_id       TEXT,
    source_url      TEXT,
    forked_from     TEXT,
    bundle_manifest JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_publications_browse
    ON community_publications(status, artifact_type, category);
CREATE INDEX IF NOT EXISTS idx_publications_author
    ON community_publications(author_id);

CREATE TABLE IF NOT EXISTS community_ratings (
    publication_id  TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    rating          INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (publication_id, user_id)
);

CREATE TABLE IF NOT EXISTS community_flags (
    id              TEXT PRIMARY KEY,
    publication_id  TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(publication_id, user_id)
);

-- Plan quality metadata
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS plan_checker_score NUMERIC(5, 3);
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS plan_judge_score NUMERIC(5, 3);
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS plan_quality JSONB;

-- P20: Invite codes for waitlist activation
CREATE TABLE IF NOT EXISTS invite_codes (
    code            TEXT PRIMARY KEY,
    created_by      TEXT NOT NULL DEFAULT 'system',
    max_uses        INTEGER NOT NULL DEFAULT 1,
    use_count       INTEGER NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

