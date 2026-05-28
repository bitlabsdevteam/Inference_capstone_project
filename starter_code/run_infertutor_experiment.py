"""
One-command experiment runner for InferTutor Arena.

This script:
1. Copies modal_infertutor_app.py.
2. Patches the serving constants based on CLI flags.
3. Deploys the Modal app.
4. Waits for /health.
5. Runs the load tester.

Students should vary the CLI flags, not rewrite deployment code.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel


console = Console()
ROOT = Path(__file__).parent
TEMPLATE = ROOT / "modal_infertutor_app.py"
GENERATED = ROOT / "modal_infertutor_app_generated.py"
APP_NAME_PREFIX = "infertutor-"


def sanitize_label(label: str) -> str:
    """Convert a user-provided label into a Modal-safe app suffix."""

    sanitized = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")
    if not sanitized:
        raise ValueError("Label must contain at least one alphanumeric character.")
    return sanitized[:48]


def validate_args(args) -> None:
    """Fail fast on invalid experiment settings before deployment."""

    positive_int_fields = [
        ("tp", args.tp),
        ("replicas", args.replicas),
        ("max_model_len", args.max_model_len),
        ("max_batch_tokens", args.max_batch_tokens),
        ("max_seqs", args.max_seqs),
        ("concurrent_inputs", args.concurrent_inputs),
        ("mm_max_pixels", args.mm_max_pixels),
        ("users", args.users),
        ("duration", args.duration),
        ("max_tokens", args.max_tokens),
        ("request_timeout", args.request_timeout),
        ("health_timeout", args.health_timeout),
    ]
    if args.gpu_count is not None:
        positive_int_fields.append(("gpu_count", args.gpu_count))
    if args.ramp_up < 0:
        raise ValueError("--ramp-up must be >= 0.")
    if args.seed < 0:
        raise ValueError("--seed must be >= 0.")
    if args.min_pause < 0 or args.max_pause < 0:
        raise ValueError("--min-pause and --max-pause must be >= 0.")
    if args.min_pause > args.max_pause:
        raise ValueError("--min-pause cannot be greater than --max-pause.")
    for field_name, value in positive_int_fields:
        if value <= 0:
            raise ValueError(f"--{field_name.replace('_', '-')} must be > 0.")


def replace_once(source: str, old: str, new: str) -> str:
    """Replace an expected template line exactly once."""

    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected to replace template snippet exactly once, found {count}: {old}"
        )
    return source.replace(old, new, 1)


def ensure_command_available(command_name: str) -> None:
    """Fail with an actionable message when a required CLI is missing."""

    if shutil.which(command_name):
        return
    raise SystemExit(
        f"Required command not found: {command_name}. Install it before deploying, "
        f"or pass --url to reuse an existing endpoint."
    )


def run_command_capture(cmd: list[str]) -> str:
    """Run a small local command and return stripped stdout when it succeeds."""

    proc = subprocess.run(
        cmd,
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def collect_git_metadata() -> dict[str, str | bool]:
    """Capture source-control metadata for experiment provenance."""

    commit = run_command_capture(["git", "rev-parse", "HEAD"])
    branch = run_command_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = run_command_capture(["git", "status", "--short"])
    metadata: dict[str, str | bool] = {}
    if commit:
        metadata["commit"] = commit
    if branch:
        metadata["branch"] = branch
    if commit or branch:
        metadata["is_dirty"] = bool(dirty)
    return metadata


def patch_modal_app(args) -> Path:
    """Create a per-experiment Modal app file with static config values."""

    source = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        'MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-VL-4B-Instruct")': f'MODEL_NAME = "{args.model}"',
        'TENSOR_PARALLEL = int(os.environ.get("TENSOR_PARALLEL", "1"))': f"TENSOR_PARALLEL = {args.tp}",
        'GPU_TYPE = os.environ.get("GPU_TYPE", "H100")': f'GPU_TYPE = "{args.gpu_type}"',
        'GPU_COUNT = int(os.environ.get("GPU_COUNT", str(TENSOR_PARALLEL)))': f"GPU_COUNT = {args.gpu_count or args.tp}",
        'DTYPE = os.environ.get("DTYPE", "bfloat16")': f'DTYPE = "{args.dtype}"',
        'ENABLE_PREFIX_CACHING = os.environ.get("ENABLE_PREFIX_CACHING", "true").lower() == "true"': f"ENABLE_PREFIX_CACHING = {args.prefix_cache}",
        'ENABLE_CHUNKED_PREFILL = os.environ.get("ENABLE_CHUNKED_PREFILL", "true").lower() == "true"': f"ENABLE_CHUNKED_PREFILL = {args.chunked_prefill}",
        'MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "8192"))': f"MAX_MODEL_LEN = {args.max_model_len}",
        'MAX_NUM_BATCHED_TOKENS = int(os.environ.get("MAX_NUM_BATCHED_TOKENS", "4096"))': f"MAX_NUM_BATCHED_TOKENS = {args.max_batch_tokens}",
        'MAX_NUM_SEQS = int(os.environ.get("MAX_NUM_SEQS", "32"))': f"MAX_NUM_SEQS = {args.max_seqs}",
        'CONCURRENT_INPUTS = int(os.environ.get("CONCURRENT_INPUTS", "64"))': f"CONCURRENT_INPUTS = {args.concurrent_inputs}",
        'MIN_CONTAINERS = int(os.environ.get("MIN_CONTAINERS", "1"))': f"MIN_CONTAINERS = {args.replicas}",
        'MAX_CONTAINERS = int(os.environ.get("MAX_CONTAINERS", "1"))': f"MAX_CONTAINERS = {args.replicas}",
        'FAST_BOOT = os.environ.get("FAST_BOOT", "true").lower() == "true"': f"FAST_BOOT = {args.fast_boot}",
        'MM_MAX_PIXELS = int(os.environ.get("MM_MAX_PIXELS", str(512 * 28 * 28)))': f"MM_MAX_PIXELS = {args.mm_max_pixels}",
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)

    app_name = f"{APP_NAME_PREFIX}{sanitize_label(args.label)}"
    source = replace_once(
        source,
        'app = modal.App("infertutor-arena")',
        f'app = modal.App("{app_name}")',
    )
    GENERATED.write_text(source, encoding="utf-8")
    return GENERATED


def deploy(app_path: Path) -> str:
    """Deploy to Modal and return the web endpoint."""

    proc = subprocess.run(
        ["modal", "deploy", str(app_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    console.print(proc.stdout)
    if proc.returncode != 0:
        console.print(proc.stderr, style="red")
        raise SystemExit(proc.returncode)

    # Modal sometimes wraps long URLs in terminal output. Remove whitespace before parsing.
    normalized = re.sub(r"\s+", "", proc.stdout)
    match = re.search(r"https://[^\"'<>]+?modal\.run", normalized)
    if not match:
        raise RuntimeError("Could not find Modal endpoint in deploy output")
    return match.group(0)


def wait_for_health(url: str, timeout_s: int = 900):
    """Wait until vLLM reports healthy."""

    console.print(f"[bold]Waiting for vLLM health:[/bold] {url}/health")
    deadline = time.time() + timeout_s
    last_error = ""
    with httpx.Client(timeout=20) as client:
        while time.time() < deadline:
            try:
                resp = client.get(f"{url.rstrip('/')}/health")
                if resp.status_code == 200:
                    console.print("[green]Endpoint is healthy[/green]")
                    return
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
            except Exception as exc:
                last_error = str(exc)
            time.sleep(10)
    raise TimeoutError(f"Endpoint did not become healthy: {last_error}")


def run_load_test(url: str, args):
    """Run the fixed prompt workload against the deployed endpoint."""

    runner_command = shlex.join(
        [Path(sys.executable).name, Path(__file__).name, *sys.argv[1:]]
    )
    app_name = f"{APP_NAME_PREFIX}{sanitize_label(args.label)}"
    git_metadata = collect_git_metadata()
    cmd = [
        sys.executable,
        str(ROOT / "load_test_infertutor.py"),
        "--url",
        url,
        "--model",
        args.model,
        "--mode",
        args.mode,
        "--users",
        str(args.users),
        "--duration",
        str(args.duration),
        "--ramp-up",
        str(args.ramp_up),
        "--max-tokens",
        str(args.max_tokens),
        "--request-timeout",
        str(args.request_timeout),
        "--min-pause",
        str(args.min_pause),
        "--max-pause",
        str(args.max_pause),
        "--seed",
        str(args.seed),
        "--runner-command",
        runner_command,
        "--app-name",
        app_name,
        "--git-commit",
        str(git_metadata.get("commit", "")),
        "--git-branch",
        str(git_metadata.get("branch", "")),
        "--git-dirty",
        "true" if git_metadata.get("is_dirty") else "false",
        "--label",
        args.label,
        "--total-gpus",
        str((args.gpu_count or args.tp) * args.replicas),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description="Deploy and benchmark InferTutor")
    parser.add_argument("--label", required=True, help="Short name for this experiment")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct")
    parser.add_argument("--gpu-type", default="H100", choices=["H100", "H200", "A100", "L40S"])
    parser.add_argument("--gpu-count", type=int, default=None)
    parser.add_argument("--tp", type=int, default=1)
    parser.add_argument("--replicas", type=int, default=1)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--prefix-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--chunked-prefill", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fast-boot", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument("--max-batch-tokens", type=int, default=4096)
    parser.add_argument("--max-seqs", type=int, default=32)
    parser.add_argument("--concurrent-inputs", type=int, default=64)
    parser.add_argument("--mm-max-pixels", type=int, default=512 * 28 * 28)
    parser.add_argument("--mode", choices=["text", "long", "image", "mixed"], default="mixed")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--ramp-up", type=int, default=15)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--min-pause", type=float, default=0.2)
    parser.add_argument("--max-pause", type=float, default=1.2)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--health-timeout", type=int, default=900)
    parser.add_argument("--url", default=None, help="Reuse an existing endpoint instead of deploying")
    parser.add_argument("--deploy-only", action="store_true")
    args = parser.parse_args()
    validate_args(args)

    total_gpus = (args.gpu_count or args.tp) * args.replicas
    console.print(Panel(json.dumps(vars(args) | {"total_gpus": total_gpus}, indent=2), title="InferTutor Experiment"))

    if total_gpus > 8:
        raise SystemExit("This starter runner caps experiments at 8 GPUs.")

    if not args.url:
        ensure_command_available("modal")
    url = args.url or deploy(patch_modal_app(args))
    wait_for_health(url, timeout_s=args.health_timeout)
    if not args.deploy_only:
        run_load_test(url, args)


if __name__ == "__main__":
    main()
