-- backend/pbpk_schema.sql
-- Run after migrate_schema.sql to add PBPK persistence tables.

CREATE TABLE IF NOT EXISTS _fd.pbpk_parameter_sets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    model_id    TEXT NOT NULL DEFAULT 'lifetime_pbpk',
    params      JSONB NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS _fd.pbpk_simulation_runs (
    id              SERIAL PRIMARY KEY,
    param_set_id    INT REFERENCES _fd.pbpk_parameter_sets(id),
    scenario        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    error_message   TEXT,
    summary         JSONB,
    timeseries      JSONB,
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
