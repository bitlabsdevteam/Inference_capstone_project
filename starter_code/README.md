# InferTutor Arena Starter Code

This folder contains the starter code for the capstone.

The goal is to remove infrastructure friction. You should spend your time on inference-engineering decisions, not on figuring out how to deploy vLLM.

## Files

| File | Purpose |
|---|---|
| `modal_infertutor_app.py` | Modal app that launches vLLM as an OpenAI-compatible server |
| `run_infertutor_experiment.py` | One-command deploy + load-test runner |
| `load_test_infertutor.py` | Async streaming load tester for text, long, image, and mixed workloads |
| `score_infertutor.py` | Summarizes result JSONs and computes a leaderboard score |
| `generate_submission_artifacts.py` | Builds submission-ready artifacts from saved benchmark JSON files |
| `result_schema.py` | Shared validation and scoring utilities for result JSON files |
| `prompts.json` | Fixed official prompt set |
| `requirements.txt` | Local Python dependencies |

## Quick Start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
modal token new
modal secret create huggingface HF_TOKEN=<YOUR_HF_TOKEN>
modal secret create infertutor-auth ENDPOINT_API_KEY=<YOUR_ENDPOINT_API_KEY>
export ENDPOINT_API_KEY=<YOUR_ENDPOINT_API_KEY>
```

Smoke test:

```bash
python run_infertutor_experiment.py \
  --label smoke \
  --gpu-type H100 \
  --replicas 1 \
  --mode text \
  --users 5 \
  --duration 30 \
  --ramp-up 5 \
  --max-tokens 64
```

Main multimodal baseline:

```bash
python run_infertutor_experiment.py \
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

Text speed baseline:

```bash
python run_infertutor_experiment.py \
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
python score_infertutor.py results_infertutor
```

Run local preflight checks before deploying:

```bash
./.venv/bin/python preflight_infertutor.py
```

Require Modal authentication for deploy readiness:

```bash
./.venv/bin/python preflight_infertutor.py --require-modal-auth
```

Require local endpoint auth configuration too:

```bash
./.venv/bin/python preflight_infertutor.py --require-modal-auth --require-endpoint-auth
```

Bootstrap Modal auth plus the Hugging Face and endpoint auth secrets from environment variables:

```bash
MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=... HF_TOKEN=... ENDPOINT_API_KEY=... python bootstrap_infertutor_env.py
```

Run the repository validation suite:

```bash
bash ../scripts/validate_repo.sh
```

Require deploy readiness from the validation suite:

```bash
bash ../scripts/validate_repo.sh --require-modal-auth
```

Generate a submission bundle from result JSON files:

```bash
python generate_submission_artifacts.py results_infertutor \
  --final-file <FINAL_RESULT_JSON> \
  --commentary-file <COMMENTARY_JSON>
```

Use `--allow-draft` only for incomplete local previews. A submission-ready bundle requires at least five experiments plus finalized commentary and final-run provenance.

Stop Modal apps when done:

```bash
modal app list
modal app stop <APP_ID_OR_NAME>
```
