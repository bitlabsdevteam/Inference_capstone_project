# InferTutor Architecture

## Status

The repository is locally complete for the intended capstone workflow:

- Modal app definition exists and is configurable through CLI-driven patching.
- The experiment runner deploys, health-checks, and then invokes the load tester.
- The load tester supports `text`, `long`, `image`, and `mixed` workloads.
- Result JSON files are validated, scored, and converted into submission artifacts.
- Local validation and unit tests run without requiring a live Modal deploy.

This document explains how the system works and how to test it step by step.

## High-Level System

InferTutor is a benchmark harness around a Modal-hosted vLLM server for
`Qwen/Qwen3-VL-4B-Instruct`.

There are two execution environments:

1. Local machine
   - Prepares experiment configuration
   - Deploys Modal apps
   - Polls `/health`
   - Runs concurrent load tests
   - Writes benchmark JSON files
   - Scores results and generates the final submission bundle

2. Modal GPU containers
   - Start the vLLM OpenAI-compatible server
   - Load the Qwen multimodal model
   - Serve `/health`
   - Serve `/v1/chat/completions`

## Core Flow

```text
run_infertutor_experiment.py
  -> patches modal_infertutor_app.py into modal_infertutor_app_generated.py
  -> modal deploy <generated app>
  -> wait for /health
  -> run load_test_infertutor.py
       -> send streamed chat completion requests
       -> collect TTFT / ITL / latency / throughput / error metrics
       -> save results_infertutor/*.json
  -> score_infertutor.py can rank saved results
  -> generate_submission_artifacts.py builds submission_bundle/*
```

## Main Files

### Root

- `README.md`
  - Main project overview and benchmark commands.
- `AGENTS.md`
  - Repository instructions and submission constraints.
- `scripts/validate_repo.sh`
  - One local entrypoint for bytecode checks, unit tests, and preflight.
- `architecture.md`
  - This file.

### `starter_code/`

- `modal_infertutor_app.py`
  - Modal app template that starts the vLLM server.
- `run_infertutor_experiment.py`
  - Main orchestration entrypoint.
- `load_test_infertutor.py`
  - Streaming load tester and metric collector.
- `preflight_infertutor.py`
  - Local environment and readiness checks.
- `bootstrap_infertutor_env.py`
  - Sets Modal auth and the required Hugging Face secret from env vars.
- `result_schema.py`
  - Shared result validation and scoring helpers.
- `score_infertutor.py`
  - Human-readable leaderboard view over saved results.
- `generate_submission_artifacts.py`
  - Produces final submission files from real benchmark outputs.
- `prompts.json`
  - Fixed official workload source.

### `tests/`

- `tests/test_infertutor_tools.py`
  - Local regression tests for patching, validation, scoring, submission bundle
    generation, and bootstrap/preflight helpers.

## Component Details

### 1. Modal App Template

`starter_code/modal_infertutor_app.py` defines the serving container:

- Uses `nvidia/cuda:12.9.0-devel-ubuntu22.04`
- Installs:
  - `vllm==0.21.0`
  - `qwen-vl-utils==0.0.14`
- Mounts persistent caches:
  - Hugging Face cache
  - vLLM cache
- Requires Modal secret:
  - `huggingface` with `HF_TOKEN`
  - `infertutor-auth` with `ENDPOINT_API_KEY`

The constants in this file are the patch targets used by the experiment runner:

- `MODEL_NAME`
- `TENSOR_PARALLEL`
- `GPU_TYPE`
- `GPU_COUNT`
- `DTYPE`
- `ENABLE_PREFIX_CACHING`
- `ENABLE_CHUNKED_PREFILL`
- `MAX_MODEL_LEN`
- `MAX_NUM_BATCHED_TOKENS`
- `MAX_NUM_SEQS`
- `CONCURRENT_INPUTS`
- `MIN_CONTAINERS`
- `MAX_CONTAINERS`
- `FAST_BOOT`
- `MM_MAX_PIXELS`

`build_vllm_command()` converts those settings into a `vllm serve` command.

### 2. Experiment Runner

`starter_code/run_infertutor_experiment.py` is the main operator interface.

Responsibilities:

- Validates CLI arguments.
- Sanitizes the experiment label into a Modal-safe app name.
- Patches `modal_infertutor_app.py` into `modal_infertutor_app_generated.py`.
- Deploys the generated app with `modal deploy`.
- Waits for `/health`.
- Verifies a real authenticated `/v1/chat/completions` smoke request before load.
- Invokes `load_test_infertutor.py` with provenance metadata.

Important design point:

- Students are expected to vary CLI flags, not rewrite the deployment logic.

### 3. Load Tester

`starter_code/load_test_infertutor.py` drives traffic against the OpenAI-compatible
endpoint.

