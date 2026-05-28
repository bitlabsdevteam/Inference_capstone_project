"""Generate submission-ready artifacts from InferTutor result JSON files."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from .result_schema import load_result, result_row, score_result
except ImportError:
    from result_schema import load_result, result_row, score_result


def load_ranked_results(path: Path) -> list[tuple[float, Path, dict]]:
    """Load and score one result file or all result files in a directory."""

    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    rows = []
    for file in files:
        data = load_result(file)
        rows.append((score_result(data), file, data))
    rows.sort(reverse=True, key=lambda row: row[0])
    return rows


def format_percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def infer_track(mode: str) -> str:
    if mode == "mixed":
        return "Multimodal Product Track"
    if mode == "text":
        return "Text Speed Track"
    return f"Custom {mode.title()} Track"


def render_experiment_table(rows: list[tuple[float, Path, dict]]) -> str:
    """Render the experiment matrix as Markdown."""

    lines = [
        "| file | mode | users | gpus | err% | TTFT p95 | ITL p95 | throughput | req/s | score |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for value, file, data in rows:
        row = result_row(data)
        lines.append(
            "| {file} | {mode} | {users} | {gpus} | {err:.1f} | {ttft:.1f} ms | {itl:.1f} ms | {throughput:.1f} | {rps:.2f} | {score:.0f} |".format(
                file=file.name,
                mode=row["mode"],
                users=int(row["users"]),
                gpus=int(row["gpus"]),
                err=100 * row["error_rate"],
                ttft=row["ttft_p95_ms"],
                itl=row["itl_p95_ms"],
                throughput=row["throughput"],
                rps=row["requests_per_s"],
                score=row["score"],
            )
        )
    return "\n".join(lines) + "\n"


def build_report(
    final_score: float,
    final_file: Path,
    final_data: dict,
    rows: list[tuple[float, Path, dict]],
) -> str:
    """Render a submission-ready engineering report template."""

    config = final_data["config"]
    results = final_data["results"]
    provenance = final_data.get("provenance", {})
    source_control = provenance.get("source_control", {})
    runner_command = (
        provenance.get("runner_command") or "TODO: record the exact final command"
    )
    best_ttft = min(
        row[2]["results"].get("ttft_p95_ms", float("inf")) for row in rows
    )
    best_itl = min(
        row[2]["results"].get("itl_p95_ms", float("inf")) for row in rows
    )
    best_throughput = max(
        row[2]["results"].get("aggregate_stream_chunks_per_s", 0.0) for row in rows
    )

    lines = [
        "# InferTutor Engineering Report",
        "",
        "## Final Run",
        "",
        f"- Track: {infer_track(config.get('mode', ''))}",
        f"- Final result file: `{final_file.name}`",
        f"- Final score: `{final_score:.0f}`",
        f"- Best TTFT p95 observed: `{best_ttft:.1f} ms`",
        f"- Best ITL p95 observed: `{best_itl:.1f} ms`",
        f"- Best throughput observed: `{best_throughput:.1f} chunks/s`",
        f"- Total GPU count: `{config.get('total_gpus', 0)}`",
        f"- Final error rate: `{format_percent(results.get('error_rate', 0.0))}`",
        f"- Experiment count included: `{len(rows)}`",
        "",
        "## Final Command",
        "",
        "```bash",
        runner_command,
        "```",
        "",
        "## Best Configuration",
        "",
        f"- Mode: `{config.get('mode', '')}`",
        f"- Users: `{config.get('users', 0)}`",
        f"- Total GPUs: `{config.get('total_gpus', 0)}`",
        f"- TTFT p95: `{results.get('ttft_p95_ms', 0.0):.1f} ms`",
        f"- ITL p95: `{results.get('itl_p95_ms', 0.0):.1f} ms`",
        f"- Throughput: `{results.get('aggregate_stream_chunks_per_s', 0.0):.1f} chunks/s`",
        "",
        "## Provenance",
        "",
        f"- Modal app name: `{provenance.get('app_name', '') or 'unknown'}`",
        f"- Git commit: `{source_control.get('commit', '') or 'unknown'}`",
        f"- Git branch: `{source_control.get('branch', '') or 'unknown'}`",
        f"- Git worktree dirty: `{source_control.get('is_dirty', 'unknown')}`",
        "",
        "## Required Commentary",
        "",
        "- Which optimization helped the most: TODO",
        "- Which optimization failed or surprised you: TODO",
        "- What would you try next with more time: TODO",
        "",
        "## Submission Checks",
        "",
        f"- At least five experiments included: `{'yes' if len(rows) >= 5 else 'no'}`",
        "",
        "## Experiment Matrix",
        "",
        render_experiment_table(rows).rstrip(),
        "",
    ]
    return "\n".join(lines) + "\n"


def write_bundle(
    rows: list[tuple[float, Path, dict]], output_dir: Path, final_index: int = 0
) -> dict:
    """Write the submission bundle to disk and return a manifest."""

    output_dir.mkdir(parents=True, exist_ok=True)
    final_score, final_file, final_data = rows[final_index]

    final_json_path = output_dir / "final_benchmark.json"
    shutil.copyfile(final_file, final_json_path)

    experiment_table_path = output_dir / "experiment_table.md"
    experiment_table_path.write_text(
        render_experiment_table(rows), encoding="utf-8"
    )

    report_path = output_dir / "engineering_report.md"
    report_path.write_text(
        build_report(final_score, final_file, final_data, rows), encoding="utf-8"
    )

    provenance = final_data.get("provenance", {})
    final_command_path = output_dir / "final_command.sh"
    final_command_path.write_text(
        (provenance.get("runner_command") or "TODO: record the exact final command")
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "final_result_source": str(final_file),
        "generated_files": {
            "final_benchmark_json": str(final_json_path),
            "engineering_report_md": str(report_path),
            "experiment_table_md": str(experiment_table_path),
            "final_command_sh": str(final_command_path),
        },
        "final_score": final_score,
        "mode": final_data["config"].get("mode", ""),
        "users": final_data["config"].get("users", 0),
        "total_gpus": final_data["config"].get("total_gpus", 0),
        "app_name": provenance.get("app_name", ""),
        "git_commit": provenance.get("source_control", {}).get("commit", ""),
        "git_branch": provenance.get("source_control", {}).get("branch", ""),
        "git_dirty": provenance.get("source_control", {}).get("is_dirty", False),
        "experiment_count": len(rows),
    }
    manifest_path = output_dir / "submission_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate InferTutor submission artifacts from result JSON files."
    )
    parser.add_argument(
        "path", nargs="?", default="results_infertutor", help="Result JSON file or directory"
    )
    parser.add_argument(
        "--output-dir",
        default="submission_bundle",
        help="Directory for generated submission files",
    )
    parser.add_argument(
        "--final-file",
        default="",
        help="Optional exact result JSON filename to use as the final submission run",
    )
    args = parser.parse_args()

    rows = load_ranked_results(Path(args.path))
    if not rows:
        raise SystemExit("No valid result JSON files found.")

    final_index = 0
    if args.final_file:
        matching = [
            index for index, (_, path, _) in enumerate(rows) if path.name == args.final_file
        ]
        if not matching:
            raise SystemExit(
                f"Could not find requested final result file: {args.final_file}"
            )
        final_index = matching[0]

    manifest = write_bundle(rows, Path(args.output_dir), final_index=final_index)
    print("Generated submission bundle:")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
