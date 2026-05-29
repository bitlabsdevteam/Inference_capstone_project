# Sprint v1 PRD - Submission Gate Alignment

## Sprint Overview

Sprint `v1` aligns the repository's validation, dependency management, and benchmark semantics with what the README claims today. The output of this sprint should make local readiness checks trustworthy and remove the highest-risk doc-to-code mismatches before any final submission runs.

## Goals

- Make local preflight and validation accurately reflect deploy readiness requirements.
- Reduce reproducibility drift by pinning local dependencies and documenting the supported environment.
- Add a functional inference smoke check after deploy so success means more than `/health`.
- Align local scoring and result metadata with the documented distinction between local chunk-based scoring and official evaluation.

## User Stories

- As a capstone submitter, I want preflight to fail for real deploy blockers so that I do not discover setup issues during a paid benchmark run.
- As a reviewer, I want the README and scorer behavior to agree so that reported scores are interpretable.
- As an operator, I want a post-deploy functional smoke test so that I know the endpoint can answer a real request before load starts.

## Technical Architecture

- Stack: Python 3.11+, Modal CLI, Modal Python SDK, httpx, rich, vLLM, Markdown docs.
- Primary components:
  - `starter_code/preflight_infertutor.py`
  - `scripts/validate_repo.sh`
  - `starter_code/run_infertutor_experiment.py`
  - `starter_code/load_test_infertutor.py`
  - `starter_code/result_schema.py`
  - `README.md`
  - `starter_code/requirements.txt`

```text
Developer shell
  -> preflight_infertutor.py
      -> dependency checks
      -> command checks
      -> auth checks
  -> run_infertutor_experiment.py
      -> modal deploy
      -> functional smoke check
      -> load_test_infertutor.py
          -> result_schema.py-compatible JSON
  -> README / docs
      -> explain local score vs official score
```

Data flow:

1. Validate environment and Modal readiness locally.
2. Deploy generated Modal app.
3. Run functional smoke request against `/v1/chat/completions`.
4. Start load test only after smoke success.
5. Persist result JSON with clarified provenance and scoring metadata.

## Out of Scope

- Running the full five-experiment campaign.
- Adding endpoint authentication.
- Adding structured observability pipelines.
- Expanding CI beyond minimal changes needed for v1 correctness.

## Dependencies

- Access to the existing repository and starter scripts.
- A supported Python environment.
- Modal and Hugging Face credentials for live verification.
