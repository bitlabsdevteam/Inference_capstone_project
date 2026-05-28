# AGENTS.md

Instructions for AI coding agents working on the InferTutor Arena capstone repository.

## Project Purpose

InferTutor Arena is an inference-engineering capstone. The deliverable is not a generic chatbot app; it is a production-style benchmark and tuning workflow for a Modal-hosted vLLM OpenAI-compatible server.

The student-facing goal is to deploy `Qwen/Qwen3-VL-4B-Instruct` on Modal GPUs, drive concurrent text/long/image/mixed workloads, measure inference metrics, tune serving parameters, and produce a defensible final benchmark/report.

Optimize for evidence-backed inference engineering:

- Low p95 time to first token (`TTFT`).
- Low p95 inter-token latency (`ITL`).
- High streamed output throughput.
- High sustained concurrent users.
- Low request error rate.
- Efficient GPU use.
- Preserved multimodal behavior for mixed/image workloads.

## Repository Map

Root files:

- `README.md`: Primary project overview, quick start, benchmark examples, scoring, cleanup, and submission checklist.
- `InferTutor_Arena_Capstone.md`: Editable source for the main assignment PDF.
- `InferTutor_Arena_Capstone.pdf`: Rendered student assignment.
- `Modal_vLLM_Runbook.md`: Editable infrastructure setup/runbook source.
- `Modal_vLLM_Runbook.pdf`: Rendered setup/runbook.
- `render_pdfs.py`: Regenerates both PDFs from the Markdown sources.
- `starter_code/`: Runnable Modal/vLLM starter implementation.

Starter code:

- `starter_code/modal_infertutor_app.py`: Modal app that launches vLLM on GPU.
- `starter_code/run_infertutor_experiment.py`: One-command deploy, health-check, and load-test runner.
- `starter_code/load_test_infertutor.py`: Async streaming load tester for fixed workloads.
- `starter_code/score_infertutor.py`: Local result summarizer and leaderboard scorer.
- `starter_code/preflight_infertutor.py`: Local environment and repo readiness checks before deployment.
- `starter_code/bootstrap_infertutor_env.py`: Bootstraps Modal authentication and the required Hugging Face secret from environment variables.
- `starter_code/generate_submission_artifacts.py`: Builds submission-ready artifacts from saved result JSON files.
- `starter_code/result_schema.py`: Shared validation and scoring utilities for benchmark result files.
- `scripts/validate_repo.sh`: Single entrypoint for bytecode checks, unit tests, and preflight.
- `.github/workflows/quality.yml`: CI workflow that runs the validation entrypoint on pushes and pull requests.
- `starter_code/prompts.json`: Official fixed prompt set. Do not modify for submitted runs.
- `starter_code/requirements.txt`: Local Python dependencies.
- `starter_code/README.md`: Starter-code quick start.

Generated runtime artifacts:

- `starter_code/modal_infertutor_app_generated.py`: Created by `run_infertutor_experiment.py` per experiment. Treat as generated.
- `starter_code/results_infertutor/*.json`: Benchmark output files. These are submission artifacts, not source code.

## Environment Assumptions

Use Python 3.11 or newer. On this machine, prefer `python3` because `python` may not exist.

Install local dependencies from `starter_code`:

```bash
cd starter_code
python3 -m pip install -r requirements.txt
```

The remote vLLM container is built by Modal from `nvidia/cuda:12.9.0-devel-ubuntu22.04` with Python 3.12 and installs:

```text
vllm==0.21.0
qwen-vl-utils==0.0.14
```

Modal and Hugging Face setup are required for live benchmarks:

```bash
modal token new
modal secret create huggingface HF_TOKEN=<YOUR_HF_TOKEN>
```

The Modal secret name must be exactly `huggingface` and must expose `HF_TOKEN`, because `modal_infertutor_app.py` declares:

```python
secrets=[modal.Secret.from_name("huggingface", required_keys=["HF_TOKEN"])]
```

Never commit tokens, Modal credentials, generated secrets, or private endpoint URLs intended to remain private.

## Core Architecture

The local machine runs the experiment orchestrator and load tester. Modal runs GPU containers with vLLM.

Flow:

```text
run_infertutor_experiment.py
  patches modal_infertutor_app.py constants
  deploys modal_infertutor_app_generated.py
  waits for /health
  starts load_test_infertutor.py
    sends streaming OpenAI-compatible chat requests
    writes results_infertutor/*.json
score_infertutor.py
  reads result JSON files
  computes local leaderboard score
```

The deployed endpoint serves:

