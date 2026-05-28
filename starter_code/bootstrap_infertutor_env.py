"""Bootstrap Modal auth and required secrets for InferTutor."""

from __future__ import annotations

import argparse
import os
import subprocess

try:
    from .preflight_infertutor import check_modal_auth, resolve_command_path
except ImportError:
    from preflight_infertutor import check_modal_auth, resolve_command_path


def run_modal_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a Modal CLI command and capture its output."""

    modal_path = resolve_command_path("modal")
    if not modal_path:
        raise RuntimeError("Modal CLI not found. Install dependencies or activate the project venv.")
    return subprocess.run(
        [modal_path, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def ensure_modal_auth(token_id: str | None, token_secret: str | None) -> bool:
    """Authenticate Modal when credentials are available, or verify existing auth."""

    auth_check = check_modal_auth(required=True)
    if auth_check.ok:
        return True

    if not token_id or not token_secret:
        print(auth_check.detail)
        return False

    proc = run_modal_command(
        ["token", "set", "--token-id", token_id, "--token-secret", token_secret]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Failed to set Modal token.")
    return True


def ensure_hf_secret(hf_token: str | None, secret_name: str, skip_secret: bool) -> bool:
    """Create the Hugging Face secret when a token is available."""

    if skip_secret:
        return True

    if not hf_token:
        print("HF_TOKEN not provided. Skipping Hugging Face secret creation.")
        return False

    proc = run_modal_command(["secret", "create", secret_name, f"HF_TOKEN={hf_token}"])
    if proc.returncode == 0:
        return True

    detail = proc.stderr.strip() or proc.stdout.strip()
    if "already exists" in detail.lower():
        print(f"Secret '{secret_name}' already exists.")
        return True
    raise RuntimeError(detail or "Failed to create Hugging Face secret.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Modal auth and secrets for InferTutor.")
    parser.add_argument("--token-id", default=os.environ.get("MODAL_TOKEN_ID", ""))
    parser.add_argument("--token-secret", default=os.environ.get("MODAL_TOKEN_SECRET", ""))
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--secret-name", default="huggingface")
    parser.add_argument("--skip-secret", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    if args.check_only:
        auth_check = check_modal_auth(required=True)
        print(auth_check.detail)
        raise SystemExit(0 if auth_check.ok else 1)

    if not ensure_modal_auth(args.token_id or None, args.token_secret or None):
        raise SystemExit(1)

    ensure_hf_secret(args.hf_token or None, args.secret_name, args.skip_secret)
    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
