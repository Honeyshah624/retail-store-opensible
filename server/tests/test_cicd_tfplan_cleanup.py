from __future__ import annotations

import io
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# Keep this unit test independent of Flask, which is an application runtime
# dependency and is not installed in every source-check environment.
cloud_provisioning_stub = types.ModuleType("services.cloud_provisioning")
cloud_provisioning_stub._create_execution = lambda *args, **kwargs: "execution-1"
cloud_provisioning_stub._stack_dir = lambda project_id, stack: Path(stack)
cloud_provisioning_stub._valid_name = lambda name: bool(
    name
    and name != "_template"
    and re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,48}[a-z0-9]", name)
)
using_cloud_stub = "services.cloud_provisioning" not in sys.modules
if using_cloud_stub:
    sys.modules["services.cloud_provisioning"] = cloud_provisioning_stub

from services import cicd_engine  # noqa: E402

if using_cloud_stub:
    sys.modules.pop("services.cloud_provisioning", None)


class TfplanLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project_dir = Path(self.temp_dir.name) / "projects" / "project-1"
        self.stack_dir = self.project_dir / "stacks" / "envs" / "demo-stack"
        self.stack_dir.mkdir(parents=True)

        self.project_dir_patch = patch.object(
            cicd_engine.cicd_store,
            "_project_dir",
            return_value=self.project_dir,
        )
        self.cloud_stack_dir_patch = patch.object(
            cicd_engine,
            "cloud_stack_dir",
            side_effect=lambda project_id, stack: (
                self.project_dir / "stacks" / "envs" / stack
            ),
        )
        self.project_dir_patch.start()
        self.cloud_stack_dir_patch.start()
        self.addCleanup(self.project_dir_patch.stop)
        self.addCleanup(self.cloud_stack_dir_patch.stop)

    @property
    def plan_path(self) -> Path:
        return self.stack_dir / "tfplan"

    def tofu_step(self, action: str) -> dict:
        return {
            "step_type": "tofu",
            "config": {"stack": "demo-stack", "action": action},
        }

    def run_tofu_step(self, action: str, result: str) -> str:
        def create_execution(*args, **kwargs):
            if action == "plan":
                self.plan_path.write_bytes(b"new approved plan")
            return "execution-1"

        with (
            patch.object(
                cicd_engine,
                "create_tofu_execution",
                side_effect=create_execution,
            ),
            patch.object(
                cicd_engine,
                "_wait_for_worker_execution",
                return_value=result,
            ),
        ):
            return cicd_engine._execute_tofu_step(
                "project-1",
                self.tofu_step(action),
                io.StringIO(),
            )

    def test_successful_plan_replaces_stale_plan_and_is_retained(self) -> None:
        self.plan_path.write_bytes(b"stale plan")

        status = self.run_tofu_step("plan", "SUCCESS")

        self.assertEqual("SUCCESS", status)
        self.assertEqual(b"new approved plan", self.plan_path.read_bytes())

    def test_failed_plan_is_deleted(self) -> None:
        status = self.run_tofu_step("plan", "FAILED")

        self.assertEqual("FAILED", status)
        self.assertFalse(self.plan_path.exists())

    def test_apply_always_deletes_plan(self) -> None:
        for result in ("SUCCESS", "FAILED"):
            with self.subTest(result=result):
                self.plan_path.write_bytes(b"approved plan")

                status = self.run_tofu_step("apply", result)

                self.assertEqual(result, status)
                self.assertFalse(self.plan_path.exists())

    def test_cleanup_failure_does_not_change_apply_result(self) -> None:
        self.plan_path.mkdir()

        status = self.run_tofu_step("apply", "SUCCESS")

        self.assertEqual("SUCCESS", status)
        self.assertTrue(self.plan_path.is_dir())

    def test_rejection_deletes_plans_after_run_update(self) -> None:
        self.plan_path.write_bytes(b"approved plan")
        run = {
            "status": "WAITING_APPROVAL",
            "approval_step": 1,
            "steps": [
                self.tofu_step("plan"),
                {"step_type": "approval", "status": "WAITING_APPROVAL"},
                self.tofu_step("apply"),
            ],
        }

        with (
            patch.object(
                cicd_engine.cicd_store,
                "get_pipeline_run",
                return_value=run,
            ),
            patch.object(
                cicd_engine.cicd_store,
                "update_pipeline_run",
                return_value=True,
            ),
        ):
            ok = cicd_engine.reject_pipeline_run("project-1", "run-1")

        self.assertTrue(ok)
        self.assertFalse(self.plan_path.exists())

    def test_failed_rejection_update_preserves_plan(self) -> None:
        self.plan_path.write_bytes(b"approved plan")
        run = {
            "status": "WAITING_APPROVAL",
            "approval_step": 1,
            "steps": [self.tofu_step("plan")],
        }

        with (
            patch.object(
                cicd_engine.cicd_store,
                "get_pipeline_run",
                return_value=run,
            ),
            patch.object(
                cicd_engine.cicd_store,
                "update_pipeline_run",
                return_value=False,
            ),
        ):
            ok = cicd_engine.reject_pipeline_run("project-1", "run-1")

        self.assertFalse(ok)
        self.assertTrue(self.plan_path.exists())

    def test_invalid_stack_name_cannot_escape_project(self) -> None:
        outside = self.project_dir.parent / "tfplan"
        outside.write_bytes(b"must remain")

        cleaned = cicd_engine._cleanup_tfplan(
            "project-1",
            "../..",
            reason="test",
        )

        self.assertFalse(cleaned)
        self.assertTrue(outside.exists())


if __name__ == "__main__":
    unittest.main()
