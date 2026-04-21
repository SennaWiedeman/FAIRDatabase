"""
helpers.py — thin bridge between the Flask routes and PBKFAIRModel,
plus DB helpers for persisting parameter sets and simulation runs.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import psycopg2.extras
from flask import g

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PBKFAIRModel import execute, SCENARIOS, DEFAULT_PARAMS  # noqa: E402


# ── Simulation helpers ────────────────────────────────────────────────────────

def run_scenario(user_params: dict) -> dict:
    """Validate basic inputs and delegate to runner.execute()."""
    valid_labels = {s["label"] for s in SCENARIOS}
    label = user_params.get("scenario", "no_bf")
    if label not in valid_labels:
        raise ValueError(
            f"Unknown scenario '{label}'. Valid options: {sorted(valid_labels)}"
        )
    half_life = user_params.get("HalfLife")
    if half_life is not None and float(half_life) <= 0:
        raise ValueError("HalfLife must be positive.")
    return execute(user_params)


def available_scenarios() -> list[dict]:
    """Return scenario metadata for the UI dropdown."""
    return [{"label": s["label"], "description": s["description"]} for s in SCENARIOS]


# ── DB helpers ────────────────────────────────────────────────────────────────

def store_parameter_set(name: str, description: str, params: dict, created_by: str) -> int:
    """Insert a named parameter set and return its id."""
    cur = g.db.cursor()
    cur.execute(
        """
        INSERT INTO _fd.pbpk_parameter_sets (name, description, params, created_by)
        VALUES (%s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (name, description, json.dumps(params), created_by),
    )
    row = cur.fetchone()
    g.db.commit()
    cur.close()
    return row[0]


def fetch_parameter_set(param_set_id: int) -> dict | None:
    """Fetch one parameter set by id, including full params JSONB."""
    cur = g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, name, description, model_id, params, created_by, created_at
        FROM _fd.pbpk_parameter_sets
        WHERE id = %s
        """,
        (param_set_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    result = dict(row)
    if isinstance(result["params"], str):
        result["params"] = json.loads(result["params"])
    result["created_at"] = result["created_at"].isoformat()
    return result


def list_parameter_sets() -> list[dict]:
    """Return all parameter sets (id, name, description, model_id, created_by, created_at)."""
    cur = g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, name, description, model_id, created_by, created_at
        FROM _fd.pbpk_parameter_sets
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    result = []
    for row in rows:
        r = dict(row)
        r["created_at"] = r["created_at"].isoformat()
        result.append(r)
    return result


def create_run(param_set_id: int, scenario: str, created_by: str) -> int:
    """Insert a new simulation run with status='pending' and return its id."""
    cur = g.db.cursor()
    cur.execute(
        """
        INSERT INTO _fd.pbpk_simulation_runs (param_set_id, scenario, status, created_by)
        VALUES (%s, %s, 'pending', %s)
        RETURNING id
        """,
        (param_set_id, scenario, created_by),
    )
    row = cur.fetchone()
    g.db.commit()
    cur.close()
    return row[0]


def update_run(
    run_id: int,
    status: str,
    summary: dict | None = None,
    timeseries: list | None = None,
    error_message: str | None = None,
) -> None:
    """Update run status, timestamps, and optionally results or error."""
    now = datetime.now(timezone.utc)
    parts = ["status = %s"]
    values: list = [status]

    if status == "running":
        parts.append("started_at = %s")
        values.append(now)
    if status in ("done", "error"):
        parts.append("finished_at = %s")
        values.append(now)
    if summary is not None:
        parts.append("summary = %s::jsonb")
        values.append(json.dumps(summary))
    if timeseries is not None:
        parts.append("timeseries = %s::jsonb")
        values.append(json.dumps(timeseries))
    if error_message is not None:
        parts.append("error_message = %s")
        values.append(error_message)

    values.append(run_id)
    cur = g.db.cursor()
    cur.execute(
        f"UPDATE _fd.pbpk_simulation_runs SET {', '.join(parts)} WHERE id = %s",
        values,
    )
    g.db.commit()
    cur.close()


def fetch_run(run_id: int) -> dict | None:
    """Fetch one simulation run by id."""
    cur = g.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, param_set_id, scenario, status, started_at, finished_at,
               error_message, summary, timeseries, created_by, created_at
        FROM _fd.pbpk_simulation_runs
        WHERE id = %s
        """,
        (run_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    result = dict(row)
    for field in ("summary", "timeseries"):
        if isinstance(result.get(field), str):
            result[field] = json.loads(result[field])
    for field in ("started_at", "finished_at", "created_at"):
        if result.get(field) is not None:
            result[field] = result[field].isoformat()
    return result
