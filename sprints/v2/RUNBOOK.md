# Sprint v2 Runbook - Submission Campaign

This runbook covers the manual operator work that remains to make the capstone submission complete once the code paths are ready.

## Goal

Produce a final bundle with:

- at least five real benchmark result JSON files
- one explicitly selected final run
- finalized engineering commentary

## Recommended Experiment Sequence

Run from `starter_code/` with the project virtual environment active.

1. Smoke validation

```bash
./../.venv/bin/python run_infertutor_experiment.py \
  --label smoke \
  --gpu-type H100 \
  --replicas 1 \
  --mode text \
  --users 5 \
  --duration 30 \
  --ramp-up 5 \
  --max-tokens 64
```

2. Single-GPU text baseline

```bash
./../.venv/bin/python run_infertutor_experiment.py \
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

3. Two-replica mixed baseline

```bash
./../.venv/bin/python run_infertutor_experiment.py \
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

4. Four-replica text throughput sweep

```bash
./../.venv/bin/python run_infertutor_experiment.py \
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

5. Prefix-cache comparison

```bash
./../.venv/bin/python run_infertutor_experiment.py \
  --label text-no-prefix \
  --gpu-type H100 \
  --replicas 1 \
  --no-prefix-cache \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode text \
  --users 50 \
  --duration 60 \
  --ramp-up 15 \
  --max-tokens 96
```

6. Chunked-prefill comparison

```bash
./../.venv/bin/python run_infertutor_experiment.py \
  --label mixed-no-chunked \
  --gpu-type H100 \
  --replicas 2 \
  --no-chunked-prefill \
  --max-seqs 32 \
  --max-batch-tokens 4096 \
  --mode mixed \
  --users 100 \
  --duration 90 \
  --ramp-up 25 \
  --max-tokens 96
```

## Result Naming and Selection

- Keep every generated JSON under `starter_code/results_infertutor/`.
- Score the directory before choosing the final run:

```bash
./../.venv/bin/python score_infertutor.py results_infertutor
```

- Pick the final JSON intentionally. Do not rely only on sorting if a lower-score run had better multimodal behavior or fewer operational caveats.

## Commentary File

Create a JSON file named for the chosen final run, for example `commentary-final.json`:

```json
{
  "best_optimization": "Explain the strongest improvement that held up across repeated runs.",
  "surprising_failure_or_tradeoff": "Explain the failed optimization or unexpected tradeoff.",
  "next_step": "Explain the next experiment you would run with more time."
}
```

## Final Bundle Command

```bash
./../.venv/bin/python generate_submission_artifacts.py results_infertutor \
  --final-file <FINAL_RESULT_JSON> \
  --commentary-file <COMMENTARY_JSON>
```

## Draft Mode

Use draft mode only for local formatting checks:

```bash
./../.venv/bin/python generate_submission_artifacts.py results_infertutor --allow-draft
```

Draft mode is not submission complete.
