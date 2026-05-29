# Sprint v5 PRD - Reproducibility and CI Quality Gates

## Sprint Overview

Sprint `v5` makes the repository defensible as an engineering deliverable by tightening reproducibility, local validation, and CI quality gates. The goal is to reduce trust-based review by making common regressions and hygiene failures fail automatically.

## Goals

- Keep dependency behavior reproducible locally and in CI.
- Enforce source hygiene around generated artifacts, raw endpoint leakage, and unsafe subprocess usage.
- Expand validation so dependency integrity and quality checks run from one entrypoint.
- Reflect the stronger validation flow in CI.

## User Stories

- As a maintainer, I want the repository to reject common hygiene regressions automatically so that private endpoints and generated artifacts do not slip into source control.
- As a reviewer, I want CI to exercise the same validation flow that developers run locally so that green checks are meaningful.
- As an operator, I want dependency integrity and result-schema semantics to be verified before I trust a run.

## Technical Architecture

- Stack: Python validation scripts, GitHub Actions, pinned dependencies, unittest-based regression tests.
- Primary components:
  - `scripts/validate_repo.sh`
  - `scripts/check_repo_hygiene.py`
  - `.github/workflows/quality.yml`
  - `starter_code/requirements.txt`
  - `tests/test_infertutor_tools.py`

```text
Developer / CI
  -> install pinned deps
  -> unittest suite
  -> repo hygiene checks
  -> pip dependency integrity check
  -> preflight
```

## Out of Scope

- Live GPU load tests inside CI.
- External security scanners that require extra network/tool bootstrap.
- Final submission evidence generation.

## Dependencies

- Sprint `v1` through `v4` local code changes completed.
- Modal credentials still required separately for live verification tasks outside CI.
