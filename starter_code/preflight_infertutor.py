"""Run local environment and repository preflight checks for InferTutor."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).parent
REQUIREMENTS_PATH = ROOT / "requirements.txt"
REQUIRED_FILES = [
    ROOT / "modal_infertutor_app.py",
    ROOT / "run_infertutor_experiment.py",
    ROOT / "load_test_infertutor.py",
    ROOT / "score_infertutor.py",
    ROOT / "prompts.json",
    ROOT / "requirements.txt",
]
REQUIRED_MODULES = ["modal", "httpx", "rich"]
REQUIRED_PROMPT_KEYS = {"system_prompt", "text", "long", "image"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


def resolve_command_path(name: str) -> str | None:
    """Resolve a command from PATH, falling back to the active Python bin directory."""

    path = shutil.which(name)
    if path:
        return path
    python_bin_dir = Path(sys.executable).parent
    candidate = python_bin_dir / name
    if candidate.exists() and candidate.is_file():
        return str(candidate)
    return None


def check_python_version() -> CheckResult:
    version_info = sys.version_info
    major = getattr(version_info, "major", version_info[0])
    minor = getattr(version_info, "minor", version_info[1])
    micro = getattr(version_info, "micro", version_info[2])
    ok = (major, minor) >= (3, 11)
    detail = f"{major}.{minor}.{micro}"
    if not ok:
        detail += " (requires Python 3.11+)"
    return CheckResult(name="python_version", ok=ok, detail=detail)


def check_required_files() -> list[CheckResult]:
    results = []
    for path in REQUIRED_FILES:
        results.append(
            CheckResult(
                name=f"file:{path.name}",
                ok=path.exists(),
                detail=str(path),
            )
        )
    return results


def check_required_modules() -> list[CheckResult]:
    results = []
    for module_name in REQUIRED_MODULES:
        ok = importlib.util.find_spec(module_name) is not None
        if ok:
            detail = "importable"
        else:
            detail = (
                "not importable; install pinned dependencies from "
                f"{REQUIREMENTS_PATH}"
            )
        results.append(CheckResult(name=f"module:{module_name}", ok=ok, detail=detail))
    return results


def check_command(name: str, *, required: bool) -> CheckResult:
    path = resolve_command_path(name)
    detail = path or "not found"
    return CheckResult(
        name=f"command:{name}",
        ok=path is not None,
        detail=detail,
        required=required,
    )


def check_modal_auth(*, required: bool = False) -> CheckResult:
    """Check whether the Modal CLI is installed and authenticated."""

    modal_path = resolve_command_path("modal")
    if not modal_path:
        return CheckResult(
            name="modal_auth",
            ok=False,
            detail=(
                "modal CLI not found. Install the Modal CLI in the active "
                "environment and rerun preflight."
            ),
            required=required,
        )
    proc = subprocess.run(
        [modal_path, "token", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        detail = proc.stdout.strip() or "authenticated"
        return CheckResult(name="modal_auth", ok=True, detail=detail, required=required)

    detail = proc.stderr.strip() or proc.stdout.strip() or "not authenticated"
    return CheckResult(name="modal_auth", ok=False, detail=detail, required=required)


def check_prompts_schema() -> CheckResult:
    prompts_path = ROOT / "prompts.json"
    if not prompts_path.exists():
        return CheckResult(
            name="prompts_schema",
            ok=False,
            detail="prompts.json not found",
        )
    try:
        data = json.loads(prompts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(name="prompts_schema", ok=False, detail=str(exc))

    missing = sorted(REQUIRED_PROMPT_KEYS - set(data))
    if missing:
        return CheckResult(
            name="prompts_schema",
            ok=False,
            detail=f"missing keys: {', '.join(missing)}",
        )

    list_fields = [field for field in ("text", "long", "image") if not isinstance(data.get(field), list) or not data[field]]
    if list_fields:
        return CheckResult(
            name="prompts_schema",
            ok=False,
            detail=f"expected non-empty prompt lists for: {', '.join(list_fields)}",
        )
    if not isinstance(data.get("system_prompt"), str) or not data["system_prompt"].strip():
        return CheckResult(
            name="prompts_schema",
            ok=False,
            detail="system_prompt must be a non-empty string",
        )
    return CheckResult(name="prompts_schema", ok=True, detail="ok")


def check_endpoint_api_key(*, required: bool = False) -> CheckResult:
    api_key = os.environ.get("ENDPOINT_API_KEY", "").strip()
    if api_key:
        return CheckResult(
            name="endpoint_api_key",
            ok=True,
            detail="configured via ENDPOINT_API_KEY",
            required=required,
        )
    return CheckResult(
        name="endpoint_api_key",
        ok=False,
        detail=(
            "ENDPOINT_API_KEY not set. Export ENDPOINT_API_KEY locally and create "
            "the 'infertutor-auth' Modal secret before running authenticated benchmarks."
        ),
        required=required,
    )


def run_preflight(
    *, require_modal_auth: bool = False, require_endpoint_auth: bool = False
) -> list[CheckResult]:
    results = [check_python_version(), check_prompts_schema()]
    results.extend(check_required_files())
    results.extend(check_required_modules())
    results.append(check_command("git", required=False))
    results.append(check_command("modal", required=False))
    results.append(check_modal_auth(required=require_modal_auth))
    results.append(check_endpoint_api_key(required=require_endpoint_auth))
    return results


def summarize(results: list[CheckResult]) -> dict:
    required_failures = [result for result in results if result.required and not result.ok]
    optional_failures = [result for result in results if not result.required and not result.ok]
    return {
        "ok": not required_failures,
        "required_failures": len(required_failures),
        "optional_failures": len(optional_failures),
        "checks": [asdict(result) for result in results],
    }


def print_text_report(results: list[CheckResult]) -> None:
    summary = summarize(results)
    for result in results:
        marker = "PASS" if result.ok else ("WARN" if not result.required else "FAIL")
        print(f"[{marker}] {result.name}: {result.detail}")
    print()
    print(
        "Summary: ok={ok} required_failures={required_failures} optional_failures={optional_failures}".format(
            **summary
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run InferTutor local preflight checks.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument(
        "--require-modal-auth",
        action="store_true",
        help="Fail the preflight if Modal CLI authentication is missing",
    )
    parser.add_argument(
        "--require-endpoint-auth",
        action="store_true",
        help="Fail the preflight if ENDPOINT_API_KEY is missing locally.",
    )
    args = parser.parse_args()

    results = run_preflight(
        require_modal_auth=args.require_modal_auth,
        require_endpoint_auth=args.require_endpoint_auth,
    )
    summary = summarize(results)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_text_report(results)

    raise SystemExit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
