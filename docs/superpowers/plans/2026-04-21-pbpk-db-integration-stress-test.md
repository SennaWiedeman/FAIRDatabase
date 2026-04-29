# PBPK DB Integration & Stress Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Store → Pull → Run → Push DB pipeline to the PBPK model routes, then validate it with a three-layer stress test covering data integrity, correctness, and concurrent load.

**Architecture:** `runner.py` stays stateless. Two new `_fd` schema tables persist named parameter sets and simulation runs. Five new Flask endpoints in `model_routes` handle the CRUD; helpers in `helpers.py` own all DB interaction. The stress test exercises the full HTTP round-trip using Flask test clients.

**Tech Stack:** Flask, psycopg2, psycopg2.extras.RealDictCursor, json, concurrent.futures.ThreadPoolExecutor, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/pbpk_schema.sql` | Create | SQL migration — two new `_fd` tables |
| `backend/app.py` | Modify | Register `model_routes` blueprint |
| `backend/src/model/helpers.py` | Modify | Add 6 DB helper functions |
| `backend/src/model/routes.py` | Modify | Add 5 new endpoints |
| `backend/tests/model/__init__.py` | Create | Make directory a package |
| `backend/tests/model/conftest.py` | Create | Fixtures: pbpk_cleanup, pbpk_client |
| `backend/tests/model/test_pbpk_stress.py` | Create | Three-layer stress test |

---

## Task 1: DB Schema Migration

**Files:**
- Create: `backend/pbpk_schema.sql`

- [ ] **Step 1: Create the migration file**

```sql
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
```

- [ ] **Step 2: Apply migration against the running Supabase stack**

```bash
cd backend
docker compose exec db psql -U postgres -d postgres -f /dev/stdin < pbpk_schema.sql
```

Expected: `CREATE TABLE` printed twice, no errors.

- [ ] **Step 3: Verify tables exist**

```bash
docker compose exec db psql -U postgres -d postgres \
  -c "\dt _fd.*"
```

Expected: `pbpk_parameter_sets` and `pbpk_simulation_runs` appear in the list.

- [ ] **Step 4: Commit**

```bash
git add backend/pbpk_schema.sql
git commit -m "feat: add PBPK parameter sets and simulation runs tables"
```

---

## Task 2: Register model_routes Blueprint

**Files:**
- Modify: `backend/app.py`
- Create: `backend/tests/model/__init__.py`

- [ ] **Step 1: Write the failing smoke test**

Create `backend/tests/model/__init__.py` (empty):

```python
```

Create `backend/tests/model/test_blueprint_smoke.py`:

```python
import pytest


class TestModelBlueprintRegistered:
    def test_scenarios_unauthenticated_redirects(self, client):
        """Verifies model_routes blueprint is registered and auth guard works."""
        resp = client.get("/model/scenarios")
        assert resp.status_code == 302

    def test_parameter_sets_unauthenticated_redirects(self, client):
        resp = client.get("/model/parameter-sets")
        assert resp.status_code == 302

    def test_runs_unauthenticated_redirects(self, client):
        resp = client.get("/model/runs/1")
        assert resp.status_code == 302
```

- [ ] **Step 2: Run tests to verify they fail (404, not 302)**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_blueprint_smoke.py -v
```

Expected: FAIL — `AssertionError: assert 404 == 302`

- [ ] **Step 3: Register the blueprint in app.py**

Add this import after line 17 in `backend/app.py`:

```python
from src.model.routes import routes as model_routes
```

Add this registration after line 40 (after `federated_routes`):

```python
    app.register_blueprint(model_routes, url_prefix="/model")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_blueprint_smoke.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/tests/model/__init__.py backend/tests/model/test_blueprint_smoke.py
git commit -m "feat: register model_routes blueprint"
```

---

## Task 3: DB Helper Functions

**Files:**
- Modify: `backend/src/model/helpers.py`

- [ ] **Step 1: Write failing tests for helpers**

Create `backend/tests/model/test_helpers.py`:

