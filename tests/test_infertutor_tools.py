from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starter_code import generate_submission_artifacts as submission
from starter_code import bootstrap_infertutor_env as bootstrap
from starter_code import load_test_infertutor as load_test
from starter_code import preflight_infertutor as preflight
from starter_code import result_schema
from starter_code import run_infertutor_experiment as runner
from starter_code import score_infertutor as scorer


def safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


class RunExperimentTests(unittest.TestCase):
    def test_sanitize_label_normalizes_and_truncates(self):
        label = " My_Label For Modal !!! " + ("abc" * 30)
        sanitized = runner.sanitize_label(label)
        self.assertRegex(sanitized, r"^[a-z0-9-]+$")
        self.assertLessEqual(len(sanitized), 48)

    def test_sanitize_label_rejects_empty_result(self):
        with self.assertRaises(ValueError):
            runner.sanitize_label("!!!")

    def test_replace_once_requires_exact_match_count(self):
        with self.assertRaises(RuntimeError):
            runner.replace_once("abc abc", "abc", "x")

    @mock.patch("starter_code.run_infertutor_experiment.shutil.which", return_value=None)
    def test_ensure_command_available_rejects_missing_cli(self, _mock_which):
        with self.assertRaises(SystemExit):
            runner.ensure_command_available("modal")

    @mock.patch("starter_code.run_infertutor_experiment.run_command_capture")
    def test_collect_git_metadata_reads_commit_branch_and_dirty(self, mock_capture):
        mock_capture.side_effect = ["abc123", "main", " M file.py"]
        metadata = runner.collect_git_metadata()
        self.assertEqual(metadata["commit"], "abc123")
        self.assertEqual(metadata["branch"], "main")
        self.assertTrue(metadata["is_dirty"])

    def test_validate_args_rejects_invalid_pause_range(self):
        args = argparse.Namespace(
            tp=1,
            replicas=1,
            max_model_len=8192,
            max_batch_tokens=4096,
            max_seqs=32,
            concurrent_inputs=64,
            mm_max_pixels=401408,
            users=10,
            duration=60,
            max_tokens=96,
            request_timeout=180,
            health_timeout=900,
            gpu_count=None,
            ramp_up=0,
            seed=1234,
            min_pause=2.0,
            max_pause=1.0,
        )
        with self.assertRaises(ValueError):
            runner.validate_args(args)

    def test_patch_modal_app_writes_generated_config(self):
        args = argparse.Namespace(
            label="Prod Smoke",
            model="Qwen/Qwen3-VL-4B-Instruct",
            gpu_type="H100",
            gpu_count=None,
            tp=2,
            replicas=3,
            dtype="bfloat16",
            prefix_cache=True,
            chunked_prefill=False,
            fast_boot=True,
            max_model_len=8192,
            max_batch_tokens=4096,
            max_seqs=16,
            concurrent_inputs=32,
            mm_max_pixels=123456,
        )
        path = runner.patch_modal_app(args)
        self.addCleanup(lambda: safe_unlink(path))
        generated = path.read_text(encoding="utf-8")
        self.assertIn('app = modal.App("infertutor-prod-smoke")', generated)
        self.assertIn("TENSOR_PARALLEL = 2", generated)
        self.assertIn("MAX_CONTAINERS = 3", generated)
        self.assertIn("ENABLE_CHUNKED_PREFILL = False", generated)

    @mock.patch("starter_code.run_infertutor_experiment.subprocess.run")
    def test_run_load_test_passes_extended_flags(self, mock_run):
        args = argparse.Namespace(
            model="Qwen/Qwen3-VL-4B-Instruct",
            mode="mixed",
            users=12,
            duration=30,
            ramp_up=5,
            max_tokens=80,
            request_timeout=90,
            min_pause=0.1,
            max_pause=0.5,
            seed=1234,
            label="demo",
            gpu_count=None,
            tp=1,
            replicas=2,
        )
        runner.run_load_test("https://example.modal.run", args)
        cmd = mock_run.call_args.kwargs["args"] if "args" in mock_run.call_args.kwargs else mock_run.call_args.args[0]
        self.assertIn("--request-timeout", cmd)
        self.assertIn("--min-pause", cmd)
        self.assertIn("--max-pause", cmd)
        self.assertIn("--seed", cmd)
        self.assertIn("--runner-command", cmd)
        self.assertIn("--app-name", cmd)
        self.assertIn("--git-commit", cmd)
        self.assertIn("--git-branch", cmd)
        self.assertIn("--git-dirty", cmd)
        self.assertIn("--total-gpus", cmd)


