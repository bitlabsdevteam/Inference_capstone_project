from __future__ import annotations

import argparse
import importlib
import importlib.util
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


def load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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

    @mock.patch("starter_code.run_infertutor_experiment.httpx.post")
    def test_smoke_test_endpoint_posts_minimal_chat_request(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=200,
            text='{"id":"ok"}',
            json=mock.Mock(return_value={"choices": [{"message": {"content": "ready"}}]}),
        )
        smoke = runner.smoke_test_endpoint(
            "https://example.modal.run", "Qwen/Qwen3-VL-4B-Instruct"
        )
        self.assertEqual(mock_post.call_args.kwargs["timeout"], 30)
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Content-Type"],
            "application/json",
        )
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "Qwen/Qwen3-VL-4B-Instruct")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["max_tokens"], 16)
        self.assertTrue(smoke["ok"])
        self.assertEqual(smoke["status_code"], 200)
        self.assertEqual(smoke["response_excerpt"], "ready")

    @mock.patch.dict("starter_code.run_infertutor_experiment.os.environ", {"ENDPOINT_API_KEY": "secret-key"})
    @mock.patch("starter_code.run_infertutor_experiment.httpx.post")
    def test_smoke_test_endpoint_uses_bearer_auth_when_api_key_present(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=200,
            text='{"id":"ok"}',
            json=mock.Mock(return_value={"choices": [{"message": {"content": "ready"}}]}),
        )
        runner.smoke_test_endpoint(
            "https://example.modal.run", "Qwen/Qwen3-VL-4B-Instruct"
        )
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Authorization"],
            "Bearer secret-key",
        )

    @mock.patch("starter_code.run_infertutor_experiment.httpx.post")
    def test_smoke_test_endpoint_fails_on_bad_status(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=503,
            text="server overloaded",
        )
        with self.assertRaises(RuntimeError):
            runner.smoke_test_endpoint(
                "https://example.modal.run", "Qwen/Qwen3-VL-4B-Instruct"
            )

    @mock.patch("starter_code.run_infertutor_experiment.run_load_test")
    @mock.patch("starter_code.run_infertutor_experiment.smoke_test_endpoint")
    @mock.patch("starter_code.run_infertutor_experiment.wait_for_health")
    @mock.patch("starter_code.run_infertutor_experiment.ensure_command_available")
    @mock.patch("starter_code.run_infertutor_experiment.deploy", return_value="https://example.modal.run")
    @mock.patch("starter_code.run_infertutor_experiment.patch_modal_app")
    @mock.patch(
        "starter_code.run_infertutor_experiment.argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            label="smoke",
            model="Qwen/Qwen3-VL-4B-Instruct",
            gpu_type="H100",
            gpu_count=None,
            tp=1,
            replicas=1,
            dtype="bfloat16",
            prefix_cache=True,
            chunked_prefill=True,
            fast_boot=True,
            max_model_len=8192,
            max_batch_tokens=4096,
            max_seqs=32,
            concurrent_inputs=64,
            mm_max_pixels=512 * 28 * 28,
            mode="text",
            users=5,
            duration=30,
            ramp_up=5,
            max_tokens=64,
            request_timeout=180,
            min_pause=0.2,
            max_pause=1.2,
            seed=1234,
            health_timeout=900,
            url=None,
            deploy_only=False,
        ),
    )
    def test_main_runs_functional_smoke_before_load_test(
        self,
        _mock_parse_args,
        mock_patch_modal_app,
        mock_deploy,
        mock_ensure_command_available,
        mock_wait_for_health,
        mock_smoke_test,
        mock_run_load_test,
    ):
        mock_patch_modal_app.return_value = Path("modal_infertutor_app_generated.py")
        runner.main()
        mock_ensure_command_available.assert_called_once_with("modal")
        mock_wait_for_health.assert_called_once()
        mock_smoke_test.assert_called_once_with(
            "https://example.modal.run", "Qwen/Qwen3-VL-4B-Instruct"
        )
        self.assertEqual(mock_run_load_test.call_count, 1)
        self.assertTrue(mock_run_load_test.call_args.args[2]["ok"])


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

    @mock.patch.dict("starter_code.load_test_infertutor.os.environ", {"ENDPOINT_API_KEY": "secret-key"})
    def test_build_request_headers_uses_bearer_auth(self):
        headers = load_test.build_request_headers()
        self.assertEqual(headers["Authorization"], "Bearer secret-key")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_redact_endpoint_url_removes_full_modal_hostname(self):
        redacted = load_test.redact_endpoint_url(
            "https://bitlabs27--infertutor-smoke-serve.modal.run"
        )
        self.assertEqual(redacted, "https://***.modal.run")

    def test_build_result_payload_redacts_endpoint_url(self):
        args = argparse.Namespace(
            url="https://bitlabs27--infertutor-smoke-serve.modal.run",
            model="Qwen/Qwen3-VL-4B-Instruct",
            mode="text",
            users=5,
            duration=30,
            ramp_up=5,
            max_tokens=64,
            request_timeout=180,
            min_pause=0.2,
            max_pause=1.2,
            label="smoke",
            total_gpus=1,
            seed=1234,
            runner_command="python run_infertutor_experiment.py --label smoke",
            app_name="infertutor-smoke",
            git_commit="abc123",
            git_branch="main",
            git_dirty=False,
            api_key="secret-key",
        )
        stats = load_test.Stats(started_at=1.0)
        payload = load_test.build_result_payload(args, stats, {"text": 1.0})
        self.assertNotIn("url", payload["config"])
        self.assertNotIn("api_key", payload["config"])
        self.assertEqual(
            payload["config"]["endpoint_url_redacted"], "https://***.modal.run"
        )

    def test_build_result_payload_includes_smoke_check(self):
        args = argparse.Namespace(
            url="https://bitlabs27--infertutor-smoke-serve.modal.run",
            model="Qwen/Qwen3-VL-4B-Instruct",
            mode="text",
            users=5,
            duration=30,
            ramp_up=5,
            max_tokens=64,
            request_timeout=180,
            min_pause=0.2,
            max_pause=1.2,
            label="smoke",
            total_gpus=1,
            seed=1234,
            runner_command="python run_infertutor_experiment.py --label smoke",
            app_name="infertutor-smoke",
            git_commit="abc123",
            git_branch="main",
            git_dirty=False,
            smoke_ok=True,
            smoke_status_code=200,
            smoke_latency_ms=123.4,
            smoke_response_excerpt="ready",
        )
        stats = load_test.Stats(started_at=1.0)
        payload = load_test.build_result_payload(args, stats, {"text": 1.0})
        self.assertEqual(payload["smoke_check"]["status_code"], 200)
        self.assertTrue(payload["smoke_check"]["ok"])
        self.assertEqual(payload["smoke_check"]["response_excerpt"], "ready")

    def _run_async(self, coro):
        import asyncio

        return asyncio.run(coro)


