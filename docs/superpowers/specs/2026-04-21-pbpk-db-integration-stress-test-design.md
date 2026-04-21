# PBPK DB Integration & Stress Test Design

**Date:** 2026-04-21
**Branch:** pbkfair-model

## Context

The PBKFAIRModel pipeline is currently stateless: parameters arrive via HTTP request, `execute()` runs in memory, results are returned as JSON, and nothing is persisted. The `model_routes` blueprint is not yet registered in `app.py`. There are no DB tables for PBPK data and zero tests for the PBPK stack.

The goal is to add a generalized Store → Pull → Run → Push pipeline that persists named parameter sets and simulation results to the DB, then validate it with a three-layer stress test. The longer-term aim is a FAIR framework that supports any PBPK parameter set (not just PFOA), with SBML model upload as a future phase.

## Decisions

- **Approach:** Thin DB layer in Flask routes — `runner.py` stays stateless and DB-free (preserves FAIR reusability). All DB interaction lives in Flask routes.
- **Generalization scope:** Parameter sets now (any subset of the ~70 model parameters stored as JSONB), SBML model upload in a future phase.
- **Visibility:** All parameter sets are public by default (FAIR principle).

## DB Schema

New migration file: `backend/pbpk_schema.sql` (applied alongside `migrate_schema.sql`).

```sql
-- Named public parameter sets (one row per chemical profile)
CREATE TABLE IF NOT EXISTS _fd.pbpk_parameter_sets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    model_id    TEXT NOT NULL DEFAULT 'lifetime_pbpk',  -- future: uploaded SBML identifier
    params      JSONB NOT NULL,   -- any subset of DEFAULT_PARAMS key/value pairs
    created_by  TEXT NOT NULL,    -- user email
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- One row per simulation run
CREATE TABLE IF NOT EXISTS _fd.pbpk_simulation_runs (
    id              SERIAL PRIMARY KEY,
    param_set_id    INT REFERENCES _fd.pbpk_parameter_sets(id),
    scenario        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | error
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    error_message   TEXT,
    summary         JSONB,   -- peak_C_ven, peak_Age_yr, final_C_ven, final_Age_yr, n_rows
    timeseries      JSONB,   -- downsampled 500-row array from execute()
    created_by      TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Key design choices:**
- `params` is JSONB so any subset of the ~70 model parameters can be stored without schema changes. A partial set (e.g. just `HalfLife` and `RateInj`) is valid — missing keys fall back to `DEFAULT_PARAMS`.
- `model_id` is a forward-compatibility column: currently always `'lifetime_pbpk'`; future rows will reference an uploaded SBML file.
- `summary` and `timeseries` are split so callers can fetch just the summary without pulling the full time series.

## Flask Routes

The `model_routes` blueprint is registered in `app.py` (currently missing). Five new endpoints:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/model/parameter-sets` | `@login_required` | **Store** — saves named parameter set, returns `{id, name}` |
| `GET` | `/model/parameter-sets` | `@login_required` | List all public parameter sets |
| `GET` | `/model/parameter-sets/<id>` | `@login_required` | Fetch one parameter set with full params |
| `POST` | `/model/runs` | `@login_required` | **Pull → Run → Push** — run simulation from a stored parameter set |
| `GET` | `/model/runs/<id>` | `@login_required` | Fetch a completed run |

### POST /model/runs — merge strategy

```
final_params = DEFAULT_PARAMS | db_params | {"scenario": scenario}
```

DB values override model defaults; the caller can override scenario at run time. This means storing only the parameters that differ from PFOA defaults is sufficient for a new chemical profile.

### Error handling

- Unknown `param_set_id` → 404
- Invalid `scenario` → 400
- ODE solver failure → run row updated to `status='error'`, `error_message` set → 500 response with `run_id` so the failed run is traceable

## Stress Test Design

**File:** `backend/tests/model/test_pbpk_stress.py`

A pytest fixture creates isolated parameter sets and runs for the test session and deletes them on teardown.

### Layer 1 — Data Integrity (~5 cases)

Store a parameter set with known values → pull back via `GET /model/parameter-sets/<id>` → assert every key matches exactly. Covers:
- Float precision (JSONB serialization)
- Full `DEFAULT_PARAMS` round-trip (all ~70 keys)
- Partial parameter set (2–3 keys only)
- Unicode in name/description fields

### Layer 2 — Correctness (~20 cases)

For each of the 4 scenarios × 5 parameter combinations:
1. Run `execute()` directly (in-process, no DB)
2. Store the same params, run via `POST /model/runs`
3. Assert all summary fields match to `1e-6` tolerance

Parameter combinations: PFOA defaults, HalfLife=10.0, HalfLife=0.1, RateInj=0.0, BirthYear=1990.

This proves the Store → Pull → merge pipeline does not corrupt numerical values.

### Layer 3 — Load (50 concurrent runs)

`concurrent.futures.ThreadPoolExecutor(max_workers=10)` fires 50 `POST /model/runs` requests simultaneously (5 batches of 10), each using a randomly sampled parameter set drawn from a fixed seed (`random.seed(42)`).

Assertions:
- All 50 runs reach `status = 'done'`
- No `timeseries` is null
- No `error_message` is set
- p95 wall-clock latency < 10 s (configurable via `PBPK_STRESS_LATENCY_P95` env var)
- SBML singleton survives concurrent access (no exceptions from `runner.py`)

## Files Changed

| File | Change |
|---|---|
| `backend/pbpk_schema.sql` | New — DB migration for two PBPK tables |
| `backend/app.py` | Register `model_routes` blueprint |
| `backend/src/model/routes.py` | Add 5 new endpoints |
| `backend/src/model/helpers.py` | Add `store_parameter_set`, `fetch_parameter_set`, `create_run`, `update_run` DB helpers |
| `backend/tests/model/__init__.py` | New — make directory a package |
| `backend/tests/model/test_pbpk_stress.py` | New — three-layer stress test |

## Out of Scope (This Phase)

- SBML model upload (`model_id` column is reserved but not activated)
- Async job queue (simulations are synchronous; ~1–2 s per run is acceptable)
- Per-user private parameter sets (all sets are public by default)
- UI changes to `pbkfair.html`
