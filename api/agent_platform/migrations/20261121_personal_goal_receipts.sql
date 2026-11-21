-- DragonZpyder Personal read-only wake acceptance schema.
-- Apply to the SAME PostgreSQL database configured as
-- DRAGONZPYDER_AGENT_DATABASE_URL for the API and worker.
-- Independent of LangGraph's checkpoint tables.
CREATE TABLE IF NOT EXISTS dz_personal_mcp_goals (
    goal_id text PRIMARY KEY,
    user_id text NOT NULL,
    session_id text NOT NULL,
    conversation_id text NOT NULL,
    total_wakes integer NOT NULL CHECK(total_wakes BETWEEN 2 AND 20),
    objective_hash char(64) NOT NULL,
    next_sequence integer NOT NULL DEFAULT 0,
    state text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS dz_personal_mcp_receipts (
    goal_id text NOT NULL REFERENCES dz_personal_mcp_goals(goal_id),
    sequence integer NOT NULL,
    status text NOT NULL,
    tool_names jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (goal_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_dz_personal_goals_owner
    ON dz_personal_mcp_goals(user_id, conversation_id, created_at DESC);
