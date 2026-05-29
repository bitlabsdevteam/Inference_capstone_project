"""Fixed workload load tester for InferTutor Arena."""

from __future__ import annotations

import argparse
import asyncio
import base64
from collections import Counter
from datetime import datetime, timezone
import json
import os
import random
import statistics
import sys
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from rich.console import Console
from rich.live import Live
from rich.table import Table


console = Console()
ROOT = Path(__file__).parent
PROMPTS = json.loads((ROOT / "prompts.json").read_text())


def build_request_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("ENDPOINT_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def redact_endpoint_url(url: str) -> str:
    if not url:
        return ""
    if ".modal.run" in url:
        return "https://***.modal.run"
    return "<redacted>"


def build_result_payload(args, stats: Stats, workload_mix: dict[str, float]) -> dict:
    payload = {
        "schema_version": 2,
        "started_at_utc": datetime.fromtimestamp(
            stats.started_at, tz=timezone.utc
        ).isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            key: value
            for key, value in vars(args).items()
            if key not in {"api_key", "url"}
        }
        | {"endpoint_url_redacted": redact_endpoint_url(args.url)},
        "provenance": {
            "runner_command": args.runner_command,
            "app_name": args.app_name,
            "source_control": {
                "commit": args.git_commit,
                "branch": args.git_branch,
                "is_dirty": args.git_dirty,
            },
            "environment": {
                "python_executable": sys.executable,
                "python_version": sys.version.split()[0],
            },
        },
        "workload_mix": workload_mix,
        "results": stats.results(),
    }
    if getattr(args, "smoke_ok", False) or getattr(args, "smoke_status_code", 0):
        payload["smoke_check"] = {
            "ok": bool(args.smoke_ok),
            "status_code": int(args.smoke_status_code),
            "latency_ms": float(args.smoke_latency_ms),
            "response_excerpt": str(args.smoke_response_excerpt or "")[:120],
        }
    return payload


