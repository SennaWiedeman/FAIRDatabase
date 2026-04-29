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
    create_run,
    update_run,
    fetch_run,
    DEFAULT_PARAMS,
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
