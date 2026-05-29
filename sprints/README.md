# InferTutor Sprint Roadmap

This roadmap splits the validated gaps in the current repository into sequential sprints that move the project from "starter harness complete" to "submission complete" and then to "production-grade".

The roadmap is designed for two workflows:

1. `/prd` owns sprint definition and backlog shape.
2. `/dev` picks the first unchecked task from the latest sprint and implements it with tests and security checks.

## Sprint Order

### `v1` Submission Gate Alignment

Close the highest-risk mismatches between documentation, local validation, and the benchmark harness so the repository can honestly claim deploy readiness.

### `v2` Submission Evidence Pack

Produce the missing submission assets: five-plus real experiments, a complete engineering report, a final benchmark choice, and artifact-level validation.

### `v3` Endpoint Security and Access Control

Harden the exposed inference endpoint with authentication, secret handling, and safer provenance/logging behavior.

### `v4` Observability and Runtime Safety

Add production-grade health, smoke, structured logs, and operator diagnostics beyond the current `/health` poll.

### `v5` Reproducibility and CI Quality Gates

Lock down dependency drift, add stronger automated checks, and align the local harness with the README's quality and scoring story.

All planned sprints are now materialized under `sprints/v1` through `sprints/v5`. `v1`, `v4`, and `v5` are complete locally; `v2` is code-complete except for live benchmark evidence generation; `v3` is code-complete except for live auth verification.

## Gap Mapping

| Validated gap | Sprint |
|---|---|
| Generated report still contains `TODO` placeholders | `v2` |
| Fewer than five experiments exist in `starter_code/results_infertutor/` | `v2` |
| README scoring formula differs from implementation | `v1`, `v5` |
| Full preflight/deploy readiness not satisfied in practice | `v1` |
| Public unauthenticated inference endpoint | `v3` |
| Missing structured logs, metrics, smoke checks, runtime diagnostics | `v4` |
| Unpinned local dependencies and weak CI gates | `v1`, `v5` |

## Execution Notes

- Complete `v1` and `v2` before claiming the project is submission-ready.
- Complete `v3` through `v5` before calling the service production-grade.
- Manual benchmark runs remain part of the plan because live Modal validation requires credentials and spend.
