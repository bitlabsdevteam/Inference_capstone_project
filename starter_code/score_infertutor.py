"""Score InferTutor benchmark result JSON files."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

try:
    from .result_schema import load_result, result_row, score_result
except ImportError:
    from result_schema import load_result, result_row, score_result


console = Console()


def main():
    parser = argparse.ArgumentParser(description="Score InferTutor benchmark result JSON files.")
    parser.add_argument("path", nargs="?", default="results_infertutor")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]No result path found:[/red] {path}")
        raise SystemExit(1)

    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files:
        console.print(f"[red]No JSON results found in:[/red] {path}")
        raise SystemExit(1)

    rows = []
    rejected = []
    for file in files:
        try:
            data = load_result(file)
        except (OSError, ValueError) as exc:
            rejected.append((file.name, str(exc)))
            continue
        rows.append((score_result(data), file, data))

    if not rows:
        console.print("[red]No valid result JSON files found.[/red]")
        for name, error in rejected:
            console.print(f" - {name}: {error}")
        raise SystemExit(1)

    rows.sort(reverse=True, key=lambda x: x[0])

    table = Table(title="InferTutor Leaderboard")
    for col in ["file", "mode", "users", "gpus", "err%", "TTFT p95", "ITL p95", "throughput", "req/s", "score"]:
        table.add_column(col, justify="right" if col != "file" else "left")

    for value, file, data in rows:
        row = result_row(data)
        table.add_row(
            file.name,
            str(row["mode"]),
            str(int(row["users"])),
            str(int(row["gpus"])),
            f'{100 * row["error_rate"]:.1f}',
            f'{row["ttft_p95_ms"]:.0f} ms',
            f'{row["itl_p95_ms"]:.1f} ms',
            f'{row["throughput"]:.1f}',
            f'{row["requests_per_s"]:.2f}',
            f"{value:.0f}",
        )

    console.print(table)
    if rejected:
        console.print("\n[yellow]Skipped invalid result files:[/yellow]")
        for name, error in rejected:
            console.print(f" - {name}: {error}")


if __name__ == "__main__":
    main()
