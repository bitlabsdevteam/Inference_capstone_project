- [x] Task 1: Capture the current runtime observability baseline and failure modes (P0)
  - Acceptance: Existing health behavior, startup diagnostics, and result error categories are documented before changes begin.
  - Files: `starter_code/modal_infertutor_app.py`, `starter_code/run_infertutor_experiment.py`, `starter_code/load_test_infertutor.py`
  - Completed: 2026-05-29 — Audited the gap between simple `/health` polling and operator-usable diagnostics, then used that audit to drive smoke metadata and runtime log changes.

- [x] Task 2: Add tests for structured smoke and diagnostic metadata in result files (P0)
  - Acceptance: Tests fail first for missing smoke metadata, richer health semantics, and new diagnostic fields.
  - Files: `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added tests for smoke metadata propagation, schema validation, redacted result payloads, and scoreboard-facing smoke visibility.

- [x] Task 3: Add structured logging around vLLM startup, readiness, and fatal startup exits (P0)
  - Acceptance: Startup failures produce machine-readable log lines with enough context to debug container boot issues.
  - Files: `starter_code/modal_infertutor_app.py`
  - Completed: 2026-05-29 — Added JSON runtime events for serve invocation, vLLM startup, startup failure, and ready state, with API-key redaction for logged commands.

- [x] Task 4: Persist functional smoke outcomes and richer error taxonomy in benchmark results (P0)
  - Acceptance: Result JSON captures smoke success/failure and materially useful error categories beyond the current counters.
  - Files: `starter_code/run_infertutor_experiment.py`, `starter_code/load_test_infertutor.py`, `starter_code/result_schema.py`
  - Completed: 2026-05-29 — The runner now captures structured smoke results and the load tester persists them into `smoke_check` alongside the existing error counters and summaries.

- [x] Task 5: Add operator-facing diagnostics to scoring or reporting tools where appropriate (P1)
  - Acceptance: Local leaderboard or report tooling surfaces the key diagnostic fields without overwhelming normal output.
  - Files: `starter_code/score_infertutor.py`, `starter_code/generate_submission_artifacts.py`
  - Completed: 2026-05-29 — The leaderboard now shows smoke status and generated submission reports include smoke outcome, status code, and latency context.

- [x] Task 6: Document post-deploy validation and failure triage steps (P1)
  - Acceptance: Operators have a concise checklist for deploy, smoke, diagnose, and retry decisions.
  - Files: `README.md`, `architecture.md`
  - Completed: 2026-05-29 — Added post-deploy triage guidance and smoke/result metadata documentation to the README and architecture guide.