```text
/health
/v1/chat/completions
```

The benchmark uses streamed chat completions and treats each non-empty streamed content delta as a chunk for starter-code throughput.

## Source Of Truth For Workloads

`starter_code/prompts.json` is the official workload source. Do not change it for final/submitted runs.

Modes:

- `text`: Normal tutor questions, decode throughput, streaming latency.
- `long`: Larger prefills, chunked prefill pressure, KV pressure.
- `image`: Multimodal path using a deterministic generated PNG data URL.
- `mixed`: Official product-like workload; about 25% image, 20% long, and the rest text.

The load tester always adds the fixed InferTutor system prompt. Prefix caching matters because that system prompt is shared across requests.

## Primary Commands

Run from `starter_code` unless noted otherwise.

Smoke test:

```bash
python3 run_infertutor_experiment.py \
  --label smoke \
  --gpu-type H100 \
  --replicas 1 \
  --mode text \
  --users 5 \
  --duration 30 \
  --ramp-up 5 \
  --max-tokens 64
```

Single-GPU baseline:

```bash
python3 run_infertutor_experiment.py \
  --label baseline-text \
  --gpu-type H100 \
  --replicas 1 \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode text \
  --users 50 \
  --duration 60 \
  --ramp-up 15 \
  --max-tokens 96
```

Main multimodal baseline:

```bash
python3 run_infertutor_experiment.py \
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

Text speed baseline with compiled mode:

```bash
python3 run_infertutor_experiment.py \
  --label compiled-r4 \
  --gpu-type H100 \
  --replicas 4 \
  --no-fast-boot \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode text \
  --users 400 \
  --duration 90 \
  --ramp-up 40 \
  --max-tokens 96
