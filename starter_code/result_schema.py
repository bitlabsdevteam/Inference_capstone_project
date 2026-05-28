"""Shared validation and scoring utilities for InferTutor result files."""

from __future__ import annotations

import json
from pathlib import Path


def _require_mapping(value, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"'{field_name}' must be a JSON object.")
    return value


def _require_number(value, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"'{field_name}' must be a number.")
    return float(value)


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
        _require_mapping(provenance, "provenance")

    workload_mix = data.get("workload_mix")
    if workload_mix is not None:
        _require_mapping(workload_mix, "workload_mix")

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
    }
