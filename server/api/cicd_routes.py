"""CI/CD Pipelines and Runs API.

Pipeline endpoints:
- GET    /api/cicd/pipelines
- POST   /api/cicd/pipelines
- GET    /api/cicd/pipelines/<id>
- PUT    /api/cicd/pipelines/<id>
- DELETE /api/cicd/pipelines/<id>
- POST   /api/cicd/pipelines/<id>/trigger

Run endpoints:
- GET    /api/cicd/runs
- GET    /api/cicd/runs/<id>
- PUT    /api/cicd/runs/<id>
- DELETE /api/cicd/runs/<id>

Approval endpoints:
- POST   /api/cicd/runs/<run_id>/approve
- POST   /api/cicd/runs/<run_id>/reject

Logs:
- GET    /api/cicd/runs/<run_id>/steps/<step_index>/log
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

import storage.cicd_store as cicd_store

from services.cicd_engine import (
    approve_pipeline_run,
    get_step_log,
    reject_pipeline_run,
    trigger_pipeline_run,
)


logger = logging.getLogger(__name__)

bp = Blueprint(
    "cicd_api",
    __name__,
    url_prefix="/api/cicd",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_id() -> Optional[str]:
    """Resolve project ID from request header, body, or query string."""

    pid = request.headers.get("X-Project-Id")

    if pid:
        return pid

    body = request.get_json(silent=True) or {}

    return (
        body.get("project_id")
        or request.args.get("project_id")
    )


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------


@bp.route("/pipelines", methods=["GET"])
def list_pipelines():

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    pipelines = cicd_store.list_pipelines(pid)

    return jsonify({
        "success": True,
        "pipelines": pipelines,
    })


@bp.route("/pipelines", methods=["POST"])
def create_pipeline():

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    data = request.get_json(silent=True) or {}

    if not data.get("name"):
        return jsonify({
            "error": "name is required"
        }), 400

    pipeline_id = cicd_store.create_pipeline(
        pid,
        data,
    )

    return jsonify({
        "success": True,
        "pipeline_id": pipeline_id,
    }), 201


@bp.route(
    "/pipelines/<pipeline_id>",
    methods=["GET"],
)
def get_pipeline(pipeline_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    pipeline = cicd_store.get_pipeline(
        pid,
        pipeline_id,
    )

    if not pipeline:
        return jsonify({
            "error": "Pipeline not found"
        }), 404

    return jsonify({
        "success": True,
        "pipeline": pipeline,
    })


@bp.route(
    "/pipelines/<pipeline_id>",
    methods=["PUT"],
)
def update_pipeline(pipeline_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    data = request.get_json(silent=True) or {}

    ok = cicd_store.update_pipeline(
        pid,
        pipeline_id,
        data,
    )

    if not ok:
        return jsonify({
            "error": "Pipeline not found"
        }), 404

    return jsonify({
        "success": True
    })


@bp.route(
    "/pipelines/<pipeline_id>",
    methods=["DELETE"],
)
def delete_pipeline(pipeline_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    ok = cicd_store.delete_pipeline(
        pid,
        pipeline_id,
    )

    if not ok:
        return jsonify({
            "error": "Pipeline not found"
        }), 404

    return jsonify({
        "success": True
    })


# ---------------------------------------------------------------------------
# Trigger pipeline
# ---------------------------------------------------------------------------


@bp.route(
    "/pipelines/<pipeline_id>/trigger",
    methods=["POST"],
)
def trigger_pipeline(pipeline_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    pipeline = cicd_store.get_pipeline(
        pid,
        pipeline_id,
    )

    if not pipeline:
        return jsonify({
            "error": "Pipeline not found"
        }), 404

    data = request.get_json(silent=True) or {}

    run_id = trigger_pipeline_run(
        project_id=pid,
        pipeline_id=pipeline_id,
        trigger_type=data.get(
            "trigger_type",
            "manual",
        ),
        git_commit=data.get(
            "git_commit",
            "",
        ),
        triggered_by=data.get(
            "triggered_by",
            "",
        ),
    )

    if not run_id:
        return jsonify({
            "error": "Failed to trigger pipeline run"
        }), 500

    run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    return jsonify({
        "success": True,
        "run_id": run_id,
        "run_number": (
            run.get("run_number")
            if run
            else None
        ),
    })


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@bp.route("/runs", methods=["GET"])
def list_runs():

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    pipeline_id = request.args.get(
        "pipeline_id"
    )

    runs = cicd_store.list_pipeline_runs(
        pid,
        pipeline_id=pipeline_id or None,
    )

    return jsonify({
        "success": True,
        "runs": runs,
    })


@bp.route(
    "/runs/<run_id>",
    methods=["GET"],
)
def get_run(run_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    if not run:
        return jsonify({
            "error": "Run not found"
        }), 404

    return jsonify({
        "success": True,
        "run": run,
    })


@bp.route(
    "/runs/<run_id>",
    methods=["PUT"],
)
def update_run(run_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    data = request.get_json(silent=True) or {}

    ok = cicd_store.update_pipeline_run(
        pid,
        run_id,
        data,
    )

    if not ok:
        return jsonify({
            "error": "Run not found"
        }), 404

    return jsonify({
        "success": True
    })


@bp.route(
    "/runs/<run_id>",
    methods=["DELETE"],
)
def delete_run(run_id: str):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    ok = cicd_store.delete_pipeline_run(
        pid,
        run_id,
    )

    if not ok:
        return jsonify({
            "error": "Run not found"
        }), 404

    return jsonify({
        "success": True
    })


# ---------------------------------------------------------------------------
# Manual approval
# ---------------------------------------------------------------------------


@bp.route(
    "/runs/<run_id>/approve",
    methods=["POST"],
)
def approve_run(run_id: str):
    """Approve a pipeline currently waiting for manual approval."""

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    if not run:
        return jsonify({
            "error": "Run not found"
        }), 404

    current_status = str(
        run.get("status") or ""
    ).upper()

    if current_status != "WAITING_APPROVAL":
        return jsonify({
            "error": "Run is not waiting for approval",
            "status": current_status,
        }), 409

    data = request.get_json(silent=True) or {}

    approved_by = (
        data.get("approved_by")
        or request.headers.get(
            "X-User-Email",
            "",
        )
        or request.headers.get(
            "X-User",
            "",
        )
    )

    try:
        ok = approve_pipeline_run(
            project_id=pid,
            run_id=run_id,
            approved_by=approved_by,
        )

    except Exception as exc:

        logger.exception(
            "Failed to approve CI/CD run %s",
            run_id,
        )

        return jsonify({
            "error": (
                "Failed to approve pipeline run: "
                f"{exc}"
            )
        }), 500

    if not ok:
        return jsonify({
            "error": "Failed to approve pipeline run"
        }), 409

    updated_run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    logger.info(
        "CI/CD run %s approved by %s",
        run_id,
        approved_by or "unknown",
    )

    return jsonify({
        "success": True,
        "message": "Pipeline approved",
        "run": updated_run,
    })


@bp.route(
    "/runs/<run_id>/reject",
    methods=["POST"],
)
def reject_run(run_id: str):
    """Reject a pipeline currently waiting for manual approval."""

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    if not run:
        return jsonify({
            "error": "Run not found"
        }), 404

    current_status = str(
        run.get("status") or ""
    ).upper()

    if current_status != "WAITING_APPROVAL":
        return jsonify({
            "error": "Run is not waiting for approval",
            "status": current_status,
        }), 409

    data = request.get_json(silent=True) or {}

    rejected_by = (
        data.get("rejected_by")
        or request.headers.get(
            "X-User-Email",
            "",
        )
        or request.headers.get(
            "X-User",
            "",
        )
    )

    reason = str(
        data.get("reason") or ""
    ).strip()

    try:
        ok = reject_pipeline_run(
            project_id=pid,
            run_id=run_id,
            rejected_by=rejected_by,
            reason=reason,
        )

    except Exception as exc:

        logger.exception(
            "Failed to reject CI/CD run %s",
            run_id,
        )

        return jsonify({
            "error": (
                "Failed to reject pipeline run: "
                f"{exc}"
            )
        }), 500

    if not ok:
        return jsonify({
            "error": "Failed to reject pipeline run"
        }), 409

    updated_run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    logger.info(
        "CI/CD run %s rejected by %s",
        run_id,
        rejected_by or "unknown",
    )

    return jsonify({
        "success": True,
        "message": "Pipeline rejected",
        "run": updated_run,
    })


# ---------------------------------------------------------------------------
# Step logs
# ---------------------------------------------------------------------------


@bp.route(
    "/runs/<run_id>/steps/<int:step_index>/log",
    methods=["GET"],
)
def get_run_step_log(
    run_id: str,
    step_index: int,
):

    pid = _project_id()

    if not pid:
        return jsonify({
            "error": "project_id is required"
        }), 400

    run = cicd_store.get_pipeline_run(
        pid,
        run_id,
    )

    if not run:
        return jsonify({
            "error": "Run not found"
        }), 404

    steps = run.get("steps", []) or []

    if (
        step_index < 0
        or step_index >= len(steps)
    ):
        return jsonify({
            "error": "Invalid step index"
        }), 404

    content = get_step_log(
        pid,
        run_id,
        step_index,
    )

    return jsonify({
        "success": True,
        "content": content,
    })