Capabilities:

- Supports four workload modes:
  - `text`
  - `long`
  - `image`
  - `mixed`
- Uses the shared InferTutor system prompt from `prompts.json`.
- Generates a deterministic inline PNG data URL for image traffic.
- Sends bearer-authenticated requests when `ENDPOINT_API_KEY` is configured.
- Sends streaming requests to `/v1/chat/completions`.
- Measures:
  - TTFT
  - ITL
  - latency
  - throughput
  - req/s
  - success rate
  - error breakdowns
- Writes timestamped result JSON files under `starter_code/results_infertutor/`.

### 4. Result Schema and Scoring

`starter_code/result_schema.py` validates benchmark outputs and computes the local
leaderboard score:

```text
score = goodput * users / (ttft_p95_seconds * itl_p95_seconds * total_gpus)
```

Where:

- `goodput = aggregate_stream_chunks_per_s * (1 - error_rate)`

`starter_code/score_infertutor.py` renders those results as a leaderboard table.
It now also surfaces whether the pre-load functional smoke check was recorded
for each run.

Important limitation:

- This local score is based on streamed content chunks per second, not exact
  token throughput.
- The README's `quality_pass_rate` term is part of the final external
  evaluation story, not something the starter harness currently measures.

### 5. Submission Artifact Generator

`starter_code/generate_submission_artifacts.py` consumes one or more real result
JSON files and writes:

- `final_benchmark.json`
- `engineering_report.md`
- `experiment_table.md`
- `final_command.sh`
- `submission_manifest.json`

The generator supports two modes:

- Submission-ready mode requires five or more real experiment JSON files, final
  provenance, and finalized structured commentary.
- Draft mode is available through `--allow-draft` and still emits placeholder
  commentary for local preview workflows.

## Request Lifecycle

One benchmark request follows this path:

1. The load tester chooses a request payload from `prompts.json`.
2. It posts a streamed request to `/v1/chat/completions`.
3. The Modal container forwards the request into vLLM.
4. vLLM performs multimodal preprocessing and generation.
5. Streamed delta chunks return to the client.
6. The load tester timestamps:
   - request start
   - first streamed content chunk
   - subsequent content chunks
   - request completion
7. Aggregated statistics are persisted to a JSON result file.

The persisted result can also include:

- `smoke_check.ok`
- `smoke_check.status_code`
- `smoke_check.latency_ms`
- `smoke_check.response_excerpt`

## Configuration and Secrets

Recommended `.env` shape:

```env
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...
HF_TOKEN=...
ENDPOINT_API_KEY=...
MODEL_NAME=Qwen/Qwen3-VL-4B-Instruct
```

Notes:

- `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` come from Modal, not Hugging Face.
- `HF_TOKEN` is used to create the Modal secret named `huggingface`.
- `ENDPOINT_API_KEY` is used locally and in the Modal secret named
  `infertutor-auth` so the benchmark client can authenticate to the deployed
  vLLM server.
- `MODEL_NAME` should remain `Qwen/Qwen3-VL-4B-Instruct` for normal submissions.

To load `.env` into the current shell:

```bash
set -a
source .env
set +a
```

## Local-Only Test Checklist

These steps do not require deploying to Modal.

### Step 1. Verify the virtualenv exists

From repo root:

```bash
./.venv/bin/python --version
```

Expected:

- Python 3.11+

### Step 2. Run the main local validation suite

From repo root:

```bash
bash scripts/validate_repo.sh
```

What it checks:

- Bytecode compilation
- Unit tests
- Preflight

Expected:

- `Validation complete.`
- Optional `modal_auth` warning is acceptable for local-only validation if you
  have not loaded Modal auth into the shell.
- Optional `endpoint_api_key` warning is acceptable for local-only validation if
  you have not loaded `ENDPOINT_API_KEY` into the shell.

### Step 3. Run unit tests directly

From repo root:

```bash
./.venv/bin/python -m unittest tests.test_infertutor_tools
```

What this proves:

- Template patching works
- CLI validation works
- Result schema validation works
- Submission bundle generation works
- Bootstrap/preflight helper logic works

### Step 4. Check CLI surfaces

