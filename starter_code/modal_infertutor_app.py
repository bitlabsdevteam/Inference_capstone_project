"""
InferTutor Arena - Modal + vLLM server.

Students should usually not edit this file first. Start by changing
configuration from run_infertutor_experiment.py CLI flags.

This app runs Qwen/Qwen3-VL-4B-Instruct behind an OpenAI-compatible vLLM
HTTP server on Modal.
"""

import os
import json
import subprocess
import time

import modal


# vLLM 0.21.0 supports Qwen3-VL and the OpenAI-compatible multimodal API.
# The CUDA base image gives vLLM access to the GPU runtime it needs.
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12"
    )
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0", "qwen-vl-utils==0.0.14")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

app = modal.App("infertutor-arena")

# Persistent caches reduce repeated model download and compilation overhead.
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)


# These constants are patched by run_infertutor_experiment.py before deploy.
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-VL-4B-Instruct")
TENSOR_PARALLEL = int(os.environ.get("TENSOR_PARALLEL", "1"))
GPU_TYPE = os.environ.get("GPU_TYPE", "H100")
GPU_COUNT = int(os.environ.get("GPU_COUNT", str(TENSOR_PARALLEL)))
DTYPE = os.environ.get("DTYPE", "bfloat16")
ENABLE_PREFIX_CACHING = os.environ.get("ENABLE_PREFIX_CACHING", "true").lower() == "true"
ENABLE_CHUNKED_PREFILL = os.environ.get("ENABLE_CHUNKED_PREFILL", "true").lower() == "true"
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "8192"))
MAX_NUM_BATCHED_TOKENS = int(os.environ.get("MAX_NUM_BATCHED_TOKENS", "4096"))
MAX_NUM_SEQS = int(os.environ.get("MAX_NUM_SEQS", "32"))
CONCURRENT_INPUTS = int(os.environ.get("CONCURRENT_INPUTS", "64"))
MIN_CONTAINERS = int(os.environ.get("MIN_CONTAINERS", "1"))
MAX_CONTAINERS = int(os.environ.get("MAX_CONTAINERS", "1"))
FAST_BOOT = os.environ.get("FAST_BOOT", "true").lower() == "true"
MM_MAX_PIXELS = int(os.environ.get("MM_MAX_PIXELS", str(512 * 28 * 28)))

MINUTES = 60
VLLM_PORT = 8000
VLLM_STARTUP_GRACE_SECONDS = 20


def redact_command(cmd: list[str]) -> list[str]:
    """Redact sensitive values before logging command metadata."""

    redacted: list[str] = []
    skip_next = False
    for part in cmd:
        if skip_next:
            redacted.append("***")
            skip_next = False
            continue
        redacted.append(part)
        if part == "--api-key":
            skip_next = True
    return redacted


def emit_runtime_event(event: str, **fields) -> None:
    """Print one machine-readable runtime event line."""

    payload = {
        "event": event,
        "component": "infertutor_modal_app",
        "ts_unix": round(time.time(), 3),
    }
    payload.update(fields)
    print(json.dumps(payload, sort_keys=True), flush=True)


def build_vllm_command() -> list[str]:
    """Build the vLLM serve command from the configured constants."""

    endpoint_api_key = os.environ.get("ENDPOINT_API_KEY", "").strip()
    if not endpoint_api_key:
        raise RuntimeError(
            "ENDPOINT_API_KEY is required. Create the 'infertutor-auth' Modal "
            "secret and expose ENDPOINT_API_KEY before deploying."
        )

    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--served-model-name",
        MODEL_NAME,
        "--host",
        "0.0.0.0",
        "--port",
        str(VLLM_PORT),
        "--tensor-parallel-size",
        str(TENSOR_PARALLEL),
        "--dtype",
        DTYPE,
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--max-num-batched-tokens",
        str(MAX_NUM_BATCHED_TOKENS),
        "--max-num-seqs",
        str(MAX_NUM_SEQS),
        "--gpu-memory-utilization",
        "0.90",
        "--uvicorn-log-level=warning",
        "--limit-mm-per-prompt",
        '{"image": 1, "video": 0}',
        "--mm-processor-kwargs",
        f'{{"min_pixels": 784, "max_pixels": {MM_MAX_PIXELS}, "fps": 1}}',
        "--api-key",
        endpoint_api_key,
    ]

    # Eager mode starts faster. Compiled mode can improve text-only throughput
    # after a longer warmup.
    if FAST_BOOT:
        cmd += ["--enforce-eager"]
    else:
        cmd += ["--no-enforce-eager"]

    if ENABLE_PREFIX_CACHING:
        cmd += ["--enable-prefix-caching"]

    if ENABLE_CHUNKED_PREFILL:
        cmd += ["--enable-chunked-prefill"]

    return cmd


def launch_vllm_server(cmd: list[str], startup_grace_s: int = VLLM_STARTUP_GRACE_SECONDS):
    """Start vLLM and fail fast if the process exits during initial startup."""

    emit_runtime_event(
        "vllm_starting",
        startup_grace_s=startup_grace_s,
        command=redact_command(cmd),
    )
    process = subprocess.Popen(cmd)
    deadline = time.time() + startup_grace_s
    while time.time() < deadline:
        return_code = process.poll()
        if return_code is not None:
            emit_runtime_event("vllm_startup_failed", return_code=return_code)
            raise RuntimeError(
                f"vLLM exited during startup with return code {return_code}."
            )
        time.sleep(1)
    emit_runtime_event("vllm_startup_ready", pid=process.pid)
    return process


@app.function(
    image=vllm_image,
    gpu=f"{GPU_TYPE}:{GPU_COUNT}",
    scaledown_window=10 * MINUTES,
    min_containers=MIN_CONTAINERS,
    max_containers=MAX_CONTAINERS,
    timeout=15 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
    },
    secrets=[
        modal.Secret.from_name("huggingface", required_keys=["HF_TOKEN"]),
        modal.Secret.from_name("infertutor-auth", required_keys=["ENDPOINT_API_KEY"]),
    ],
)
@modal.concurrent(max_inputs=CONCURRENT_INPUTS)
@modal.web_server(port=VLLM_PORT, startup_timeout=15 * MINUTES)
def serve():
    """Start vLLM inside the Modal container."""

    cmd = build_vllm_command()
    emit_runtime_event(
        "serve_invoked",
        model=MODEL_NAME,
        tensor_parallel=TENSOR_PARALLEL,
        gpu_type=GPU_TYPE,
        gpu_count=GPU_COUNT,
        max_num_seqs=MAX_NUM_SEQS,
        max_num_batched_tokens=MAX_NUM_BATCHED_TOKENS,
    )
    launch_vllm_server(cmd)