```python
import json
import pytest
from app import get_db


class TestPBPKHelpers:
    def test_store_and_fetch_parameter_set(self, app):
        from src.model.helpers import store_parameter_set, fetch_parameter_set
        with app.app_context():
            db = get_db()
            params = {"HalfLife": 5.0, "RateInj": 0.3}
            ps_id = store_parameter_set("Test Chemical", "A test", params, "test@test.com")
            assert isinstance(ps_id, int)

            row = fetch_parameter_set(ps_id)
            assert row is not None
            assert row["name"] == "Test Chemical"
            assert row["description"] == "A test"
            assert row["params"]["HalfLife"] == 5.0
            assert row["params"]["RateInj"] == 0.3
            assert row["created_by"] == "test@test.com"
            assert row["model_id"] == "lifetime_pbpk"

            # Cleanup
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_fetch_nonexistent_parameter_set_returns_none(self, app):
        from src.model.helpers import fetch_parameter_set
        with app.app_context():
            assert fetch_parameter_set(999999999) is None

    def test_list_parameter_sets(self, app):
        from src.model.helpers import store_parameter_set, list_parameter_sets
        with app.app_context():
            db = get_db()
            id1 = store_parameter_set("Chem A", "", {"HalfLife": 1.0}, "u@test.com")
            id2 = store_parameter_set("Chem B", "", {"HalfLife": 2.0}, "u@test.com")
            rows = list_parameter_sets()
            ids = [r["id"] for r in rows]
            assert id1 in ids
            assert id2 in ids
            assert all("params" not in r for r in rows)  # list omits params blob

            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = ANY(%s)", ([id1, id2],))
            db.commit()
            cur.close()

    def test_create_and_fetch_run(self, app):
        from src.model.helpers import store_parameter_set, create_run, fetch_run
        with app.app_context():
            db = get_db()
            ps_id = store_parameter_set("Run Test", "", {}, "u@test.com")
            run_id = create_run(ps_id, "no_bf", "u@test.com")
            assert isinstance(run_id, int)

            run = fetch_run(run_id)
            assert run["param_set_id"] == ps_id
            assert run["scenario"] == "no_bf"
            assert run["status"] == "pending"
            assert run["timeseries"] is None

            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_simulation_runs WHERE id = %s", (run_id,))
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_update_run_to_done(self, app):
        from src.model.helpers import store_parameter_set, create_run, update_run, fetch_run
        with app.app_context():
            db = get_db()
            ps_id = store_parameter_set("Update Test", "", {}, "u@test.com")
            run_id = create_run(ps_id, "no_bf", "u@test.com")

            update_run(run_id, "running")
            run = fetch_run(run_id)
            assert run["status"] == "running"
            assert run["started_at"] is not None

            summary = {"peak_C_ven": 0.05, "n_rows": 500}
            timeseries = [{"time": 0.0, "C_ven": 0.0}]
            update_run(run_id, "done", summary=summary, timeseries=timeseries)
            run = fetch_run(run_id)
            assert run["status"] == "done"
            assert run["summary"]["peak_C_ven"] == pytest.approx(0.05)
            assert run["timeseries"][0]["time"] == 0.0
            assert run["finished_at"] is not None

            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_simulation_runs WHERE id = %s", (run_id,))
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_fetch_nonexistent_run_returns_none(self, app):
        from src.model.helpers import fetch_run
        with app.app_context():
            assert fetch_run(999999999) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_helpers.py -v
```

Expected: ImportError or AttributeError — the helper functions don't exist yet.

- [ ] **Step 3: Implement DB helpers in helpers.py**

Replace the full content of `backend/src/model/helpers.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_helpers.py -v
```

Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/model/helpers.py backend/tests/model/test_helpers.py
git commit -m "feat: add PBPK DB helper functions with tests"
```

---

## Task 4: Parameter Set Routes

**Files:**
- Modify: `backend/src/model/routes.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/model/test_parameter_set_routes.py`:

```python
import json
import pytest