def make_png_data_url(width: int = 256, height: int = 192) -> str:
    """Create a small deterministic PNG as a diagram-like image prompt."""

    palette = [(245, 247, 250), (38, 92, 135), (228, 111, 71), (81, 168, 129)]
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            idx = ((x // 24) + (y // 24)) % len(palette)
            if 48 < x < 208 and 70 < y < 92:
                idx = 1
            if 48 < x < 208 and 132 < y < 154:
                idx = 2
            raw.extend(palette[idx])

    def chunk(kind: bytes, data: bytes) -> bytes:
        import struct

        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    import struct

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


IMAGE_URL = make_png_data_url()


@dataclass
class Stats:
    total_requests: int = 0
    total_successes: int = 0
    total_errors: int = 0
    total_chunks: int = 0
    ttft_ms: list[float] = field(default_factory=list)
    itl_ms: list[float] = field(default_factory=list)
    latency_ms: list[float] = field(default_factory=list)
    per_request_tps: list[float] = field(default_factory=list)
    error_types: Counter[str] = field(default_factory=Counter)
    error_statuses: Counter[str] = field(default_factory=Counter)
    last_error: str = ""
    started_at: float = 0.0
    active_users: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def success(self, ttft: float, itl: float, latency: float, chunks: int):
        async with self.lock:
            self.total_requests += 1
            self.total_successes += 1
            self.total_chunks += chunks
            self.ttft_ms.append(ttft)
            self.itl_ms.append(itl)
            self.latency_ms.append(latency)
            self.per_request_tps.append(chunks / (latency / 1000) if latency > 0 else 0)

    async def error(self, *, error_type: str, status_code: int | None = None, detail: str = ""):
        async with self.lock:
            self.total_requests += 1
            self.total_errors += 1
            self.error_types[error_type] += 1
            if status_code is not None:
                self.error_statuses[str(status_code)] += 1
            self.last_error = detail[:240] if detail else error_type

    @staticmethod
    def percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        return ordered[min(int(len(ordered) * p / 100), len(ordered) - 1)]

    def elapsed(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0

    def results(self) -> dict:
        elapsed = self.elapsed()
        return {
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_requests, 1),
            "total_stream_chunks": self.total_chunks,
            "ttft_p50_ms": self.percentile(self.ttft_ms, 50),
            "ttft_p95_ms": self.percentile(self.ttft_ms, 95),
            "ttft_p99_ms": self.percentile(self.ttft_ms, 99),
            "itl_p50_ms": self.percentile(self.itl_ms, 50),
            "itl_p95_ms": self.percentile(self.itl_ms, 95),
            "latency_p50_ms": self.percentile(self.latency_ms, 50),
            "latency_p95_ms": self.percentile(self.latency_ms, 95),
            "per_request_tps_mean": statistics.mean(self.per_request_tps) if self.per_request_tps else 0,
            "aggregate_stream_chunks_per_s": self.total_chunks / elapsed if elapsed else 0,
            "requests_per_s": self.total_requests / elapsed if elapsed else 0,
            "successes_per_s": self.total_successes / elapsed if elapsed else 0,
            "errors_by_type": dict(self.error_types),
            "errors_by_status": dict(self.error_statuses),
            "last_error": self.last_error,
        }

    def table(self) -> Table:
        r = self.results()
        table = Table(title=f"InferTutor Load Test - {self.elapsed():.0f}s")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        table.add_row("Active users", str(self.active_users))
        table.add_row("Requests", str(r["total_requests"]))
        table.add_row("Successes", str(r["total_successes"]))
        table.add_row("Errors", str(r["total_errors"]))
        table.add_row("TTFT p95", f'{r["ttft_p95_ms"]:.1f} ms')
        table.add_row("ITL p95", f'{r["itl_p95_ms"]:.1f} ms')
        table.add_row("Latency p95", f'{r["latency_p95_ms"]:.1f} ms')
        table.add_row("Throughput", f'{r["aggregate_stream_chunks_per_s"]:.1f} chunks/s')
        table.add_row("Req/s", f'{r["requests_per_s"]:.2f}')
        return table


def choose_messages(mode: str) -> list[dict]:
    """Build one OpenAI chat request from the official prompt set."""

    system = {"role": "system", "content": PROMPTS["system_prompt"]}
    if mode == "text":
        return [system, {"role": "user", "content": random.choice(PROMPTS["text"])}]
    if mode == "long":
        return [system, {"role": "user", "content": random.choice(PROMPTS["long"])}]
    if mode == "image":
        content = [
            {"type": "image_url", "image_url": {"url": IMAGE_URL}},
            {"type": "text", "text": random.choice(PROMPTS["image"])},
        ]
        return [system, {"role": "user", "content": content}]

    # Official product workload: mostly text, with some long and image traffic.
    roll = random.random()
    if roll < 0.25:
        return choose_messages("image")
    if roll < 0.45:
        return choose_messages("long")
    return choose_messages("text")


def extract_content(delta: dict) -> str:
    """Normalize OpenAI-style streamed content into a string for counting."""

    content = delta.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "".join(parts)
    return ""


async def user_loop(user_id: int, args, stats: Stats, stop_event: asyncio.Event):
    async with httpx.AsyncClient(timeout=args.request_timeout) as client:
        while not stop_event.is_set():
            payload = {
                "model": args.model,
                "messages": choose_messages(args.mode),
                "max_tokens": args.max_tokens,
                "temperature": 0.2,
                "stream": True,
            }

            request_start = time.perf_counter()
            first_chunk_at = None
            chunk_times = []
            chunks = 0
            request_error_type = ""
            request_error_detail = ""

            try:
                async with client.stream(
                    "POST",
                    f"{args.url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=build_request_headers(),
                ) as resp:
                    if resp.status_code != 200:
                        detail = (await resp.aread()).decode("utf-8", errors="replace")
                        await stats.error(
                            error_type="http_error",
                            status_code=resp.status_code,
                            detail=detail,
                        )
                        continue

                    async for line in resp.aiter_lines():
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        try:
                            chunk = json.loads(line)
                            content = extract_content(chunk["choices"][0]["delta"])
                        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                            request_error_type = "stream_parse_error"
                            request_error_detail = str(exc)
                            break
                        if content:
                            now = time.perf_counter()
                            first_chunk_at = first_chunk_at or now
                            chunk_times.append(now)
                            chunks += 1

                request_end = time.perf_counter()
                if request_error_type:
                    await stats.error(
                        error_type=request_error_type,
                        detail=request_error_detail,
                    )
                    continue
                if first_chunk_at is None or chunks == 0:
                    await stats.error(
                        error_type="empty_stream",
                        detail="The response completed without any content chunks.",
                    )
                    continue

                gaps = [b - a for a, b in zip(chunk_times, chunk_times[1:])]
                ttft = (first_chunk_at - request_start) * 1000
                itl = (sum(gaps) / len(gaps) * 1000) if gaps else 0.0
                latency = (request_end - request_start) * 1000
                await stats.success(ttft, itl, latency, chunks)
            except httpx.TimeoutException as exc:
                await stats.error(error_type="timeout", detail=str(exc))
            except httpx.HTTPError as exc:
                await stats.error(error_type="http_client_error", detail=str(exc))
            except Exception as exc:
                await stats.error(error_type="unexpected_error", detail=str(exc))

            await asyncio.sleep(random.uniform(args.min_pause, args.max_pause))


async def run(args):
    stats = Stats(started_at=time.time())
    stop_event = asyncio.Event()
    tasks = []

    async def ramp_users():
        delay = args.ramp_up / max(args.users, 1) if args.ramp_up else 0
        for i in range(args.users):
            if stop_event.is_set():
                return
            tasks.append(asyncio.create_task(user_loop(i, args, stats, stop_event)))
            stats.active_users = i + 1
            if delay:
                await asyncio.sleep(delay)

    ramp_task = asyncio.create_task(ramp_users())
    with Live(stats.table(), refresh_per_second=0.5, console=console) as live:
        end = time.time() + args.duration
        while time.time() < end:
            await asyncio.sleep(2)
            live.update(stats.table())

    stop_event.set()
    ramp_task.cancel()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    workload_mix = {"text": 1.0} if args.mode == "text" else {
        "long": 1.0 if args.mode == "long" else 0.0,
        "image": 1.0 if args.mode == "image" else 0.0,
        "text": 1.0 if args.mode == "text" else 0.0,
    }
    if args.mode == "mixed":
        workload_mix = {"text": 0.55, "long": 0.20, "image": 0.25}

    result = build_result_payload(args, stats, workload_mix)
    out_dir = ROOT / "results_infertutor"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{args.label}_{args.mode}_{args.users}u_{int(time.time())}.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    console.print(stats.table())
    console.print(f"[green]Saved {out_file}[/green]")


def validate_args(args) -> None:
    if args.users <= 0:
        raise ValueError("--users must be > 0.")
    if args.duration <= 0:
        raise ValueError("--duration must be > 0.")
    if args.ramp_up < 0:
        raise ValueError("--ramp-up must be >= 0.")
    if args.max_tokens <= 0:
        raise ValueError("--max-tokens must be > 0.")
    if args.request_timeout <= 0:
        raise ValueError("--request-timeout must be > 0.")
    if args.total_gpus <= 0:
        raise ValueError("--total-gpus must be > 0.")
    if args.min_pause < 0 or args.max_pause < 0:
        raise ValueError("--min-pause and --max-pause must be >= 0.")
    if args.min_pause > args.max_pause:
        raise ValueError("--min-pause cannot be greater than --max-pause.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct")
    parser.add_argument("--mode", choices=["text", "long", "image", "mixed"], default="mixed")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--ramp-up", type=int, default=15)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--min-pause", type=float, default=0.2)
    parser.add_argument("--max-pause", type=float, default=1.2)
    parser.add_argument("--label", default="manual")
    parser.add_argument("--total-gpus", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--runner-command", default="")
    parser.add_argument("--app-name", default="")
    parser.add_argument("--git-commit", default="")
    parser.add_argument("--git-branch", default="")
    parser.add_argument(
        "--git-dirty",
        type=lambda value: value.lower() == "true",
        default=False,
    )
    parser.add_argument(
        "--smoke-ok",
        type=lambda value: value.lower() == "true",
        default=False,
    )
    parser.add_argument("--smoke-status-code", type=int, default=0)
    parser.add_argument("--smoke-latency-ms", type=float, default=0.0)
    parser.add_argument("--smoke-response-excerpt", default="")
    args = parser.parse_args()
    validate_args(args)
    random.seed(args.seed)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