class ModalAppTests(unittest.TestCase):
    def test_build_vllm_command_requires_endpoint_api_key(self):
        try:
            modal_app = importlib.import_module("starter_code.modal_infertutor_app")
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        with mock.patch.dict(
            "starter_code.modal_infertutor_app.os.environ",
            {"ENDPOINT_API_KEY": ""},
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                modal_app.build_vllm_command()

    def test_build_vllm_command_includes_api_key(self):
        try:
            modal_app = importlib.import_module("starter_code.modal_infertutor_app")
        except ModuleNotFoundError as exc:
            self.skipTest(str(exc))
        with mock.patch.dict(
            "starter_code.modal_infertutor_app.os.environ",
            {"ENDPOINT_API_KEY": "secret-key"},
            clear=False,
        ):
            with mock.patch("starter_code.modal_infertutor_app.MODEL_NAME", "Qwen/Qwen3-VL-4B-Instruct"):
                cmd = modal_app.build_vllm_command()
        self.assertIn("--api-key", cmd)
        self.assertIn("secret-key", cmd)

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

    def test_validate_result_data_rejects_non_boolean_smoke_ok(self):
        with self.assertRaises(ValueError):
            result_schema.validate_result_data(
                {
                    "config": {"users": 10, "total_gpus": 1},
                    "results": {"error_rate": 0.0},
                    "smoke_check": {"ok": "yes", "status_code": 200},
                }
            )


class SubmissionArtifactTests(unittest.TestCase):
    @staticmethod
    def make_result(
        *,
        label: str,
        users: int = 10,
        throughput: float = 200.0,
        include_commentary: bool = True,
        include_provenance: bool = True,
    ) -> dict:
        sample = {
            "schema_version": 2,
            "config": {"mode": "text", "users": users, "total_gpus": 1},
            "results": {
                "error_rate": 0.1,
                "ttft_p95_ms": 1000.0,
                "itl_p95_ms": 50.0,
                "aggregate_stream_chunks_per_s": throughput,
                "requests_per_s": 5.0,
            },
        }
        if include_provenance:
            sample["provenance"] = {
                "runner_command": f"python3 run_infertutor_experiment.py --label {label}",
                "app_name": f"infertutor-{label}",
                "source_control": {
                    "commit": f"{label}123",
                    "branch": "main",
                    "is_dirty": False,
                },
            }
        if include_commentary:
            sample["submission_commentary"] = {
                "best_optimization": "Enabled prefix caching for the repeated tutor system prompt.",
                "surprising_failure_or_tradeoff": "Higher batch tokens improved throughput but degraded TTFT at low concurrency.",
                "next_step": "Benchmark multimodal runs with a wider replica sweep.",
            }
        return sample

    def test_render_experiment_table_and_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for index in range(5):
                result_path = Path(tmpdir) / f"demo-{index}.json"
                sample = self.make_result(
                    label=f"demo-{index}",
                    users=10 + index,
                    throughput=200.0 + index,
                )
                result_path.write_text(json.dumps(sample), encoding="utf-8")
            rows = submission.load_ranked_results(Path(tmpdir))
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
            self.assertIn("Which optimization helped the most", report)
            self.assertNotIn("TODO", report)
            manifest_text = (bundle_dir / "submission_manifest.json").read_text(
                encoding="utf-8"
            )
            self.assertIn('"submission_ready": true', manifest_text)

    def test_write_bundle_rejects_less_than_five_experiments_without_draft_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = Path(tmpdir) / "demo.json"
            result_path.write_text(
                json.dumps(self.make_result(label="demo")), encoding="utf-8"
            )
            rows = submission.load_ranked_results(result_path)
            with self.assertRaises(ValueError):
                submission.write_bundle(rows, Path(tmpdir) / "bundle")

    def test_write_bundle_allows_draft_mode_with_incomplete_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result_path = Path(tmpdir) / "demo.json"
            result_path.write_text(
                json.dumps(self.make_result(label="demo", include_commentary=False)),
                encoding="utf-8",
            )
            rows = submission.load_ranked_results(result_path)
            manifest = submission.write_bundle(
                rows, Path(tmpdir) / "bundle", allow_draft=True
            )
            self.assertFalse(manifest["submission_ready"])
            report = (Path(tmpdir) / "bundle" / "engineering_report.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("TODO", report)

    def test_write_bundle_rejects_missing_submission_commentary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for index in range(5):
                result_path = Path(tmpdir) / f"demo-{index}.json"
                result_path.write_text(
                    json.dumps(
                        self.make_result(
                            label=f"demo-{index}",
                            include_commentary=index != 4,
                        )
                    ),
                    encoding="utf-8",
                )
            rows = submission.load_ranked_results(Path(tmpdir))
            with self.assertRaises(ValueError):
                submission.write_bundle(
                    rows, Path(tmpdir) / "bundle", final_index=4
                )

    def test_write_bundle_rejects_missing_final_run_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for index in range(5):
                result_path = Path(tmpdir) / f"demo-{index}.json"
                result_path.write_text(
                    json.dumps(
                        self.make_result(
                            label=f"demo-{index}",
                            throughput=500.0 if index == 4 else 200.0 + index,
                            include_provenance=index != 4,
                        )
                    ),
                    encoding="utf-8",
                )
            rows = submission.load_ranked_results(Path(tmpdir))
            with self.assertRaises(ValueError):
                submission.write_bundle(rows, Path(tmpdir) / "bundle")

    def test_validate_result_data_rejects_blank_submission_commentary_field(self):
        with self.assertRaises(ValueError):
            result_schema.validate_result_data(
                {
                    "config": {"users": 10, "total_gpus": 1},
                    "results": {"error_rate": 0.0},
                    "submission_commentary": {
                        "best_optimization": "",
                        "surprising_failure_or_tradeoff": "tradeoff",
                        "next_step": "next",
                    },
                }
            )

    def test_load_submission_commentary_file_merges_structured_commentary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            commentary_path = Path(tmpdir) / "commentary.json"
            commentary_path.write_text(
                json.dumps(
                    {
                        "best_optimization": "Kept prefix caching on.",
                        "surprising_failure_or_tradeoff": "Replica scaling hit startup overhead.",
                        "next_step": "Run the multimodal track with the same config.",
                    }
                ),
                encoding="utf-8",
            )
            merged = submission.load_submission_commentary_file(commentary_path)
            self.assertEqual(merged["best_optimization"], "Kept prefix caching on.")

    def test_resolve_final_index_selects_requested_filename(self):
        rows = [
            (10.0, Path("first.json"), {}),
            (20.0, Path("second.json"), {}),
        ]
        self.assertEqual(submission.resolve_final_index(rows, "second.json"), 1)

    def test_resolve_final_index_rejects_unknown_filename(self):
        rows = [(10.0, Path("first.json"), {})]
        with self.assertRaises(SystemExit):
            submission.resolve_final_index(rows, "missing.json")


class PreflightTests(unittest.TestCase):
    def test_check_python_version_accepts_supported_version(self):
        with mock.patch.object(preflight.sys, "version_info", (3, 11, 8)):
            result = preflight.check_python_version()
        self.assertTrue(result.ok)

    def test_check_python_version_rejects_older_version(self):
        with mock.patch.object(preflight.sys, "version_info", (3, 10, 14)):
            result = preflight.check_python_version()
        self.assertFalse(result.ok)
        self.assertIn("requires Python 3.11+", result.detail)

    @mock.patch.dict("starter_code.preflight_infertutor.os.environ", {}, clear=True)
    def test_check_endpoint_api_key_reports_missing_required_secret(self):
        result = preflight.check_endpoint_api_key(required=True)
        self.assertFalse(result.ok)
        self.assertTrue(result.required)
        self.assertIn("ENDPOINT_API_KEY", result.detail)

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

    def test_check_required_modules_reports_install_hint_for_missing_module(self):
        def fake_find_spec(name: str):
            if name == "modal":
                return None
            return object()

        with mock.patch(
            "starter_code.preflight_infertutor.importlib.util.find_spec",
            side_effect=fake_find_spec,
        ):
            results = preflight.check_required_modules()
        modal_result = [result for result in results if result.name == "module:modal"][0]
        self.assertFalse(modal_result.ok)
        self.assertIn("requirements.txt", modal_result.detail)

    @mock.patch("starter_code.preflight_infertutor.resolve_command_path", return_value=None)
    def test_check_modal_auth_reports_install_hint_when_cli_missing(self, _mock_resolve):
        result = preflight.check_modal_auth(required=True)
        self.assertFalse(result.ok)
        self.assertTrue(result.required)
        self.assertIn("Install the Modal CLI", result.detail)

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

    @mock.patch("starter_code.bootstrap_infertutor_env.run_modal_command")
    def test_ensure_endpoint_auth_secret_creates_secret(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
        self.assertTrue(
            bootstrap.ensure_endpoint_auth_secret(
                "secret-key", "infertutor-auth", False
            )
        )


class RepoHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.hygiene = load_module_from_path(
            "check_repo_hygiene", root / "scripts" / "check_repo_hygiene.py"
        )

    def test_dependency_pin_check_rejects_unpinned_requirement(self):
        with self.assertRaises(ValueError):
            self.hygiene.check_requirements_are_pinned(
                ["modal>=1.4.0", "httpx==0.28.1"]
            )

    def test_modal_url_check_rejects_raw_modal_hostname(self):
        with self.assertRaises(ValueError):
            self.hygiene.check_for_raw_modal_urls(
                {"README.md": "https://bitlabs27--infertutor.modal.run"}
            )

    def test_tracked_artifact_check_rejects_generated_results(self):
        with self.assertRaises(ValueError):
            self.hygiene.check_for_tracked_generated_artifacts(
                ["starter_code/results_infertutor/demo.json"]
            )

    def test_shell_true_check_rejects_unsafe_subprocess_usage(self):
        with self.assertRaises(ValueError):
            self.hygiene.check_python_files_for_shell_true(
                {"app.py": "import subprocess\nsubprocess.run('ls', shell=True)\n"}
            )

    def test_required_doc_language_check_rejects_missing_score_scope_notice(self):
        with self.assertRaises(ValueError):
            self.hygiene.check_required_doc_language(
                {
                    "README.md": "quality_pass_rate only",
                    "InferTutor_Arena_Capstone.md": "quality_pass_rate only",
                }
            )


if __name__ == "__main__":
    unittest.main()
