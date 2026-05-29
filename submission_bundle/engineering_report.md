# InferTutor Engineering Report

## Final Run

- Track: Text Speed Track
- Final result file: `smoke_text_5u_1779945158.json`
- Final score: `37988`
- Best TTFT p95 observed: `674.8 ms`
- Best ITL p95 observed: `23.2 ms`
- Best throughput observed: `119.1 chunks/s`
- Total GPU count: `1`
- Final error rate: `0.0%`
- Experiment count included: `1`
- Functional smoke check: `unknown`

## Final Command

```bash
python run_infertutor_experiment.py --label smoke --gpu-type H100 --replicas 1 --mode text --users 5 --duration 30 --ramp-up 5 --max-tokens 64
```

## Best Configuration

- Mode: `text`
- Users: `5`
- Total GPUs: `1`
- TTFT p95: `674.8 ms`
- ITL p95: `23.2 ms`
- Throughput: `119.1 chunks/s`

## Provenance

- Modal app name: `infertutor-smoke`
- Git commit: `71fe9f064d0a6b6c350d2ebc794a0878558269a9`
- Git branch: `main`
- Git worktree dirty: `True`
- Smoke status code: `unknown`
- Smoke latency: `unknown`

## Required Commentary

- Which optimization helped the most: TODO
- Which optimization failed or surprised you: TODO
- What would you try next with more time: TODO

## Submission Checks

- At least five experiments included: `no`
- Draft mode: `yes`

## Experiment Matrix

| file | mode | users | gpus | err% | TTFT p95 | ITL p95 | throughput | req/s | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| smoke_text_5u_1779945158.json | text | 5 | 1 | 0.0 | 674.8 ms | 23.2 ms | 119.1 | 1.86 | 37988 |