class LoadTesterTests(unittest.TestCase):
    def test_extract_content_handles_string_and_list_payloads(self):
        self.assertEqual(load_test.extract_content({"content": "hello"}), "hello")
        self.assertEqual(
            load_test.extract_content(
                {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
            ),
            "ab",
        )
        self.assertEqual(load_test.extract_content({"content": [{"type": "image"}]}), "")

    def test_validate_args_rejects_bad_total_gpus(self):
        args = argparse.Namespace(
            users=1,
            duration=1,
            ramp_up=0,
            max_tokens=1,
            request_timeout=1,
            total_gpus=0,
            min_pause=0,
            max_pause=0,
        )
        with self.assertRaises(ValueError):
            load_test.validate_args(args)

    def test_stats_results_include_error_breakdown(self):
        stats = load_test.Stats(started_at=1.0)
        with mock.patch("starter_code.load_test_infertutor.time.time", return_value=3.0):
            self._run_async(stats.success(100.0, 10.0, 200.0, 5))
            self._run_async(
                stats.error(error_type="http_error", status_code=503, detail="server overloaded")
            )
            results = stats.results()
        self.assertEqual(results["total_requests"], 2)
        self.assertEqual(results["total_successes"], 1)
        self.assertEqual(results["errors_by_type"]["http_error"], 1)
        self.assertEqual(results["errors_by_status"]["503"], 1)
        self.assertEqual(results["last_error"], "server overloaded")

    def _run_async(self, coro):
        import asyncio

        return asyncio.run(coro)


class ScoreTests(unittest.TestCase):
    def test_load_result_requires_config_and_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text(json.dumps({"bad": True}), encoding="utf-8")
            with self.assertRaises(ValueError):
                scorer.load_result(path)

    def test_score_uses_goodput_formula(self):
        value = result_schema.score_result(
            {
                "config": {"users": 10, "total_gpus": 2},
                "results": {
                    "error_rate": 0.25,
                    "aggregate_stream_chunks_per_s": 100.0,
                    "ttft_p95_ms": 1000.0,
                    "itl_p95_ms": 50.0,
                },
            }
        )
        self.assertEqual(value, 7500.0)

    def test_validate_result_data_rejects_non_numeric_error_rate(self):
        with self.assertRaises(ValueError):
            result_schema.validate_result_data(
                {
                    "config": {"users": 10, "total_gpus": 1},
                    "results": {"error_rate": "bad"},
                }
            )


class SubmissionArtifactTests(unittest.TestCase):
    def test_render_experiment_table_and_bundle(self):
        sample = {
            "schema_version": 2,
            "config": {"mode": "text", "users": 10, "total_gpus": 1},
            "provenance": {
                "runner_command": "python3 run_infertutor_experiment.py --label demo",
                "app_name": "infertutor-demo",
                "source_control": {
                    "commit": "abc123",
                    "branch": "main",
                    "is_dirty": False,
                },
            },
            "results": {
                "error_rate": 0.1,
                "ttft_p95_ms": 1000.0,
                "itl_p95_ms": 50.0,
                "aggregate_stream_chunks_per_s": 200.0,
                "requests_per_s": 5.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = Path(tmpdir) / "demo.json"
            result_path.write_text(json.dumps(sample), encoding="utf-8")
            rows = submission.load_ranked_results(result_path)
            bundle_dir = Path(tmpdir) / "bundle"
            manifest = submission.write_bundle(rows, bundle_dir)
            self.assertEqual(manifest["mode"], "text")
            self.assertTrue((bundle_dir / "final_benchmark.json").exists())
            self.assertTrue((bundle_dir / "engineering_report.md").exists())
            self.assertTrue((bundle_dir / "experiment_table.md").exists())
            self.assertTrue((bundle_dir / "final_command.sh").exists())
            report = (bundle_dir / "engineering_report.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("InferTutor Engineering Report", report)
            self.assertIn(
                "python3 run_infertutor_experiment.py --label demo", report
            )
            self.assertIn("abc123", report)
            manifest_text = (bundle_dir / "submission_manifest.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"git_commit": "abc123"', manifest_text)


class PreflightTests(unittest.TestCase):
    def test_check_python_version_accepts_supported_version(self):
        with mock.patch.object(preflight.sys, "version_info", (3, 11, 8)):
            result = preflight.check_python_version()
        self.assertTrue(result.ok)

    def test_check_command_marks_missing_optional_tool_as_warning_candidate(self):
        with (
            mock.patch("starter_code.preflight_infertutor.shutil.which", return_value=None),
            mock.patch("starter_code.preflight_infertutor.Path.exists", return_value=False),
        ):
            result = preflight.check_command("modal", required=False)
        self.assertFalse(result.ok)
        self.assertFalse(result.required)

    @mock.patch("starter_code.preflight_infertutor.shutil.which", return_value=None)
    @mock.patch("starter_code.preflight_infertutor.sys.executable", "/tmp/venv/bin/python")
    @mock.patch("starter_code.preflight_infertutor.Path.exists", return_value=True)
    @mock.patch("starter_code.preflight_infertutor.Path.is_file", return_value=True)
    def test_resolve_command_path_falls_back_to_python_bin_dir(
        self, _mock_is_file, _mock_exists, _mock_which
    ):
        resolved = preflight.resolve_command_path("modal")
        self.assertEqual(resolved, "/tmp/venv/bin/modal")

    @mock.patch("starter_code.preflight_infertutor.shutil.which", return_value="/tmp/modal")
    @mock.patch("starter_code.preflight_infertutor.subprocess.run")
    def test_check_modal_auth_reports_unauthenticated_state(self, mock_run, _mock_which):
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="Token missing")
        result = preflight.check_modal_auth()
        self.assertFalse(result.ok)
        self.assertFalse(result.required)
        self.assertIn("Token missing", result.detail)

    @mock.patch("starter_code.preflight_infertutor.check_modal_auth")
    def test_run_preflight_can_require_modal_auth(self, mock_check_modal_auth):
        mock_check_modal_auth.return_value = preflight.CheckResult(
            name="modal_auth", ok=False, detail="missing", required=True
        )
        results = preflight.run_preflight(require_modal_auth=True)
        modal_auth = [result for result in results if result.name == "modal_auth"][0]
        self.assertTrue(modal_auth.required)

    def test_check_prompts_schema_passes_on_repo_prompts(self):
        result = preflight.check_prompts_schema()
        self.assertTrue(result.ok)

    def test_summarize_counts_required_and_optional_failures(self):
        summary = preflight.summarize(
            [
                preflight.CheckResult(name="a", ok=False, detail="bad", required=True),
                preflight.CheckResult(name="b", ok=False, detail="warn", required=False),
                preflight.CheckResult(name="c", ok=True, detail="ok", required=True),
            ]
        )
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["required_failures"], 1)
        self.assertEqual(summary["optional_failures"], 1)


class BootstrapTests(unittest.TestCase):
    @mock.patch("starter_code.bootstrap_infertutor_env.check_modal_auth")
    def test_ensure_modal_auth_succeeds_when_already_authenticated(self, mock_check):
        mock_check.return_value = preflight.CheckResult(
            name="modal_auth", ok=True, detail="authenticated", required=True
        )
        self.assertTrue(bootstrap.ensure_modal_auth(None, None))

    @mock.patch("starter_code.bootstrap_infertutor_env.check_modal_auth")
    def test_ensure_modal_auth_fails_without_credentials(self, mock_check):
        mock_check.return_value = preflight.CheckResult(
            name="modal_auth", ok=False, detail="Token missing", required=True
        )
        self.assertFalse(bootstrap.ensure_modal_auth(None, None))

    @mock.patch("starter_code.bootstrap_infertutor_env.run_modal_command")
    def test_ensure_hf_secret_accepts_existing_secret(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout="", stderr="Secret already exists")
        self.assertTrue(bootstrap.ensure_hf_secret("hf_value", "huggingface", False))

    @mock.patch("starter_code.bootstrap_infertutor_env.run_modal_command")
    def test_ensure_hf_secret_creates_secret(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
        self.assertTrue(bootstrap.ensure_hf_secret("hf_value", "huggingface", False))


if __name__ == "__main__":
    unittest.main()
