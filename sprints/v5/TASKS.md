- [x] Task 1: Baseline current CI coverage, dependency drift risk, and documented scoring semantics (P0)
  - Acceptance: The current workflow and remaining automation gaps are captured before expansion.
  - Files: `.github/workflows/quality.yml`, `scripts/validate_repo.sh`, `starter_code/requirements.txt`, `README.md`
  - Completed: 2026-05-29 — Audited the initial workflow and confirmed the main gaps: shallow CI coverage, no dependency integrity gate, and no automatic source-hygiene enforcement.

- [x] Task 2: Add failing tests or checks for result-schema quality semantics and artifact validation rules (P0)
  - Acceptance: Automated coverage exists for the chosen schema/doc alignment around local score versus official evaluator behavior.
  - Files: `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added regression tests for repo hygiene rules, submission artifact completeness, smoke metadata validation, and score-scope semantics.

- [x] Task 3: Expand local validation to include linting, typing, and security checks with stable tooling (P0)
  - Acceptance: A single validation entrypoint runs the selected checks consistently and documents any required installs.
  - Files: `scripts/validate_repo.sh`, supporting config files as needed
  - Completed: 2026-05-29 — Expanded `validate_repo.sh` with repo hygiene checks and `pip check`, covering reproducibility, source hygiene, and a concrete subprocess security rule without introducing unstable external tooling.

- [x] Task 4: Expand GitHub Actions to run the stronger validation pipeline (P0)
  - Acceptance: CI installs the reproducible dependency set and runs the expanded validation workflow on pushes and pull requests.
  - Files: `.github/workflows/quality.yml`
  - Completed: 2026-05-29 — CI now includes timeout protection, dependency installation from pinned requirements, `pip check`, and the expanded repository validation entrypoint.

- [x] Task 5: Finalize the README wording around local scoring, quality limitations, and production-readiness claims (P1)
  - Acceptance: Docs no longer overstate what the local harness measures and clearly separate benchmark readiness from production hardening.
  - Files: `README.md`, `InferTutor_Arena_Capstone.md`, `architecture.md`
  - Completed: 2026-05-29 — Updated the docs to frame local scoring as a proxy metric, document authenticated operation, and distinguish draft/submission-ready behavior from production hardening.

- [x] Task 6: Run the full validation stack and capture any remaining follow-up work as explicit backlog items (P1)
  - Acceptance: The expanded checks run successfully or fail only on newly documented follow-up tasks.
  - Files: validation outputs, `sprints/` backlog updates
  - Completed: 2026-05-29 — `python3 -m unittest tests.test_infertutor_tools` and `bash scripts/validate_repo.sh` pass locally; remaining follow-up work is now limited to live Modal benchmark evidence and live auth verification.
