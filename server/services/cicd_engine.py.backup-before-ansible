"""CI/CD Pipeline Orchestrator.

Runs CI/CD pipeline steps in a background thread and writes per-step
logs into:

    cicd/runs/<run_id>/step_<index>.log

Supported step types:

- shell
    Execute a shell command on the OpenSible server.

- tofu
    Queue a native OpenSible TOFU_RUN execution and wait for the
    OpenSible worker to finish it.

- approval
    Pause the pipeline in WAITING_APPROVAL state until the run is
    approved or rejected.

- ansible
    Queue a native OpenSible Ansible execution and wait for the
    OpenSible worker to finish it.

Target flow:

    OpenTofu Init
        ↓
    OpenTofu Validate
        ↓
    OpenTofu Plan -out=tfplan
        ↓
    Manual Approval
        ↓
    OpenTofu Apply tfplan
        ↓
    Ansible Deployment
        ↓
    Helmfile
        ↓
    Retail Store
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid

from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

import storage.cicd_store as cicd_store

from services.cloud_provisioning import (
    _create_execution as create_tofu_execution,
)

from services.execution_history import (
    create_execution_record,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TERMINAL_SUCCESS = {
    "SUCCESS",
    "SUCCEEDED",
    "COMPLETED",
}

TERMINAL_FAILURE = {
    "FAILED",
    "FAILURE",
    "ERROR",
    "CANCELED",
    "CANCELLED",
    "REJECTED",
}

TOFU_ACTIONS = {
    "init",
    "validate",
    "plan",
    "apply",
    "destroy",
    "fmt",
    "refresh",
    "drift",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def trigger_pipeline_run(
    project_id: str,
    pipeline_id: str,
    trigger_type: str = "manual",
    git_commit: str = "",
    triggered_by: str = "",
) -> Optional[str]:
    """Create a pipeline run and start execution in a background thread."""

    pipeline = cicd_store.get_pipeline(
        project_id,
        pipeline_id,
    )

    if not pipeline:
        logger.error(
            "Pipeline %s not found",
            pipeline_id,
        )
        return None

    steps: List[Dict[str, Any]] = []

    for stage in pipeline.get("stages", []) or []:

        stage_name = stage.get(
            "name",
            "stage",
        )

        for step in stage.get("steps", []) or []:

            steps.append(
                {
                    "stage_name": stage_name,
                    "step_name": step.get(
                        "name",
                        "step",
                    ),
                    "step_type": step.get(
                        "type",
                        "shell",
                    ),
                    "config": step.get(
                        "config",
                        {},
                    )
                    or {},
                    "status": "PENDING",
                    "started_at": None,
                    "finished_at": None,
                    "log_ref": None,
                }
            )

    run_id = cicd_store.create_pipeline_run(
        project_id,
        pipeline_id,
        {
            "trigger_type": trigger_type,
            "status": "QUEUED",
            "git_commit": git_commit,
            "triggered_by": triggered_by,
            "steps": steps,
            "current_step": 0,
            "approval_step": None,
            "approved": False,
            "rejected": False,
        },
    )

    if not run_id:
        logger.error(
            "Unable to create pipeline run for %s",
            pipeline_id,
        )
        return None

    _start_pipeline_thread(
        project_id,
        run_id,
    )

    return run_id


def approve_pipeline_run(
    project_id: str,
    run_id: str,
    approved_by: str = "",
) -> bool:
    """Approve a pipeline waiting at an approval step."""

    run = cicd_store.get_pipeline_run(
        project_id,
        run_id,
    )

    if not run:
        return False

    if str(
        run.get("status") or ""
    ).upper() != "WAITING_APPROVAL":
        return False

    ok = cicd_store.update_pipeline_run(
        project_id,
        run_id,
        {
            "status": "QUEUED",
            "approved": True,
            "rejected": False,
            "approved_by": approved_by,
            "approved_at": time.time(),
        },
    )

    if not ok:
        return False

    logger.info(
        "Pipeline %s approved by %s",
        run_id,
        approved_by or "unknown",
    )

    _start_pipeline_thread(
        project_id,
        run_id,
    )

    return True


def reject_pipeline_run(
    project_id: str,
    run_id: str,
    rejected_by: str = "",
    reason: str = "",
) -> bool:
    """Reject a pipeline waiting at an approval step."""

    run = cicd_store.get_pipeline_run(
        project_id,
        run_id,
    )

    if not run:
        return False

    if str(
        run.get("status") or ""
    ).upper() != "WAITING_APPROVAL":
        return False

    steps = list(
        run.get("steps", []) or []
    )

    approval_step = run.get(
        "approval_step"
    )

    if (
        approval_step is not None
        and 0 <= int(approval_step) < len(steps)
    ):

        idx = int(approval_step)

        steps[idx]["status"] = "REJECTED"
        steps[idx]["finished_at"] = time.time()

        for i in range(
            idx + 1,
            len(steps),
        ):
            if steps[i].get("status") == "PENDING":
                steps[i]["status"] = "SKIPPED"

    ok = cicd_store.update_pipeline_run(
        project_id,
        run_id,
        {
            "status": "REJECTED",
            "rejected": True,
            "approved": False,
            "rejected_by": rejected_by,
            "rejection_reason": reason,
            "rejected_at": time.time(),
            "steps": steps,
        },
    )

    logger.info(
        "Pipeline %s rejected by %s",
        run_id,
        rejected_by or "unknown",
    )

    return bool(ok)


def get_step_log(
    project_id: str,
    run_id: str,
    step_index: int,
) -> str:
    """Return CI/CD step log."""

    log_path = _step_log_path(
        project_id,
        run_id,
        step_index,
    )

    if not log_path.exists():
        return ""

    try:
        return log_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception as exc:

        logger.warning(
            "Error reading step log %s: %s",
            log_path,
            exc,
        )

        return ""


# ---------------------------------------------------------------------------
# Thread management
# ---------------------------------------------------------------------------


def _start_pipeline_thread(
    project_id: str,
    run_id: str,
) -> None:

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(
            project_id,
            run_id,
        ),
        name=f"cicd-run-{run_id[:8]}",
        daemon=True,
    )

    thread.start()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _run_dir(
    project_id: str,
    run_id: str,
) -> Path:

    project_dir = cicd_store._project_dir(
        project_id
    )

    directory = (
        project_dir
        / "cicd"
        / "runs"
        / run_id
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def _step_log_path(
    project_id: str,
    run_id: str,
    index: int,
) -> Path:

    return (
        _run_dir(
            project_id,
            run_id,
        )
        / f"step_{index}.log"
    )


def _project_dir(
    project_id: str,
) -> Path:

    return cicd_store._project_dir(
        project_id
    )


def _project_repo_dir(
    project_id: str,
) -> Path:

    return (
        _project_dir(project_id)
        / "repo"
    )


def _generated_playbooks_dir(
    project_id: str,
) -> Path:

    directory = (
        _project_dir(project_id)
        / "runtime"
        / "generated_playbooks"
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


def _run_pipeline_thread(
    project_id: str,
    run_id: str,
) -> None:

    try:

        run = cicd_store.get_pipeline_run(
            project_id,
            run_id,
        )

        if not run:
            return

        if str(
            run.get("status") or ""
        ).upper() in {
            "SUCCESS",
            "FAILED",
            "REJECTED",
        }:
            return

        steps: List[Dict[str, Any]] = list(
            run.get("steps", []) or []
        )

        current_step = int(
            run.get("current_step") or 0
        )

        approved = bool(
            run.get("approved", False)
        )

        approval_step = run.get(
            "approval_step"
        )

        cicd_store.update_pipeline_run(
            project_id,
            run_id,
            {
                "status": "RUNNING",
            },
        )

        i = current_step

        while i < len(steps):

            step = steps[i]

            step_type = str(
                step.get("step_type")
                or "shell"
            ).lower()

            # ---------------------------------------------------------------
            # Manual approval
            # ---------------------------------------------------------------

            if step_type == "approval":

                # Returning after approval:
                # mark the approval step successful and continue.
                if (
                    approved
                    and approval_step is not None
                    and int(approval_step) == i
                ):

                    step["status"] = "SUCCESS"

                    if not step.get("started_at"):
                        step["started_at"] = time.time()

                    step["finished_at"] = time.time()
                    step["log_ref"] = f"step_{i}.log"

                    log_path = _step_log_path(
                        project_id,
                        run_id,
                        i,
                    )

                    with open(
                        log_path,
                        "a",
                        encoding="utf-8",
                    ) as log:

                        log.write(
                            "=== Manual Approval ===\n\n"
                        )

                        log.write(
                            "Pipeline approved.\n"
                        )

                        approved_by = run.get(
                            "approved_by"
                        )

                        if approved_by:
                            log.write(
                                f"Approved by: {approved_by}\n"
                            )

                    i += 1

                    cicd_store.update_pipeline_run(
                        project_id,
                        run_id,
                        {
                            "steps": steps,
                            "current_step": i,
                            "approved": False,
                            "approval_step": None,
                        },
                    )

                    approved = False
                    approval_step = None

                    continue

                # First arrival at approval gate.
                step["status"] = "WAITING_APPROVAL"
                step["started_at"] = time.time()
                step["log_ref"] = f"step_{i}.log"

                log_path = _step_log_path(
                    project_id,
                    run_id,
                    i,
                )

                with open(
                    log_path,
                    "w",
                    encoding="utf-8",
                ) as log:

                    log.write(
                        "=== Manual Approval ===\n\n"
                    )

                    log.write(
                        "Pipeline is waiting for approval.\n"
                    )

                cicd_store.update_pipeline_run(
                    project_id,
                    run_id,
                    {
                        "status": "WAITING_APPROVAL",
                        "steps": steps,
                        "current_step": i,
                        "approval_step": i,
                        "approved": False,
                    },
                )

                logger.info(
                    "Pipeline %s waiting for approval at step %s",
                    run_id,
                    i,
                )

                return

            # ---------------------------------------------------------------
            # Normal execution step
            # ---------------------------------------------------------------

            step["status"] = "RUNNING"
            step["started_at"] = time.time()
            step["log_ref"] = f"step_{i}.log"

            cicd_store.update_pipeline_run(
                project_id,
                run_id,
                {
                    "steps": steps,
                    "current_step": i,
                },
            )

            status = _execute_step(
                project_id,
                run_id,
                i,
                step,
            )

            step["status"] = status
            step["finished_at"] = time.time()

            if status != "SUCCESS":

                for j in range(
                    i + 1,
                    len(steps),
                ):
                    if (
                        steps[j].get("status")
                        == "PENDING"
                    ):
                        steps[j]["status"] = "SKIPPED"

                cicd_store.update_pipeline_run(
                    project_id,
                    run_id,
                    {
                        "status": "FAILED",
                        "steps": steps,
                        "current_step": i,
                    },
                )

                logger.error(
                    "Pipeline run %s failed at step %s",
                    run_id,
                    i,
                )

                return

            i += 1

            cicd_store.update_pipeline_run(
                project_id,
                run_id,
                {
                    "steps": steps,
                    "current_step": i,
                },
            )

        cicd_store.update_pipeline_run(
            project_id,
            run_id,
            {
                "status": "SUCCESS",
                "steps": steps,
                "current_step": len(steps),
            },
        )

        logger.info(
            "Pipeline run %s finished successfully",
            run_id,
        )

    except Exception as exc:

        logger.exception(
            "Pipeline run %s crashed: %s",
            run_id,
            exc,
        )

        try:
            cicd_store.update_pipeline_run(
                project_id,
                run_id,
                {
                    "status": "FAILED",
                },
            )

        except Exception:
            pass


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


def _execute_step(
    project_id: str,
    run_id: str,
    index: int,
    step: Dict[str, Any],
) -> str:

    log_path = _step_log_path(
        project_id,
        run_id,
        index,
    )

    step_type = str(
        step.get("step_type")
        or "shell"
    ).lower()

    config = (
        step.get("config", {})
        or {}
    )

    with open(
        log_path,
        "w",
        encoding="utf-8",
    ) as log:

        log.write(
            f"=== Step: "
            f"{step.get('step_name')} "
            f"({step_type}) ===\n"
        )

        log.write(
            f"=== Stage: "
            f"{step.get('stage_name')} ===\n\n"
        )

        log.flush()

        # ---------------------------------------------------------------
        # Shell
        # ---------------------------------------------------------------

        if step_type == "shell":

            return _execute_shell_step(
                project_id,
                run_id,
                config,
                log,
            )

        # ---------------------------------------------------------------
        # OpenTofu
        # ---------------------------------------------------------------

        if step_type == "tofu":

            return _execute_tofu_step(
                project_id,
                step,
                log,
            )

        # ---------------------------------------------------------------
        # Ansible
        # ---------------------------------------------------------------

        if step_type == "ansible":

            return _execute_ansible_step(
                project_id,
                step,
                log,
            )

        log.write(
            f"[error] unknown step type: "
            f"{step_type}\n"
        )

        return "FAILED"


# ---------------------------------------------------------------------------
# Shell execution
# ---------------------------------------------------------------------------


def _execute_shell_step(
    project_id: str,
    run_id: str,
    config: Dict[str, Any],
    log: TextIO,
) -> str:

    command = (
        config.get("command")
        or config.get("script")
        or ""
    )

    if not str(command).strip():

        log.write(
            "[error] no command provided\n"
        )

        return "FAILED"

    log.write(
        f"$ {command}\n\n"
    )

    log.flush()

    try:

        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(
                _run_dir(
                    project_id,
                    run_id,
                )
            ),
            env=os.environ.copy(),
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None

        for line in proc.stdout:

            log.write(line)
            log.flush()

        rc = proc.wait()

        log.write(
            f"\n[exit code: {rc}]\n"
        )

        return (
            "SUCCESS"
            if rc == 0
            else "FAILED"
        )

    except Exception as exc:

        log.write(
            f"\n[exception] {exc}\n"
        )

        return "FAILED"


# ---------------------------------------------------------------------------
# OpenTofu
# ---------------------------------------------------------------------------


def _execute_tofu_step(
    project_id: str,
    step: Dict[str, Any],
    log: TextIO,
) -> str:

    config = (
        step.get("config", {})
        or {}
    )

    action = str(
        config.get("action")
        or config.get("tofu_action")
        or ""
    ).strip().lower()

    stack = str(
        config.get("stack")
        or config.get("stack_name")
        or ""
    ).strip()

    if action not in TOFU_ACTIONS:

        log.write(
            f"[error] invalid tofu action: "
            f"{action}\n"
        )

        return "FAILED"

    if not stack:

        log.write(
            "[error] stack name is required\n"
        )

        return "FAILED"

    log.write(
        f"[tofu] stack: {stack}\n"
    )

    log.write(
        f"[tofu] action: {action}\n"
    )

    log.flush()

    try:

        execution_id = create_tofu_execution(
            project_id,
            stack,
            action,
            triggered_by="cicd",
        )

    except Exception as exc:

        logger.exception(
            "Unable to queue OpenTofu execution"
        )

        log.write(
            f"[error] unable to queue "
            f"OpenTofu execution: {exc}\n"
        )

        return "FAILED"

    return _wait_for_worker_execution(
        project_id,
        execution_id,
        log,
    )


# ---------------------------------------------------------------------------
# Ansible
# ---------------------------------------------------------------------------


def _execute_ansible_step(
    project_id: str,
    step: Dict[str, Any],
    log: TextIO,
) -> str:
    """Queue an Ansible playbook for the native OpenSible worker.

    Recommended CI/CD configuration:

        type: ansible
        config:
          playbook_path: playbooks/retail-store-deploy.yml
          inventory_files:
            - inventory.yml
          ansible_config: ansible-config/ansible.cfg
          stage: apply

    playbook_path is relative to the OpenSible project's repo directory.
    """

    config = (
        step.get("config", {})
        or {}
    )

    playbook_path = str(
        config.get("playbook_path")
        or config.get("playbook")
        or ""
    ).strip()

    inventory_files = (
        config.get("inventory_files")
        or ["inventory.yml"]
    )

    ansible_config = str(
        config.get("ansible_config")
        or "ansible-config/ansible.cfg"
    ).strip()

    stage = str(
        config.get("stage")
        or "apply"
    ).strip().lower()

    worker_id = str(
        config.get("worker_id")
        or config.get("target_worker_id")
        or ""
    ).strip()

    if stage not in {
        "init",
        "validate",
        "plan",
        "apply",
    }:
        stage = "apply"

    if isinstance(
        inventory_files,
        str,
    ):
        inventory_files = [
            inventory_files
        ]

    if not playbook_path:

        log.write(
            "[error] ansible playbook_path "
            "is required\n"
        )

        return "FAILED"

    repo_dir = _project_repo_dir(
        project_id
    )

    source_playbook = (
        Path(playbook_path)
        if Path(playbook_path).is_absolute()
        else repo_dir / playbook_path
    )

    if not source_playbook.exists():

        log.write(
            "[error] playbook not found: "
            f"{source_playbook}\n"
        )

        return "FAILED"

    # ---------------------------------------------------------------
    # Validate inventory
    # ---------------------------------------------------------------

    resolved_inventory: List[str] = []

    for inventory in inventory_files:

        inventory = str(
            inventory
        ).strip()

        if not inventory:
            continue

        inventory_path = Path(
            inventory
        )

        if not inventory_path.is_absolute():
            inventory_path = (
                repo_dir
                / inventory
            )

        if not inventory_path.exists():

            log.write(
                "[error] inventory not found: "
                f"{inventory_path}\n"
            )

            return "FAILED"

        # Worker expects project-relative inventory names.
        resolved_inventory.append(
            inventory
        )

    if not resolved_inventory:

        log.write(
            "[error] no inventory files configured\n"
        )

        return "FAILED"

    # ---------------------------------------------------------------
    # Validate ansible.cfg
    # ---------------------------------------------------------------

    ansible_config_path = Path(
        ansible_config
    )

    if not ansible_config_path.is_absolute():

        # Existing OpenSible layout normally keeps ansible config
        # outside repo:
        #
        # projects/<id>/ansible-config/ansible.cfg
        #
        project_candidate = (
            _project_dir(project_id)
            / ansible_config
        )

        repo_candidate = (
            repo_dir
            / ansible_config
        )

        if project_candidate.exists():
            ansible_config_path = (
                project_candidate
            )

        elif repo_candidate.exists():
            ansible_config_path = (
                repo_candidate
            )

    if not ansible_config_path.exists():

        log.write(
            "[error] ansible_config not found: "
            f"{ansible_config_path}\n"
        )

        return "FAILED"

    # ---------------------------------------------------------------
    # Generate worker-visible playbook
    # ---------------------------------------------------------------

    execution_id = str(
        uuid.uuid4()
    )

    generated_playbook = (
        _generated_playbooks_dir(
            project_id
        )
        / f"{execution_id}.yml"
    )

    try:

        shutil.copyfile(
            source_playbook,
            generated_playbook,
        )

    except Exception as exc:

        log.write(
            "[error] unable to prepare generated "
            f"playbook: {exc}\n"
        )

        return "FAILED"

    # ---------------------------------------------------------------
    # Lifecycle flags
    # ---------------------------------------------------------------

    check_mode = bool(
        config.get(
            "check_mode",
            False,
        )
    )

    syntax_check = bool(
        config.get(
            "syntax_check",
            False,
        )
    )

    galaxy_install = bool(
        config.get(
            "galaxy_install",
            False,
        )
    )

    diff_mode = bool(
        config.get(
            "diff_mode",
            False,
        )
    )

    if stage == "validate":
        syntax_check = True

    elif stage == "init":
        galaxy_install = True

    elif stage == "plan":
        check_mode = True
        diff_mode = True

    verbosity = (
        config.get("verbosity")
        or None
    )

    forks = config.get(
        "forks"
    )

    connection_timeout = config.get(
        "connection_timeout"
    )

    run_params: Dict[str, Any] = {
        "temp_playbook": str(
            generated_playbook
        ),
        "inventory_files": (
            resolved_inventory
        ),
        "ansible_config": (
            ansible_config
        ),
        "project_dir": str(
            _project_dir(project_id)
        ),
        "check_mode": check_mode,
        "verbosity": verbosity,
        "forks": (
            int(forks)
            if forks is not None
            and str(forks).strip()
            else None
        ),
        "force_handlers": bool(
            config.get(
                "force_handlers",
                False,
            )
        ),
        "connection_timeout": (
            int(connection_timeout)
            if connection_timeout
            is not None
            and str(
                connection_timeout
            ).strip()
            else None
        ),
        "strategy": str(
            config.get(
                "strategy",
                "linear",
            )
        ),
        "vault_id": (
            config.get("vault_id")
            or None
        ),
        "stage": stage,
        "syntax_check": syntax_check,
        "galaxy_install": galaxy_install,
        "diff_mode": diff_mode,
    }

    if worker_id:

        run_params[
            "target_worker_id"
        ] = worker_id

        run_params[
            "requirements"
        ] = {
            "worker_id": worker_id
        }

    execution_data = {
        "playbookName": (
            config.get("playbook_name")
            or source_playbook.stem
        ),
        "mode": "PER_GROUP",
        "inventorySnapshot": {
            "groups": []
        },
        "selectionSnapshot": {
            "playbookName": (
                config.get(
                    "playbook_name"
                )
                or source_playbook.stem
            )
        },
        "stats": {
            "hostsTargeted": 0,
            "totalRoleExecutions": 0,
        },
        "warnings": [],
        "status": "QUEUED",
        "runParams": run_params,
        "play_name": (
            config.get("play_name")
            or (
                f"[{stage}] "
                f"{source_playbook.stem}"
            )
        ),
        "triggeredBy": "cicd",
        "triggeredByUserId": "",
    }

    log.write(
        "[ansible] preparing native "
        "OpenSible execution\n"
    )

    log.write(
        f"[ansible] playbook: "
        f"{source_playbook}\n"
    )

    log.write(
        f"[ansible] inventory: "
        f"{resolved_inventory}\n"
    )

    log.write(
        f"[ansible] ansible config: "
        f"{ansible_config}\n"
    )

    log.write(
        f"[ansible] stage: "
        f"{stage}\n"
    )

    log.flush()

    try:

        created_id = create_execution_record(
            execution_data,
            project_id=project_id,
            execution_id=execution_id,
        )

    except Exception as exc:

        logger.exception(
            "Unable to queue Ansible execution"
        )

        log.write(
            "[error] unable to queue "
            f"Ansible execution: {exc}\n"
        )

        return "FAILED"

    if not created_id:

        log.write(
            "[error] OpenSible did not create "
            "the Ansible execution record\n"
        )

        return "FAILED"

    log.write(
        f"[ansible] queued execution: "
        f"{created_id}\n"
    )

    log.flush()

    return _wait_for_worker_execution(
        project_id,
        created_id,
        log,
    )


# ---------------------------------------------------------------------------
# Native worker execution monitoring
# ---------------------------------------------------------------------------


def _execution_file(
    project_id: str,
    execution_id: str,
) -> Path:

    return (
        _project_dir(project_id)
        / "history"
        / "executions"
        / f"{execution_id}.json"
    )


def _execution_log_file(
    project_id: str,
    execution_id: str,
) -> Path:

    return (
        _project_dir(project_id)
        / "history"
        / "logs"
        / f"{execution_id}.log"
    )


def _read_execution(
    project_id: str,
    execution_id: str,
) -> Optional[Dict[str, Any]]:

    path = _execution_file(
        project_id,
        execution_id,
    )

    if not path.exists():
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as exc:

        logger.warning(
            "Unable to read execution %s: %s",
            execution_id,
            exc,
        )

        return None


def _append_new_worker_log(
    project_id: str,
    execution_id: str,
    log: TextIO,
    offset: int,
) -> int:
    """Copy newly produced worker output into the CI/CD step log."""

    worker_log = _execution_log_file(
        project_id,
        execution_id,
    )

    if not worker_log.exists():
        return offset

    try:

        size = worker_log.stat().st_size

        if size < offset:
            offset = 0

        if size == offset:
            return offset

        with open(
            worker_log,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as source:

            source.seek(offset)

            content = source.read()

            new_offset = source.tell()

        if content:

            log.write(content)

            if not content.endswith("\n"):
                log.write("\n")

            log.flush()

        return new_offset

    except Exception as exc:

        logger.debug(
            "Unable to stream execution log %s: %s",
            execution_id,
            exc,
        )

        return offset


def _wait_for_worker_execution(
    project_id: str,
    execution_id: str,
    log: TextIO,
    timeout: int = 3600,
) -> str:

    log.write(
        f"[worker] queued execution: "
        f"{execution_id}\n"
    )

    log.flush()

    started = time.time()

    previous_status: Optional[str] = None

    log_offset = 0

    missing_count = 0

    while True:

        # Stream worker output into CI/CD log.
        log_offset = _append_new_worker_log(
            project_id,
            execution_id,
            log,
            log_offset,
        )

        execution = _read_execution(
            project_id,
            execution_id,
        )

        if execution is None:

            missing_count += 1

            # Execution file may not be visible immediately.
            if missing_count > 30:

                log.write(
                    "[error] worker execution "
                    "record not found\n"
                )

                return "FAILED"

            time.sleep(1)

            continue

        missing_count = 0

        status = str(
            execution.get("status")
            or "UNKNOWN"
        ).upper()

        if status != previous_status:

            log.write(
                f"[worker] status: "
                f"{status}\n"
            )

            log.flush()

            previous_status = status

        if status in TERMINAL_SUCCESS:

            # One final log read after completion.
            time.sleep(0.25)

            _append_new_worker_log(
                project_id,
                execution_id,
                log,
                log_offset,
            )

            log.write(
                "\n[worker] execution "
                "completed successfully\n"
            )

            log.flush()

            return "SUCCESS"

        if status in TERMINAL_FAILURE:

            time.sleep(0.25)

            _append_new_worker_log(
                project_id,
                execution_id,
                log,
                log_offset,
            )

            log.write(
                "\n[worker] execution "
                f"failed with status "
                f"{status}\n"
            )

            log.flush()

            return "FAILED"

        if (
            time.time() - started
            > timeout
        ):

            log.write(
                "\n[error] worker execution "
                f"timed out after "
                f"{timeout} seconds\n"
            )

            log.flush()

            return "FAILED"

        time.sleep(2)