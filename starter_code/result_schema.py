"""Shared validation and scoring utilities for InferTutor result files."""

from __future__ import annotations

import json
from pathlib import Path


SUBMISSION_COMMENTARY_FIELDS = (
    "best_optimization",
    "surprising_failure_or_tradeoff",
    "next_step",
)


def _require_mapping(value, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"'{field_name}' must be a JSON object.")
    return value


def _require_number(value, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"'{field_name}' must be a number.")
    return float(value)


def _require_non_empty_string(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field_name}' must be a non-empty string.")
    return value.strip()


def validate_result_data(data: dict) -> dict:
    """Validate the minimum schema expected by scorer and reporting tools."""

    if not isinstance(data, dict):
        raise ValueError("Result file must contain a JSON object.")

    if "config" not in data or "results" not in data:
        raise ValueError("Result file must contain 'config' and 'results' keys.")

    config = _require_mapping(data["config"], "config")
    results = _require_mapping(data["results"], "results")

    if "schema_version" in data and not isinstance(data["schema_version"], int):
        raise ValueError("'schema_version' must be an integer when present.")

    if "users" in config:
        users = _require_number(config["users"], "config.users")
        if users <= 0:
            raise ValueError("'config.users' must be > 0.")
    if "total_gpus" in config:
        total_gpus = _require_number(config["total_gpus"], "config.total_gpus")
        if total_gpus <= 0:
            raise ValueError("'config.total_gpus' must be > 0.")

    numeric_result_fields = [
        "error_rate",
        "ttft_p95_ms",
        "itl_p95_ms",
        "aggregate_stream_chunks_per_s",
        "requests_per_s",
    ]
    for field_name in numeric_result_fields:
        if field_name in results:
            _require_number(results[field_name], f"results.{field_name}")

    provenance = data.get("provenance")
    if provenance is not None:
        provenance = _require_mapping(provenance, "provenance")
        source_control = provenance.get("source_control")
        if source_control is not None:
            source_control = _require_mapping(
                source_control, "provenance.source_control"
            )
            if "is_dirty" in source_control and not isinstance(
                source_control["is_dirty"], bool
            ):
                raise ValueError(
                    "'provenance.source_control.is_dirty' must be a boolean."
                )

    workload_mix = data.get("workload_mix")
    if workload_mix is not None:
        _require_mapping(workload_mix, "workload_mix")

    smoke_check = data.get("smoke_check")
    if smoke_check is not None:
        smoke_check = _require_mapping(smoke_check, "smoke_check")
        if not isinstance(smoke_check.get("ok"), bool):
            raise ValueError("'smoke_check.ok' must be a boolean.")
        if "status_code" in smoke_check:
            _require_number(smoke_check["status_code"], "smoke_check.status_code")
        if "latency_ms" in smoke_check:
            _require_number(smoke_check["latency_ms"], "smoke_check.latency_ms")
        if "response_excerpt" in smoke_check and not isinstance(
            smoke_check["response_excerpt"], str
        ):
            raise ValueError("'smoke_check.response_excerpt' must be a string.")

    submission_commentary = data.get("submission_commentary")
    if submission_commentary is not None:
        submission_commentary = _require_mapping(
            submission_commentary, "submission_commentary"
        )
        for field_name in SUBMISSION_COMMENTARY_FIELDS:
            if field_name not in submission_commentary:
                raise ValueError(
                    f"'submission_commentary.{field_name}' is required when "
                    "'submission_commentary' is present."
                )
            _require_non_empty_string(
                submission_commentary[field_name],
                f"submission_commentary.{field_name}",
            )

    return data


def load_result(path: Path) -> dict:
    """Read and validate one result JSON file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_result_data(data)


def score_result(data: dict) -> float:
    """Compute the local leaderboard score for one validated result."""

    config = data["config"]
    result = data["results"]
    users = max(float(config.get("users", 1)), 1.0)
    total_gpus = max(float(config.get("total_gpus", 1)), 1.0)
    error_rate = min(max(float(result.get("error_rate", 1)), 0.0), 1.0)
    goodput = float(result.get("aggregate_stream_chunks_per_s", 0)) * (1 - error_rate)
    ttft = max(float(result.get("ttft_p95_ms", 1)) / 1000, 0.001)
    itl = max(float(result.get("itl_p95_ms", 1)) / 1000, 0.001)
    return goodput * users / (ttft * itl * total_gpus)


def result_row(data: dict) -> dict[str, float | str]:
    """Extract a normalized summary row from one validated result."""

    config = data["config"]
    results = data["results"]
    return {
        "mode": str(config.get("mode", "")),
        "users": float(config.get("users", 0)),
        "gpus": float(config.get("total_gpus", 0)),
        "error_rate": float(results.get("error_rate", 0.0)),
        "ttft_p95_ms": float(results.get("ttft_p95_ms", 0.0)),
        "itl_p95_ms": float(results.get("itl_p95_ms", 0.0)),
        "throughput": float(results.get("aggregate_stream_chunks_per_s", 0.0)),
        "requests_per_s": float(results.get("requests_per_s", 0.0)),
        "score": score_result(data),
        "smoke_ok": data.get("smoke_check", {}).get("ok", False),
        "last_error": str(results.get("last_error", "")),
    }


def require_submission_provenance(data: dict) -> dict:
    """Require the provenance fields needed for a final submission bundle."""

    provenance = _require_mapping(data.get("provenance"), "provenance")
    _require_non_empty_string(
        provenance.get("runner_command", ""), "provenance.runner_command"
    )
    _require_non_empty_string(provenance.get("app_name", ""), "provenance.app_name")
    source_control = _require_mapping(
        provenance.get("source_control"), "provenance.source_control"
    )
    _require_non_empty_string(
        source_control.get("commit", ""), "provenance.source_control.commit"
    )
    _require_non_empty_string(
        source_control.get("branch", ""), "provenance.source_control.branch"
    )
    if not isinstance(source_control.get("is_dirty"), bool):
        raise ValueError("'provenance.source_control.is_dirty' must be a boolean.")
    return provenance