From repo root:

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py --help
./.venv/bin/python starter_code/load_test_infertutor.py --help
./.venv/bin/python starter_code/score_infertutor.py --help
./.venv/bin/python starter_code/preflight_infertutor.py --help
./.venv/bin/python starter_code/generate_submission_artifacts.py --help
```

What this proves:

- The entrypoints import successfully
- The documented flags exist

### Step 5. Check local preflight explicitly

From repo root:

```bash
./.venv/bin/python starter_code/preflight_infertutor.py --json
```

Expected:

- `ok: true`
- `modal_auth` may be false if env vars are not loaded into the current shell

### Step 6. Optional authenticated local preflight

If you want local proof that auth is wired correctly:

```bash
set -a
source .env
set +a
./.venv/bin/python starter_code/preflight_infertutor.py --require-modal-auth --json
```

Expected:

- `ok: true`
- `modal_auth.ok: true`

### Step 7. Optional bootstrap dry run

This step still does not deploy a benchmark.

```bash
export PATH="$PWD/.venv/bin:$PATH"
set -a
source .env
set +a
./.venv/bin/python starter_code/bootstrap_infertutor_env.py
```

What it does:

- Configures Modal auth from `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`
- Creates or reuses the `huggingface` Modal secret

## User-Run Modal Test Checklist

You asked to leave Modal testing to you. These are the exact steps to run when
you want live verification.

### Step 1. Load environment variables

From repo root:

```bash
export PATH="$PWD/.venv/bin:$PATH"
set -a
source .env
set +a
```

### Step 2. Authenticate and provision the HF secret

```bash
./.venv/bin/python starter_code/bootstrap_infertutor_env.py
```

### Step 3. Require authenticated validation

```bash
bash scripts/validate_repo.sh --require-modal-auth
```

### Step 4. Run the smoke test

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label smoke \
  --gpu-type H100 \
  --replicas 1 \
  --mode text \
  --users 5 \
  --duration 30 \
  --ramp-up 5 \
  --max-tokens 64
```

Acceptance:

- Deploy succeeds
- `/health` succeeds
- A JSON file appears under `starter_code/results_infertutor/`
- The smoke result has `error_rate == 0`

### Step 5. Run submission experiments

From repo root:

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-baseline-r1 \
  --gpu-type H100 \
  --replicas 1 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 50 \
  --duration 90 \
  --ramp-up 20 \
  --max-tokens 96
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r2 \
  --gpu-type H100 \
  --replicas 2 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 100 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r2-users120 \
  --gpu-type H100 \
  --replicas 2 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 120 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r2-noprefix \
  --gpu-type H100 \
  --replicas 2 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 100 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96 \
  --no-prefix-cache
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r2-nochunk \
  --gpu-type H100 \
  --replicas 2 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 100 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96 \
  --no-chunked-prefill
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r2-seq64-b8192 \
  --gpu-type H100 \
  --replicas 2 \
  --max-seqs 64 \
  --max-batch-tokens 8192 \
  --mode mixed \
  --users 100 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96
```

```bash
./.venv/bin/python starter_code/run_infertutor_experiment.py \
  --label mixed-r4 \
  --gpu-type H100 \
  --replicas 4 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 120 \
  --duration 90 \
  --ramp-up 30 \
  --max-tokens 96
```

### Step 6. Score the accumulated results

```bash
./.venv/bin/python starter_code/score_infertutor.py starter_code/results_infertutor
```

Selection rule:

- Prefer the highest-scoring `mixed` run with acceptable multimodal behavior.
- Prefer a zero-error run over a slightly higher-scoring run with non-trivial
  errors.

### Step 7. Generate the submission bundle

Replace `<final-file>.json` with your chosen real benchmark output.

```bash
./.venv/bin/python starter_code/generate_submission_artifacts.py \
  starter_code/results_infertutor \
  --final-file <final-file>.json \
  --output-dir starter_code/submission_bundle
```

### Step 8. Provide final commentary

Create a JSON file for the final run commentary and pass it with
`--commentary-file` when generating the bundle. Use `--allow-draft` only for
local previews.

### Step 9. Verify submission contents

The final bundle must contain:

- `final_benchmark.json`
- `final_command.sh`
- `engineering_report.md`
- `experiment_table.md`
- `submission_manifest.json`

### Step 10. Stop running Modal apps

```bash
export PATH="$PWD/.venv/bin:$PATH"
modal app list
modal app stop <APP_ID_OR_NAME>
```

## Local Evidence Collected

The following local checks are the strongest non-Modal proof points:

- `bash scripts/validate_repo.sh`
- `./.venv/bin/python -m unittest tests.test_infertutor_tools`
- `./.venv/bin/python starter_code/run_infertutor_experiment.py --help`
- `./.venv/bin/python starter_code/load_test_infertutor.py --help`
- `./.venv/bin/python starter_code/score_infertutor.py --help`

These confirm the repo is locally runnable and the main toolchain is implemented.
They do not replace live Modal smoke testing.

## Known Boundaries

- Local validation cannot prove live GPU deployment quality.
- Final submission artifacts should be generated only from real benchmark JSON
  files, not synthetic placeholders.
- `engineering_report.md` is not complete until the final bundle is generated
  without `--allow-draft` and includes finalized commentary.
