CREATE TABLE IF NOT EXISTS dz_native_workflows (
 goal_id uuid PRIMARY KEY,owner_id text NOT NULL,session_hash text NOT NULL,
 request_id uuid NOT NULL,conversation_id uuid NOT NULL,plan jsonb NOT NULL,
 plan_sha256 char(64) NOT NULL,ceiling_usd numeric(20,10) NOT NULL CHECK(ceiling_usd>0),
 state text NOT NULL CHECK(state IN ('preparing','active','inflight','completed','blocked','cancelled','uncertain')),
 next_sequence integer NOT NULL DEFAULT 0 CHECK(next_sequence>=0),
 cancel_requested boolean NOT NULL DEFAULT false,blocked_reason text,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,request_id)
);
CREATE TABLE IF NOT EXISTS dz_native_workflow_phases (
 goal_id uuid NOT NULL REFERENCES dz_native_workflows(goal_id),sequence integer NOT NULL,
 phase_id text NOT NULL,report jsonb NOT NULL,report_sha256 char(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(goal_id,sequence),UNIQUE(goal_id,phase_id)
);
CREATE INDEX IF NOT EXISTS dz_native_workflows_owner ON dz_native_workflows(owner_id,updated_at DESC);
