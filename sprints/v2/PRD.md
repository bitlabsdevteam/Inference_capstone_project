# Sprint v2 PRD - Submission Evidence Pack

## Sprint Overview

Sprint `v2` converts the corrected harness into a submission-ready evidence package. The sprint focuses on generating enough real benchmark evidence, validating artifact completeness, and removing all placeholder content from the final submission bundle.

## Goals

- Produce and preserve at least five real benchmark result files.
- Generate a complete submission bundle with no placeholder `TODO` content.
- Allow explicit selection of the final benchmark run and verify its provenance.
- Fail bundle generation when submission requirements are not met.

## User Stories

- As a capstone submitter, I want the bundle generator to tell me whether the submission is actually complete so that I do not submit placeholders.
- As a reviewer, I want the engineering report and experiment table to be based on real runs so that the claims are defensible.
- As an operator, I want to select the final run intentionally rather than relying on score sorting alone.

## Technical Architecture

- Stack: Python, Markdown artifact generation, local JSON result validation.
- Primary components:
  - `starter_code/generate_submission_artifacts.py`
  - `starter_code/result_schema.py`
  - `starter_code/score_infertutor.py`
  - `tests/test_infertutor_tools.py`
  - `starter_code/results_infertutor/`

```text
benchmark results (*.json)
  -> result_schema.py validation
  -> generate_submission_artifacts.py
      -> final_benchmark.json
      -> engineering_report.md
      -> experiment_table.md
      -> final_command.sh
      -> submission_manifest.json
      -> completeness checks
```

Data flow:

1. Load real result JSON files.
2. Validate minimum experiment count and provenance completeness.
3. Select the final run explicitly.
4. Generate report, table, command, and manifest.
5. Reject incomplete bundles that still contain placeholder content.

## Out of Scope

- Endpoint authentication.
- Metrics backends or tracing.
- CI and security scanner expansion.

## Dependencies

- Sprint `v1` completed.
- Modal credentials and quota for live runs.
- Human-written conclusions from actual experiments.
