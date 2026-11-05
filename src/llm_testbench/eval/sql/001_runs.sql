-- Run history of the evaluation harness (phase 2.7). Idempotent: replayed at every run.
--
-- eval_runs holds one row per run, with the columns one filters on and the whole record
-- as JSON; eval_query_results holds the per-query scores, so that two runs can be joined
-- query by query in plain SQL:
--
--   SELECT a.query_id, (a.metrics->>'ndcg_at_10')::float - (b.metrics->>'ndcg_at_10')::float AS gain
--   FROM eval_query_results a JOIN eval_query_results b USING (query_id)
--   WHERE a.run_id = '<candidate>' AND b.run_id = '<baseline>' ORDER BY gain;
--
-- The database is the queryable history; the versioned archive (data/results/runs/) is the
-- durable one. A local cluster is recreated without a second thought, a git history is not.

CREATE TABLE IF NOT EXISTS eval_runs (
    run_id      text        PRIMARY KEY,
    created_at  timestamptz NOT NULL,
    suite       text        NOT NULL,
    arm         text        NOT NULL,
    dataset     text        NOT NULL,
    publishable boolean     NOT NULL,
    git_sha     text,
    git_dirty   boolean,
    metrics     jsonb       NOT NULL,
    run         jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS eval_runs_by_arm ON eval_runs (suite, arm, created_at DESC);

CREATE TABLE IF NOT EXISTS eval_query_results (
    run_id     text             NOT NULL REFERENCES eval_runs (run_id) ON DELETE CASCADE,
    query_id   text             NOT NULL,
    metrics    jsonb            NOT NULL,
    ranking    jsonb            NOT NULL,
    latency_ms double precision NOT NULL,
    PRIMARY KEY (run_id, query_id)
);
