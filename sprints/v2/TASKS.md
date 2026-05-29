- [x] Task 1: Capture the current artifact generator and submission checklist behavior (P0)
  - Acceptance: Current bundle outputs, required submission fields, and known gaps are recorded before implementation.
  - Files: `starter_code/generate_submission_artifacts.py`, `README.md`, `InferTutor_Arena_Capstone.md`
  - Completed: 2026-05-29 — Audited the generator against the README submission checklist and confirmed the initial gaps: placeholder commentary, single-run acceptance, and missing final-run provenance enforcement.

- [x] Task 2: Add tests that fail when submission bundles contain `TODO` placeholders or fewer than five experiments (P0)
  - Acceptance: Test coverage exists for minimum experiment count, placeholder rejection, and explicit final-file selection.
  - Files: `tests/test_infertutor_tools.py`
  - Completed: 2026-05-29 — Added unit tests for experiment-count enforcement, placeholder rejection, draft mode, commentary validation, provenance validation, commentary-file loading, and explicit final-file selection.

- [x] Task 3: Enforce submission completeness in artifact generation (P0)
  - Acceptance: Bundle generation refuses incomplete evidence packs unless an explicit draft mode is chosen and documented.
  - Files: `starter_code/generate_submission_artifacts.py`
  - Completed: 2026-05-29 — Added completeness enforcement with a five-experiment minimum and an explicit `--allow-draft` escape hatch for incomplete local previews.

- [x] Task 4: Add support for injecting finalized commentary into the engineering report from structured inputs (P0)
  - Acceptance: The generator can consume finalized narrative fields instead of hardcoded `TODO` lines.
  - Files: `starter_code/generate_submission_artifacts.py`, `starter_code/result_schema.py`
  - Completed: 2026-05-29 — Added `submission_commentary` validation plus an optional `--commentary-file` JSON input that is merged into the final bundle and used to render placeholder-free reports.

- [x] Task 5: Add provenance validation for the final benchmark selection and final command output (P1)
  - Acceptance: Selected final run must contain runner command, app name, and source-control fields before the bundle is emitted.
  - Files: `starter_code/result_schema.py`, `starter_code/generate_submission_artifacts.py`
  - Completed: 2026-05-29 — Added provenance validation for the selected final run and factored explicit final-file resolution into a tested helper.

- [x] Task 6: Create an operator runbook for the five-experiment campaign and final submission assembly (P1)
  - Acceptance: The repo includes a concrete experiment sequence, result naming guidance, and final bundle generation steps.
  - Files: `README.md` or a new runbook under `sprints/v2/`
  - Completed: 2026-05-29 — Added bundle-generation documentation to the README files and created `sprints/v2/RUNBOOK.md` with a concrete six-run experiment campaign and final assembly steps.

- [ ] Task 7: Execute the experiment campaign and generate the final submission bundle (P1)
  - Acceptance: `starter_code/results_infertutor/` contains five-plus real runs and the final bundle is generated from those results.
  - Files: `starter_code/results_infertutor/`, generated `submission_bundle/`
