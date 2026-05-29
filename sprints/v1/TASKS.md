- [x] Task 1: Baseline the current validation and dependency flow (P0)
  - Acceptance: Current preflight, validation script, requirements, and README claims are summarized in sprint notes or commit context before changes start.
  - Files: `starter_code/preflight_infertutor.py`, `scripts/validate_repo.sh`, `starter_code/requirements.txt`, `README.md`
  - Completed: 2026-05-29 — Audited the current validation path, dependency versions, and README scoring/deploy claims to ground the sprint backlog in repo evidence.

- [x] Task 2: Add tests for the desired preflight behavior and supported environment checks (P0)
  - Acceptance: Tests fail first for missing `modal` module/CLI handling, auth requirement behavior, and any new supported-version checks.
  - Files: `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added unit coverage for Python version failure, missing module install hints, missing Modal CLI guidance, and functional smoke-check behavior.

- [x] Task 3: Pin local Python dependencies and update setup docs to match the pinned toolchain (P0)
  - Acceptance: `starter_code/requirements.txt` uses exact versions or a documented reproducible strategy, and docs describe the supported Python path consistently.
  - Files: `starter_code/requirements.txt`, `README.md`, `starter_code/README.md`
  - Completed: 2026-05-29 — Pinned the starter dependencies to the versions installed in the project venv and updated the docs to use the repo virtual environment explicitly.

- [x] Task 4: Tighten preflight and repository validation to report real deploy blockers clearly (P0)
  - Acceptance: Preflight distinguishes required vs optional checks correctly and emits actionable failures for missing SDK, CLI, or auth.
  - Files: `starter_code/preflight_infertutor.py`, `scripts/validate_repo.sh`
  - Completed: 2026-05-29 — Improved preflight error messaging for missing Python packages and missing Modal CLI while preserving optional auth behavior unless explicitly required.

- [x] Task 5: Add a post-deploy functional smoke request before the load test begins (P0)
  - Acceptance: The runner issues a minimal `/v1/chat/completions` request after `/health`, aborts on failure, and has automated test coverage.
  - Files: `starter_code/run_infertutor_experiment.py`, `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added a non-streaming chat-completions smoke check between readiness and load generation and covered it with unit tests.

- [x] Task 6: Add result-schema fields or documentation needed to explain local score vs official evaluator score (P1)
  - Acceptance: Local chunk-based scoring is explicitly labeled, and schema/docs no longer imply that `quality_pass_rate` is already measured locally.
  - Files: `starter_code/result_schema.py`, `starter_code/load_test_infertutor.py`, `README.md`, `InferTutor_Arena_Capstone.md`
  - Completed: 2026-05-29 — Updated the top-level docs and assignment source to call out that starter-code scoring is chunk-based local tuning guidance, not the full official evaluator score.

- [x] Task 7: Re-run local validation and record the remaining external blockers for live deploy verification (P1)
  - Acceptance: Targeted tests and repo validation pass locally; any remaining live-only blockers are limited to credentials or external service state.
  - Files: `scripts/validate_repo.sh`, `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — `python3 -m unittest tests.test_infertutor_tools` and `bash scripts/validate_repo.sh` pass locally; the only remaining live blocker is missing Modal token authentication in this environment.