class TestParameterSetRoutes:
    def test_create_parameter_set_returns_201(self, logged_in_user, app):
        client, user = logged_in_user
        resp = client.post(
            "/model/parameter-sets",
            json={"name": "PFOA Default", "description": "Standard PFOA", "params": {"HalfLife": 2.5}},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data
        assert data["name"] == "PFOA Default"

        # Cleanup
        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (data["id"],))
            db.commit()
            cur.close()

    def test_create_parameter_set_missing_name_returns_400(self, logged_in_user):
        client, _ = logged_in_user
        resp = client.post(
            "/model/parameter-sets",
            json={"params": {"HalfLife": 2.5}},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"]

    def test_list_parameter_sets_returns_200(self, logged_in_user, app):
        client, _ = logged_in_user
        # Create one first
        resp = client.post(
            "/model/parameter-sets",
            json={"name": "List Test", "params": {}},
            content_type="application/json",
        )
        ps_id = resp.get_json()["id"]

        resp = client.get("/model/parameter-sets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        ids = [r["id"] for r in data]
        assert ps_id in ids
        # Params blob must not be included in list
        assert all("params" not in r for r in data)

        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_get_single_parameter_set_returns_200(self, logged_in_user, app):
        client, _ = logged_in_user
        resp = client.post(
            "/model/parameter-sets",
            json={"name": "Single Get Test", "params": {"HalfLife": 7.0, "RateInj": 0.2}},
            content_type="application/json",
        )
        ps_id = resp.get_json()["id"]

        resp = client.get(f"/model/parameter-sets/{ps_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == ps_id
        assert data["params"]["HalfLife"] == pytest.approx(7.0)

        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_get_nonexistent_parameter_set_returns_404(self, logged_in_user):
        client, _ = logged_in_user
        resp = client.get("/model/parameter-sets/999999999")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_parameter_set_routes.py -v
```

Expected: FAIL — `AssertionError: assert 404 == 201` (routes don't exist yet)

- [ ] **Step 3: Add parameter set routes to routes.py**

Replace the full content of `backend/src/model/routes.py` with:

```python
"""
routes.py — Flask blueprint for the lifetime PBPK model.

Registered in app.py with url_prefix="/model".

Endpoints
---------
GET  /model/ui                        Renders the simulation UI (login required)
POST /model/run                       Runs one scenario in-memory, returns JSON
GET  /model/scenarios                 Returns available scenario list as JSON
POST /model/parameter-sets            Store a named parameter set
GET  /model/parameter-sets            List all public parameter sets
GET  /model/parameter-sets/<id>       Fetch one parameter set with full params
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, session

from src.auth.decorators import login_required
from .helpers import (
    run_scenario,
    available_scenarios,
    store_parameter_set,
    fetch_parameter_set,
    list_parameter_sets,
)

routes = Blueprint("model_routes", __name__)


# ── Existing endpoints ────────────────────────────────────────────────────────

@routes.route("/ui", methods=["GET"])
@login_required()
def model_ui():
    return render_template(
        "model/pbkfair.html",
        scenarios=available_scenarios(),
        user_email=session.get("email"),
        current_path=request.path,
    )


@routes.route("/run", methods=["POST"])
@login_required()
def run():
    payload = request.get_json(silent=True) or {}
    try:
        result = run_scenario(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": f"Simulation failed: {exc}"}), 500
    return jsonify(result), 200


@routes.route("/scenarios", methods=["GET"])
@login_required()
def scenarios():
    return jsonify(available_scenarios()), 200


# ── Parameter set endpoints ───────────────────────────────────────────────────

@routes.route("/parameter-sets", methods=["POST"])
@login_required()
def create_parameter_set():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    params = payload.get("params", {})
    if not isinstance(params, dict):
        return jsonify({"error": "params must be a JSON object"}), 400
    description = payload.get("description", "")
    created_by = session.get("email", "")
    ps_id = store_parameter_set(name, description, params, created_by)
    return jsonify({"id": ps_id, "name": name}), 201


@routes.route("/parameter-sets", methods=["GET"])
@login_required()
def get_parameter_sets():
    return jsonify(list_parameter_sets()), 200


@routes.route("/parameter-sets/<int:param_set_id>", methods=["GET"])
@login_required()
def get_parameter_set(param_set_id):
    ps = fetch_parameter_set(param_set_id)
    if ps is None:
        return jsonify({"error": "Parameter set not found"}), 404
    return jsonify(ps), 200
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_parameter_set_routes.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/src/model/routes.py backend/tests/model/test_parameter_set_routes.py
git commit -m "feat: add parameter set CRUD endpoints"
```

---

## Task 5: Simulation Run Routes

**Files:**
- Test: `backend/tests/model/test_run_routes.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/model/test_run_routes.py`:

```python
import pytest


class TestSimulationRunRoutes:
    def test_create_run_returns_200_with_results(self, logged_in_user, app):
        client, _ = logged_in_user
        # Store a minimal parameter set first
        ps_resp = client.post(
            "/model/parameter-sets",
            json={"name": "Run Route Test", "params": {"HalfLife": 2.5}},
            content_type="application/json",
        )
        ps_id = ps_resp.get_json()["id"]

        run_resp = client.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": "no_bf"},
            content_type="application/json",
        )
        assert run_resp.status_code == 200
        data = run_resp.get_json()
        assert "run_id" in data
        assert data["scenario"] == "no_bf"
        assert isinstance(data["peak_C_ven"], float)
        assert isinstance(data["timeseries"], list)
        assert len(data["timeseries"]) > 0

        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_simulation_runs WHERE id = %s", (data["run_id"],))
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_create_run_missing_param_set_id_returns_400(self, logged_in_user):
        client, _ = logged_in_user
        resp = client.post(
            "/model/runs",
            json={"scenario": "no_bf"},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "param_set_id" in resp.get_json()["error"]

    def test_create_run_nonexistent_param_set_returns_404(self, logged_in_user):
        client, _ = logged_in_user
        resp = client.post(
            "/model/runs",
            json={"param_set_id": 999999999, "scenario": "no_bf"},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_create_run_persists_status_done(self, logged_in_user, app):
        client, _ = logged_in_user
        ps_resp = client.post(
            "/model/parameter-sets",
            json={"name": "Persist Test", "params": {}},
            content_type="application/json",
        )
        ps_id = ps_resp.get_json()["id"]

        run_resp = client.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": "no_bf"},
            content_type="application/json",
        )
        run_id = run_resp.get_json()["run_id"]

        fetch_resp = client.get(f"/model/runs/{run_id}")
        assert fetch_resp.status_code == 200
        run = fetch_resp.get_json()
        assert run["status"] == "done"
        assert run["summary"] is not None
        assert run["timeseries"] is not None
        assert run["finished_at"] is not None

        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_simulation_runs WHERE id = %s", (run_id,))
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()

    def test_get_nonexistent_run_returns_404(self, logged_in_user):
        client, _ = logged_in_user
        resp = client.get("/model/runs/999999999")
        assert resp.status_code == 404

    def test_invalid_scenario_sets_run_status_error(self, logged_in_user, app):
        client, _ = logged_in_user
        ps_resp = client.post(
            "/model/parameter-sets",
            json={"name": "Error Test", "params": {}},
            content_type="application/json",
        )
        ps_id = ps_resp.get_json()["id"]

        run_resp = client.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": "invalid_scenario"},
            content_type="application/json",
        )
        assert run_resp.status_code == 400
        data = run_resp.get_json()
        assert "run_id" in data

        fetch_resp = client.get(f"/model/runs/{data['run_id']}")
        assert fetch_resp.get_json()["status"] == "error"
        assert fetch_resp.get_json()["error_message"] is not None

        with app.app_context():
            from app import get_db
            db = get_db()
            cur = db.cursor()
            cur.execute("DELETE FROM _fd.pbpk_simulation_runs WHERE id = %s", (data["run_id"],))
            cur.execute("DELETE FROM _fd.pbpk_parameter_sets WHERE id = %s", (ps_id,))
            db.commit()
            cur.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_run_routes.py -v
```

Expected: FAIL — `AssertionError: assert 404 == 200` (run endpoints not yet added to routes.py)

- [ ] **Step 3: Add simulation run endpoints to routes.py**

Append the following to the end of `backend/src/model/routes.py` (add the two new imports to the existing import block first, then append the two route functions):

Add `create_run`, `update_run`, `fetch_run`, `DEFAULT_PARAMS` to the `from .helpers import (...)` block so it reads:

```python
from .helpers import (
    run_scenario,
    available_scenarios,
    store_parameter_set,
    fetch_parameter_set,
    list_parameter_sets,
    create_run,
    update_run,
    fetch_run,
    DEFAULT_PARAMS,
)
```

Then append to the bottom of `routes.py`:

```python
# ── Simulation run endpoints ──────────────────────────────────────────────────

@routes.route("/runs", methods=["POST"])
@login_required()
def create_simulation_run():
    payload = request.get_json(silent=True) or {}
    param_set_id = payload.get("param_set_id")
    if param_set_id is None:
        return jsonify({"error": "param_set_id is required"}), 400

    ps = fetch_parameter_set(int(param_set_id))
    if ps is None:
        return jsonify({"error": "Parameter set not found"}), 404

    scenario = payload.get("scenario", "no_bf")
    created_by = session.get("email", "")

    run_id = create_run(int(param_set_id), scenario, created_by)
    update_run(run_id, "running")

    merged_params = {**DEFAULT_PARAMS, **ps["params"], "scenario": scenario}

    try:
        result = run_scenario(merged_params)
    except ValueError as exc:
        update_run(run_id, "error", error_message=str(exc))
        return jsonify({"error": str(exc), "run_id": run_id}), 400
    except RuntimeError as exc:
        update_run(run_id, "error", error_message=str(exc))
        return jsonify({"error": f"Simulation failed: {exc}", "run_id": run_id}), 500

    summary = {
        "peak_C_ven": result.get("peak_C_ven"),
        "peak_Age_yr": result.get("peak_Age_yr"),
        "final_C_ven": result.get("final_C_ven"),
        "final_Age_yr": result.get("final_Age_yr"),
        "n_rows": result.get("n_rows"),
    }
    update_run(run_id, "done", summary=summary, timeseries=result.get("timeseries"))

    return jsonify({"run_id": run_id, **result}), 200


@routes.route("/runs/<int:run_id>", methods=["GET"])
@login_required()
def get_simulation_run(run_id):
    run = fetch_run(run_id)
    if run is None:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run), 200
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_run_routes.py -v
```

Expected: 6 PASSED (each test involving a simulation will take ~1–2 s)

- [ ] **Step 5: Commit**

```bash
git add backend/src/model/helpers.py backend/tests/model/test_run_routes.py
git commit -m "feat: add simulation run endpoints with DB persistence"
```

---

## Task 6: Layer 1 — Data Integrity Stress Test

**Files:**
- Create: `backend/tests/model/conftest.py`
- Modify: `backend/tests/model/test_pbpk_stress.py` (create)

- [ ] **Step 1: Create shared conftest for stress test fixtures**

Create `backend/tests/model/conftest.py`:

```python
import pytest
from app import get_db


@pytest.fixture(scope="module")
def pbpk_client(app):
    """A test client with session pre-seeded as logged-in user for stress tests."""
    from config import supabase_extension

    TEST_EMAIL = "pbpk_stress@test.com"
    TEST_PASSWORD = "aBJ3%!fj0_f42h2pvw3"

    client = app.test_client()
    client.post(
        "/auth/register",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        follow_redirects=True,
    )
    client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        follow_redirects=True,
    )

    with app.app_context():
        users = supabase_extension.client.auth.admin.list_users()
        user = next((u for u in users if u.email == TEST_EMAIL), None)

    yield client, TEST_EMAIL

    with app.app_context():
        if user:
            supabase_extension.client.auth.admin.delete_user(user.id)


@pytest.fixture(scope="module")
def pbpk_cleanup(app):
    """Collects IDs created during stress tests and deletes them on teardown."""
    ps_ids: list[int] = []
    run_ids: list[int] = []

    yield ps_ids, run_ids

    with app.app_context():
        db = get_db()
        cur = db.cursor()
        if run_ids:
            cur.execute(
                "DELETE FROM _fd.pbpk_simulation_runs WHERE id = ANY(%s)", (run_ids,)
            )
        if ps_ids:
            cur.execute(
                "DELETE FROM _fd.pbpk_parameter_sets WHERE id = ANY(%s)", (ps_ids,)
            )
        db.commit()
        cur.close()
```

- [ ] **Step 2: Write the data integrity test**

Create `backend/tests/model/test_pbpk_stress.py` with Layer 1:

```python
"""
Three-layer PBPK stress test.

Layer 1 — Data integrity: params survive the JSONB round-trip exactly.
Layer 2 — Correctness: DB-routed simulation matches direct execute() output.
Layer 3 — Load: 50 concurrent runs complete without error under p95 < 10 s.
"""
import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from PBKFAIRModel import execute, DEFAULT_PARAMS


# ── Layer 1: Data Integrity ────────────────────────────────────────────────────

class TestLayer1DataIntegrity:
    """Parameters written to DB must be fetched back bit-for-bit identical."""

    def _store_and_fetch(self, client, params, name="integrity-test"):
        resp = client.post(
            "/model/parameter-sets",
            json={"name": name, "params": params, "description": "stress test"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        ps_id = resp.get_json()["id"]

        resp = client.get(f"/model/parameter-sets/{ps_id}")
        assert resp.status_code == 200
        return ps_id, resp.get_json()["params"]

    def test_full_default_params_round_trip(self, pbpk_client, pbpk_cleanup):
        client, _ = pbpk_client
        ps_ids, _ = pbpk_cleanup
        ps_id, fetched = self._store_and_fetch(client, DEFAULT_PARAMS, "full-defaults")
        ps_ids.append(ps_id)

        for key, expected in DEFAULT_PARAMS.items():
            assert key in fetched, f"Missing key: {key}"
            assert fetched[key] == pytest.approx(expected, rel=1e-9), (
                f"Value mismatch for {key}: stored {expected}, fetched {fetched[key]}"
            )

    def test_partial_params_round_trip(self, pbpk_client, pbpk_cleanup):
        client, _ = pbpk_client
        ps_ids, _ = pbpk_cleanup
        params = {"HalfLife": 7.123456789, "RateInj": 0.000123456}
        ps_id, fetched = self._store_and_fetch(client, params, "partial-params")
        ps_ids.append(ps_id)

        assert fetched["HalfLife"] == pytest.approx(7.123456789, rel=1e-9)
        assert fetched["RateInj"] == pytest.approx(0.000123456, rel=1e-9)
        assert len(fetched) == 2

    def test_unicode_name_and_description(self, pbpk_client, pbpk_cleanup):
        client, _ = pbpk_client
        ps_ids, _ = pbpk_cleanup
        resp = client.post(
            "/model/parameter-sets",
            json={
                "name": "PFAS — éléments chimiques",
                "description": "Modèle générique ≥ 1 composé",
                "params": {"HalfLife": 2.5},
            },
            content_type="application/json",
        )
        assert resp.status_code == 201
        ps_id = resp.get_json()["id"]
        ps_ids.append(ps_id)

        resp = client.get(f"/model/parameter-sets/{ps_id}")
        data = resp.get_json()
        assert data["name"] == "PFAS — éléments chimiques"
        assert data["description"] == "Modèle générique ≥ 1 composé"

    def test_empty_params_round_trip(self, pbpk_client, pbpk_cleanup):
        client, _ = pbpk_client
        ps_ids, _ = pbpk_cleanup
        ps_id, fetched = self._store_and_fetch(client, {}, "empty-params")
        ps_ids.append(ps_id)
        assert fetched == {}

    def test_extreme_float_values(self, pbpk_client, pbpk_cleanup):
        client, _ = pbpk_client
        ps_ids, _ = pbpk_cleanup
        params = {
            "HalfLife": 1e-10,
            "RateInj": 1e10,
            "PC_0": 0.0,
        }
        ps_id, fetched = self._store_and_fetch(client, params, "extreme-floats")
        ps_ids.append(ps_id)
        assert fetched["HalfLife"] == pytest.approx(1e-10, rel=1e-9)
        assert fetched["RateInj"] == pytest.approx(1e10, rel=1e-9)
        assert fetched["PC_0"] == 0.0
```

- [ ] **Step 3: Run Layer 1 tests**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_pbpk_stress.py::TestLayer1DataIntegrity -v
```

Expected: 5 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/tests/model/conftest.py backend/tests/model/test_pbpk_stress.py
git commit -m "test(stress): layer 1 data integrity tests"
```

---

## Task 7: Layer 2 — Correctness Stress Test

**Files:**
- Modify: `backend/tests/model/test_pbpk_stress.py`

- [ ] **Step 1: Append Layer 2 to test_pbpk_stress.py**

Add the following class after `TestLayer1DataIntegrity`:

```python
# ── Layer 2: Correctness ──────────────────────────────────────────────────────

class TestLayer2Correctness:
    """
    For each scenario × parameter combination: direct execute() must match
    the DB-routed POST /model/runs result to within floating-point tolerance.
    """

    PARAM_COMBOS = [
        ("pfoa_default",   {}),
        ("high_halflife",  {"HalfLife": 10.0}),
        ("low_halflife",   {"HalfLife": 0.1}),
        ("zero_intake",    {"RateInj": 0.0}),
        ("early_birth",    {"BirthYear": 1990.0}),
    ]
    SCENARIOS = ["no_bf", "bf_6mo", "bf_1yr", "bf_3yr"]

    def _run_via_db(self, client, ps_id, scenario):
        resp = client.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": scenario},
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.get_json()
        return resp.get_json()

    @pytest.mark.parametrize("label,extra_params", PARAM_COMBOS)
    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_db_route_matches_direct_execute(
        self, scenario, label, extra_params, pbpk_client, pbpk_cleanup
    ):
        client, _ = pbpk_client
        ps_ids, run_ids = pbpk_cleanup

        merged = {**DEFAULT_PARAMS, **extra_params}
        direct = execute({**merged, "scenario": scenario})

        resp = client.post(
            "/model/parameter-sets",
            json={"name": f"correctness-{label}", "params": extra_params},
            content_type="application/json",
        )
        assert resp.status_code == 201
        ps_id = resp.get_json()["id"]
        ps_ids.append(ps_id)

        db_result = self._run_via_db(client, ps_id, scenario)
        run_ids.append(db_result["run_id"])

        tol = 1e-6
        for field in ("peak_C_ven", "peak_Age_yr", "final_C_ven", "final_Age_yr"):
            direct_val = direct.get(field)
            db_val = db_result.get(field)
            if direct_val is None:
                assert db_val is None, f"{field}: expected None, got {db_val}"
            else:
                assert db_val == pytest.approx(direct_val, rel=tol), (
                    f"scenario={scenario} label={label} field={field}: "
                    f"direct={direct_val}, db={db_val}"
                )

        assert db_result["n_rows"] == direct["n_rows"]
```

- [ ] **Step 2: Run Layer 2 tests**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_pbpk_stress.py::TestLayer2Correctness -v
```

Expected: 20 PASSED (4 scenarios × 5 param combos). Each test runs one simulation (~1–2 s), total ~30–60 s.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/model/test_pbpk_stress.py
git commit -m "test(stress): layer 2 correctness tests — 20 scenario/param combinations"
```

---

## Task 8: Layer 3 — Load Stress Test

**Files:**
- Modify: `backend/tests/model/test_pbpk_stress.py`

- [ ] **Step 1: Append Layer 3 to test_pbpk_stress.py**

Add the following class after `TestLayer2Correctness`:

```python
# ── Layer 3: Load ─────────────────────────────────────────────────────────────

class TestLayer3Load:
    """
    50 concurrent simulations via ThreadPoolExecutor (10 workers).
    Assertions: all runs complete as 'done', p95 latency < PBPK_STRESS_LATENCY_P95 (default 10 s).
    """

    N_RUNS = 50
    N_WORKERS = 10
    SCENARIOS = ["no_bf", "bf_6mo", "bf_1yr", "bf_3yr"]

    def _make_client_with_session(self, app, email):
        """Create a fresh test client manually seeded with a session."""
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user"] = email
            sess["email"] = email
        return client

    def _fire_one_run(self, app, email, ps_id, scenario):
        client = self._make_client_with_session(app, email)
        t0 = time.monotonic()
        resp = client.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": scenario},
            content_type="application/json",
        )
        elapsed = time.monotonic() - t0
        return resp.status_code, resp.get_json(), elapsed

    @pytest.mark.slow
    def test_50_concurrent_runs(self, app, pbpk_client, pbpk_cleanup):
        import os
        client, email = pbpk_client
        ps_ids, run_ids = pbpk_cleanup
        p95_threshold = float(os.environ.get("PBPK_STRESS_LATENCY_P95", "10"))

        # Create one shared parameter set (public — all clients can use it)
        resp = client.post(
            "/model/parameter-sets",
            json={"name": "load-test-params", "params": {"HalfLife": 2.5}},
            content_type="application/json",
        )
        assert resp.status_code == 201
        ps_id = resp.get_json()["id"]
        ps_ids.append(ps_id)

        # Pre-warm the SBML singleton to avoid race on first initialization
        warmup = self._make_client_with_session(app, email)
        warmup.post(
            "/model/runs",
            json={"param_set_id": ps_id, "scenario": "no_bf"},
            content_type="application/json",
        )

        rng = random.Random(42)
        jobs = [
            (app, email, ps_id, rng.choice(self.SCENARIOS))
            for _ in range(self.N_RUNS)
        ]

        latencies = []
        statuses = []
        results = []

        with ThreadPoolExecutor(max_workers=self.N_WORKERS) as pool:
            futures = [pool.submit(self._fire_one_run, *job) for job in jobs]
            for fut in as_completed(futures):
                status_code, data, elapsed = fut.result()
                statuses.append(status_code)
                latencies.append(elapsed)
                results.append(data)

        # All must succeed
        failed = [r for s, r in zip(statuses, results) if s != 200]
        assert not failed, f"{len(failed)} runs failed: {failed[:3]}"

        # All runs must be persisted as 'done'
        for data in results:
            run_ids.append(data["run_id"])

        for data in results:
            assert data.get("timeseries") is not None, (
                f"run_id={data.get('run_id')} has null timeseries"
            )
            assert data.get("error_message") is None, (
                f"run_id={data.get('run_id')} has error: {data.get('error_message')}"
            )

        # p95 latency check
        latencies.sort()
        p95_idx = int(math.ceil(0.95 * len(latencies))) - 1
        p95 = latencies[p95_idx]
        assert p95 < p95_threshold, (
            f"p95 latency {p95:.2f}s exceeds threshold {p95_threshold}s"
        )
```

- [ ] **Step 2: Run Layer 3 load test**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_pbpk_stress.py::TestLayer3Load -v -m slow
```

Expected: 1 PASSED. The test runs 50+1 simulations concurrently (~60–120 s total). If p95 > 10 s, raise `PBPK_STRESS_LATENCY_P95` or reduce `N_RUNS`.

- [ ] **Step 3: Run the full stress suite**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest tests/model/test_pbpk_stress.py -v -m "slow or not slow"
```

Expected: 26 PASSED (5 + 20 + 1)

- [ ] **Step 4: Run the full test suite to check for regressions**

```bash
cd backend
export PYTHONPATH=$(pwd):$(pwd)/..
pytest -m "not slow" -v
```

Expected: All existing tests plus new unit/route tests PASSED. No regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/model/test_pbpk_stress.py
git commit -m "test(stress): layer 3 load test — 50 concurrent PBPK runs"
```