```

Score results:

```bash
python3 score_infertutor.py results_infertutor
```

Run local preflight:

```bash
python3 preflight_infertutor.py
```

Require deploy readiness:

```bash
python3 preflight_infertutor.py --require-modal-auth
```

Bootstrap Modal auth and the required secret from environment variables:

```bash
MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=... HF_TOKEN=... python3 bootstrap_infertutor_env.py
```

Run repository validation:

```bash
bash scripts/validate_repo.sh
```

If the local machine is not provisioned for Modal yet, use:

```bash
bash scripts/validate_repo.sh --skip-preflight
```

To require actual Modal authentication readiness, use:

```bash
bash scripts/validate_repo.sh --require-modal-auth
```

Generate a submission bundle:

```bash
python3 generate_submission_artifacts.py results_infertutor
```

Stop Modal apps after experiments:

```bash
modal app list
modal app stop <APP_ID_OR_NAME>
```

Regenerate PDFs from repository root after editing the Markdown assignment/runbook:

```bash
python3 render_pdfs.py
```

## Experiment Runner Flags

`run_infertutor_experiment.py` is the preferred tuning interface. Students should vary CLI flags before rewriting deployment code.

Important serving/deployment flags:

- `--model`: Defaults to `Qwen/Qwen3-VL-4B-Instruct`. Do not change for normal final submissions.
- `--gpu-type`: One of `H100`, `H200`, `A100`, `L40S`; assignment target is `H100`.
- `--gpu-count`: GPUs per Modal container. Defaults to `--tp` if unset.
- `--tp`: vLLM tensor parallel size. Defaults to `1`.
- `--replicas`: Modal min/max containers. This scales out independent vLLM replicas.
- `--dtype`: Defaults to `bfloat16`.
- `--prefix-cache` / `--no-prefix-cache`: Enables/disables vLLM prefix caching.
- `--chunked-prefill` / `--no-chunked-prefill`: Enables/disables chunked prefill.
- `--fast-boot` / `--no-fast-boot`: `--fast-boot` enforces eager mode; `--no-fast-boot` allows compiled/CUDA graph behavior.
- `--max-model-len`: Defaults to `8192`.
- `--max-batch-tokens`: Maps to vLLM `--max-num-batched-tokens`; defaults to `4096`.
- `--max-seqs`: Maps to vLLM `--max-num-seqs`; defaults to `32`.
- `--concurrent-inputs`: Modal per-container concurrency; defaults to `64`.
- `--mm-max-pixels`: Maximum image pixels passed to Qwen-VL processor; defaults to `512 * 28 * 28`.
- `--request-timeout`: Per-request HTTP timeout used by the load tester.
- `--min-pause` / `--max-pause`: Synthetic user think-time bounds between requests.
- `--seed`: Random seed for reproducible workload selection.
- `--health-timeout`: Maximum time to wait for the deployed endpoint to pass `/health`.
- `--url`: Reuse an existing endpoint instead of deploying a new app.
- `--deploy-only`: Deploy and health-check without running the load test.

Load/workload flags:

- `--mode`: `text`, `long`, `image`, or `mixed`.
- `--users`: Target concurrent synthetic users.
- `--duration`: Load-test duration in seconds.
- `--ramp-up`: User ramp-up duration in seconds.
- `--max-tokens`: Maximum generated output tokens.
- `--seed`: Random seed for reproducible workload selection.

The runner refuses experiments above 8 total GPUs:

```text
total_gpus = (gpu_count or tp) * replicas
```

## Allowed And Disallowed Changes

Allowed tuning surface for experiments:

- Number of replicas.
- GPU count and GPU type, within assignment budget.
- Tensor parallel size.
- `max_num_seqs`.
- `max_num_batched_tokens`.
- `max_model_len`, as long as official prompts are not rejected.
- Prefix caching on/off.
- Chunked prefill on/off.
- Eager vs compiled mode.
- Modal concurrent input limit.
- Max output tokens only when the track rules allow it.
- Image pixel budget only if answer quality remains acceptable.
- Ramp-up strategy for private experiments.
- Warmup strategy.

Do not change for final submissions unless a special track explicitly allows it:

- Model family.
- Official prompt set in `prompts.json`.
- Scoring script semantics.
- Quality/evaluation rules.
- Workload mode for the submitted track.

If modifying code, preserve the student-facing contract in the README and runbook. Prefer improvements that make the benchmark more reliable, observable, or easier to operate without invalidating leaderboard comparability.

## Track-Specific Guidance

Multimodal Product Track:

- Use `--mode mixed`.
- Recommended cap: up to 4 H100 GPUs.
- Prefer eager mode (`--fast-boot`) unless evidence shows compiled mode works for mixed traffic.
- Protect image and long-prompt behavior; do not tune only for text.
- Baseline worth comparing against: 2 replicas, `max-seqs=32`, `max-batch-tokens=4096`, 100 users, 0% errors.

Text Speed Track:

- Use `--mode text`.
- Recommended cap: up to 4 H100 GPUs.
- Compiled mode (`--no-fast-boot`) can materially improve text-only throughput after longer startup/warmup.
- Baseline worth comparing against: 4 replicas, `max-seqs=32`, `max-batch-tokens=4096`, 400 users, `--no-fast-boot`.

Optional Boss Fight:

- Up to 8 H100 GPUs if quota and cost budget allow.
- Expect non-GPU bottlenecks at high users: web concurrency, queues, request timeouts, cold starts, and endpoint limits.
- Do not treat higher aggregate throughput as a win if error rate rises enough to reduce goodput.

## Metrics And Scoring

The starter load tester writes JSON under:

```text
starter_code/results_infertutor/
```

Key result fields:

- `ttft_p95_ms`: p95 time from request start to first streamed content chunk.
- `itl_p95_ms`: p95 inter-content-chunk latency.
- `latency_p95_ms`: p95 total request latency.
- `aggregate_stream_chunks_per_s`: Aggregate streamed content chunks per second.
- `requests_per_s`: Completed requests per second.
- `successes_per_s`: Successful completed requests per second.
- `error_rate`: Failed requests divided by total requests.
- `errors_by_type`: Failure breakdown by error category.
- `errors_by_status`: Failure breakdown by HTTP status code.
- `last_error`: Most recent captured failure detail for quick diagnosis.

Local scoring in `score_infertutor.py`:

```text
goodput = aggregate_stream_chunks_per_s * (1 - error_rate)
score = goodput * users / (ttft_p95_seconds * itl_p95_seconds * total_gpus)
```

The README’s capstone formula additionally includes `quality_pass_rate`; final external evaluators may tokenize outputs instead of counting streamed chunks. Keep outputs useful and do not optimize by making responses empty, broken, or low-quality.

## Minimum Experiment Matrix

A complete engineering submission should include at least:

- Baseline: 1 replica, default starter config.
- More users: find where p95 latency bends.
- Prefix caching: on vs off.
- Chunked prefill: on vs off.
- Batch knobs: `seq32/b4096` vs at least one wider config.
- Scale out: 1 replica vs 2 or 4 replicas.
- Final: best clean run.

Keep the exact command, result JSON path, key metrics, and interpretation for every experiment.

## Optimization Heuristics

If TTFT p95 is high:

- Try lower `--max-batch-tokens`.
- Enable `--prefix-cache`.
- Enable `--chunked-prefill`.
- Reduce `--mm-max-pixels` for multimodal only if quality remains acceptable.
- Add replicas.
- Warm containers before the final measured run.
- Check for cold starts and long prompts queueing ahead of short prompts.

If ITL p95 is high:

- Try lower `--max-seqs`.
- Try lower `--max-batch-tokens`.
- Use compiled mode for text-only runs.
- Reduce `--concurrent-inputs`.
- Check whether prefills are interrupting decode.

If throughput is low:

- Increase users until GPU saturation, watching p95 latency.
- Add replicas if one GPU/container is saturated.
- Increase `--max-seqs` carefully.
- Try compiled mode for text-only.
- Confirm errors are not hiding failed goodput.

If errors appear:

- Reduce users.
- Slow ramp-up.
- Reduce `--concurrent-inputs`.
- Add replicas if capacity is insufficient.
- Increase request timeout in direct load-test experiments if appropriate.
- Inspect Modal logs.

## Editing Guidelines For Agents

Before making changes:

- Read `README.md` and `starter_code/README.md`.
- Inspect the script being modified and verify actual flags/defaults from code.
- Check `git status --short` and avoid overwriting unrelated user changes.

When modifying experiment behavior:

- Keep `run_infertutor_experiment.py` as the main user interface.
- Keep generated app patching deterministic and easy to inspect.
- Fail fast if template patching assumptions no longer match `modal_infertutor_app.py`.
- Keep `load_test_infertutor.py` compatible with the OpenAI chat completions streaming format.
- Keep result JSON schema backward compatible unless updating `score_infertutor.py` and docs together.
- Do not silently change scoring incentives.

When modifying docs:

- Update Markdown sources first.
- Regenerate PDFs with `python3 render_pdfs.py` if assignment/runbook PDFs must reflect the change.
- Keep root `README.md`, `starter_code/README.md`, and this file consistent for commands and flags.

When modifying Modal/vLLM settings:

- Consider cost and startup time.
- Preserve cleanup instructions.
- Keep the Hugging Face secret name contract unless all docs and code are changed together.
- Avoid hardcoding local-only credentials, absolute user paths, or private endpoints.

## Validation Checklist

For documentation-only changes:

```bash
python3 -m py_compile render_pdfs.py starter_code/*.py
```

For automated regression checks on the benchmark tooling:

```bash
python3 -m unittest tests.test_infertutor_tools
```

If Markdown sources for PDFs changed:

```bash
python3 render_pdfs.py
```

For local script sanity:

```bash
cd starter_code
python3 run_infertutor_experiment.py --help
python3 load_test_infertutor.py --help
python3 score_infertutor.py --help
```

For scoring validation when results exist:

```bash
cd starter_code
python3 score_infertutor.py results_infertutor
```

For live infrastructure validation, run the smoke test and require zero errors before larger experiments.

## Submission Checklist

A final student submission should contain:

- Final benchmark JSON.
- Exact command used for the final run.
- One-page engineering report.
- Table of at least five experiments.
- Short explanation of the best configuration.
- One surprising failure or tradeoff.

The repository now includes `starter_code/generate_submission_artifacts.py` to bootstrap these files from benchmark JSON outputs. Review and refine the generated report before submitting.

The report should answer:

- Final score.
- Best TTFT p95.
- Best ITL p95.
- Best throughput.
- Total GPU count.
- Optimization that helped the most.
- Optimization that failed or surprised the team.
- What to try next with more time.

## Cost And Cleanup Rules

Modal GPU containers can continue costing money while active or warm. Always include cleanup in runbooks and final instructions:

```bash
modal app list
modal app stop <APP_ID_OR_NAME>
```

The rough cost model is:

```text
Cost = GPU_count * runtime_hours * price_per_GPU_hour
```

Cold starts, model downloads, and compilation time count. Compiled-mode experiments can cost more because startup and graph capture take longer.

## Common Pitfalls

- Running from the repository root and then wondering why `requirements.txt` or `results_infertutor` is not found; most starter commands should run from `starter_code`.
- Using `python` on systems where only `python3` is installed.
- Forgetting `modal secret create huggingface HF_TOKEN=...`.
- Comparing text-only compiled results against mixed-workload eager results as if they were the same track.
- Raising users until throughput improves while ignoring error rate and p95 latency.
- Increasing `max_num_batched_tokens` so much that prefill throughput improves but decode stutter gets worse.
- Editing `prompts.json` and invalidating final comparisons.
- Forgetting to stop Modal apps after experiments.
