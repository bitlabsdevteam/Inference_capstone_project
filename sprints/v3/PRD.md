# Sprint v3 PRD - Endpoint Security and Access Control

## Sprint Overview

Sprint `v3` hardens the benchmark endpoint so it can be treated as a protected service rather than an openly exposed demo URL. The goal is to require authenticated access for inference traffic and reduce accidental leakage of secrets and sensitive provenance.

## Goals

- Require authentication for inference requests.
- Keep benchmark automation compatible with the new auth path.
- Reduce exposure of sensitive endpoint details in logs and saved artifacts.
- Document a secure operator workflow for secret rotation and local execution.

## User Stories

- As an operator, I want inference requests to require a bearer token so that public endpoint discovery does not grant free access.
- As a benchmark runner, I want the load test and smoke checks to authenticate automatically so that security does not break the harness.
- As a reviewer, I want saved artifacts to avoid leaking sensitive runtime details unnecessarily.

## Technical Architecture

- Stack: Modal web app, Python auth helpers, environment/secret configuration.
- Primary components:
  - `starter_code/modal_infertutor_app.py`
  - `starter_code/run_infertutor_experiment.py`
  - `starter_code/load_test_infertutor.py`
  - `starter_code/preflight_infertutor.py`
  - `starter_code/bootstrap_infertutor_env.py`
  - `tests/test_infertutor_tools.py`

```text
Operator secret
  -> Modal secret / env
  -> vLLM --api-key
      -> /health
      -> /v1/chat/completions
Runner + load tester
  -> bearer auth header injection
  -> smoke + load requests
Saved artifacts
  -> redacted endpoint URL
  -> no auth secret persistence
```

## Out of Scope

- Full SSO or user management.
- External API gateway integration.
- Per-user rate limiting.

## Dependencies

- Sprint `v1` completed.
- Sprint `v2` code-side artifact hardening completed.
- Modal credentials and a live deployment for final auth verification.
