# Sprint v4 PRD - Observability and Runtime Safety

## Sprint Overview

Sprint `v4` upgrades the service from a benchmark-only deployment to an operable runtime with meaningful diagnostics. The sprint adds functional smoke metadata, structured runtime logs, richer leaderboard context, and operator-facing triage guidance.

## Goals

- Emit structured runtime logs that are useful during startup and benchmark failures.
- Distinguish basic liveness from functional serving readiness.
- Persist functional smoke outcomes into benchmark results.
- Surface diagnostic context in local scoring and operator docs.

## User Stories

- As an operator, I want to know whether the service merely booted or actually answered a tutor request before load began.
- As a debugger, I want startup failures to emit machine-readable events so that container boot issues are traceable.
- As a benchmark runner, I want persisted smoke metadata and error context in the result files so that I can compare runs without opening raw logs.

## Technical Architecture

- Stack: Modal app lifecycle hooks, Python logging, smoke utilities, result metadata.
- Primary components:
  - `starter_code/modal_infertutor_app.py`
  - `starter_code/run_infertutor_experiment.py`
  - `starter_code/load_test_infertutor.py`
  - `starter_code/result_schema.py`
  - `starter_code/score_infertutor.py`
  - `tests/test_infertutor_tools.py`

```text
Modal container startup
  -> structured runtime events
  -> vLLM launch
Runner
  -> /health
  -> functional smoke request
  -> load test
Result JSON
  -> smoke_check
  -> error summaries
Leaderboard/report
  -> smoke visibility
```

## Out of Scope

- External monitoring vendors.
- Distributed tracing systems.
- Live alert delivery or pager integration.

## Dependencies

- Sprint `v1` completed.
- Sprint `v3` local auth wiring completed.
- Live Modal access for final runtime verification.
