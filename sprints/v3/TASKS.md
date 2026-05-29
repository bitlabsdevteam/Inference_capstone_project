- [x] Task 1: Baseline the current public endpoint and provenance exposure paths (P0)
  - Acceptance: Current request flow, headers, and result-file exposure points are identified before auth changes begin.
  - Files: `starter_code/modal_infertutor_app.py`, `starter_code/run_infertutor_experiment.py`, `starter_code/load_test_infertutor.py`
  - Completed: 2026-05-29 — Audited the starter endpoint flow and confirmed the main risks: public unauthenticated inference traffic and raw endpoint persistence in benchmark results.

- [x] Task 2: Add failing tests for authenticated request handling in the runner and load tester (P0)
  - Acceptance: Tests cover missing token, provided token, and backward-compatible draft/local behavior where intended.
  - Files: `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added tests for bearer-auth headers, endpoint auth env checks, bootstrap secret creation, vLLM API-key configuration, and result redaction behavior.

- [ ] Task 3: Implement bearer-token authentication for inference traffic (P0)
  - Acceptance: The deployed service rejects unauthorized inference requests and accepts authorized ones.
  - Files: `starter_code/modal_infertutor_app.py`

- [x] Task 4: Thread auth configuration through preflight, runner, smoke checks, and load test requests (P0)
  - Acceptance: Local tooling can source auth config and attach the required header automatically.
  - Files: `starter_code/preflight_infertutor.py`, `starter_code/run_infertutor_experiment.py`, `starter_code/load_test_infertutor.py`
  - Completed: 2026-05-29 — Added `ENDPOINT_API_KEY` handling to preflight, smoke checks, load-test headers, and local bootstrap flow.

- [x] Task 5: Redact or minimize sensitive endpoint details in persisted artifacts and console output (P1)
  - Acceptance: Saved results and generated reports avoid leaking more endpoint detail than required for auditability.
  - Files: `starter_code/load_test_infertutor.py`, `starter_code/generate_submission_artifacts.py`
  - Completed: 2026-05-29 — Result JSON now stores a redacted endpoint URL and excludes auth input from persisted config while submission bundles continue to rely on provenance and app naming rather than raw URLs.

- [x] Task 6: Document secure operator setup and token rotation workflow (P1)
  - Acceptance: Docs explain how to create, pass, rotate, and validate auth secrets.
  - Files: `README.md`, `Modal_vLLM_Runbook.md`
  - Completed: 2026-05-29 — Updated the setup docs and runbook to require `infertutor-auth`, local `ENDPOINT_API_KEY`, and authenticated preflight/bootstrap flows.
