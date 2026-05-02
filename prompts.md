# Prompt Pack for Implementing the Project (TDD, Incremental)

Use these prompts in order. Each prompt assumes the previous one is complete and committed. Keep every step small, tested, and integrated before moving on.

## Prompt 1 - Bootstrap and first passing test
You are building a Python FastAPI backend from scratch.

Goal:
- Create a minimal project scaffold for an API service.
- Add pytest configuration.
- Implement `GET /health` returning `{ "status": "ok", "service": "emt-epcr-backend" }`.
- Add one passing test for `/health`.

Constraints:
- Keep implementation minimal.
- Do not add AI provider integration yet.
- Show file-by-file changes and then run tests.

Deliverables:
- Updated code
- Test output
- Brief note on what changed and why

## Prompt 2 - Lifespan and startup config validation
Continue from the existing codebase.

Goal:
- Add FastAPI lifespan startup checks that require:
  - `GROQ_API_KEY`
  - at least one of `API_KEY` or `API_KEYS`
- Fail startup with clear error messages if missing.
- Keep `/health` working.
- Add readiness endpoint `/health/ready` that reports initialized dependency status.

Testing:
- Add/adjust tests for readiness and startup guard behavior.
- Keep tests deterministic (use monkeypatch).

Deliverables:
- Code updates
- Test updates
- Full test run results

## Prompt 3 - Authentication foundation
Continue incrementally.

Goal:
- Implement API key loader that merges `API_KEY` + parsed `API_KEYS` (comma/newline separated).
- Add authentication dependency supporting:
  - `X-API-Key`
  - `Authorization: Bearer <token>`
- Return `401` when missing/invalid.

Testing:
- Add targeted tests for:
  - missing auth
  - valid `X-API-Key`
  - valid bearer token
  - merged key behavior

Constraints:
- Do not implement audio processing logic yet.

## Prompt 4 - Add process endpoint skeleton
Continue from current state.

Goal:
- Create `POST /api/v1/process-audio` with multipart `file`.
- Protect endpoint with auth dependency.
- Return a temporary placeholder response using a typed response model.

Testing:
- Add one unauthorized test and one authorized happy-path test using fake/placeholder behavior.
- Keep tests passing without external network calls.

## Prompt 5 - File validation rules
Extend the process endpoint.

Goal:
- Validate uploaded file:
  - non-empty filename
  - allowed audio extension set
  - allowed MIME types
  - max upload byte size from env default
- Return proper status codes (`400`, `413`, `415`) with useful detail messages.

Testing:
- Add separate tests for each validation failure.
- Keep existing auth and health tests passing.

## Prompt 6 - Service abstraction and fake injection
Refactor for testability.

Goal:
- Introduce a service interface/object with async methods:
  - `transcribe_audio(audio_bytes, filename)`
  - `extract_epcr_data(transcript)`
- Inject this service through FastAPI dependencies or startup state.
- Provide a fake service in tests.

Constraints:
- No real provider calls in tests.
- Keep endpoint behavior unchanged from client perspective.

Testing:
- Ensure existing process happy-path test uses fake service and still passes.

## Prompt 7 - Implement STT provider call safely
Now implement real transcription service logic.

Goal:
- Integrate provider SDK for speech-to-text in the service implementation.
- Offload blocking SDK calls to a worker thread so event loop is not blocked.
- Wrap provider failures in a domain-specific exception.

Endpoint behavior:
- Map provider transcription failures to HTTP `502`.

Testing:
- Add tests that simulate service-level provider failure and verify `502`.
- Keep fake-based success tests.

## Prompt 8 - Implement structured extraction with strict schema validation
Continue from the existing service.

Goal:
- Define complete Pydantic schema for extracted ePCR data with nested sections:
  - demographics, vitals, assessment, physical_exam, interventions, narrative, clinical_tagged_summary, call_summary
- Build extraction call that requests JSON-only output.
- Parse JSON and validate against schema.
- Raise extraction-specific error when JSON is invalid/empty/schema-mismatched.

Endpoint behavior:
- Map extraction failure to HTTP `422`.

Testing:
- Add tests for extraction failure branch and success payload shape.

## Prompt 9 - Usage tracking (in-memory, per API key fingerprint)
Add operational analytics.

Goal:
- Implement async-safe in-memory usage tracker keyed by SHA-256 fingerprint of client key.
- Track:
  - `process_audio_requests`
  - `audio_bytes_transcribed`
  - `full_epcr_successes`
- Integrate tracker into process flow at correct points.

Testing:
- Add tests verifying:
  - request count increments for authenticated attempts
  - transcribed bytes increments after successful transcription
  - success count increments only after full successful extraction

## Prompt 10 - Admin usage endpoint
Expose usage report securely.

Goal:
- Add `GET /admin/usage`.
- Require `ADMIN_API_KEY` config and `X-Admin-Key` request header.
- Return usage rows using response model.
- Return `404` if admin reporting is not enabled.
- Return `401` for invalid admin key.

Testing:
- Add tests for enabled/disabled/unauthorized flows and usage data correctness.

## Prompt 11 - Rate limiting and request identity
Add production guardrails.

Goal:
- Integrate SlowAPI rate limiting on `POST /api/v1/process-audio`.
- Use hashed client key for limiter identity when present.
- Fallback to remote IP when no key is available.
- Make limit configurable via `RATE_LIMIT`.

Testing:
- Add focused tests for key derivation logic.
- Keep broader endpoint tests stable.

## Prompt 12 - Docs and developer runbook
Finalize project usability.

Goal:
- Write/refresh README with:
  - setup commands
  - required env vars and examples
  - run command
  - curl examples for auth + upload
  - tests command
  - endpoint list
- Include note about in-memory usage reset on restart.

Quality checks:
- Ensure commands are copy-pasteable.
- Keep documentation aligned with actual code paths and env var names.

## Prompt 13 - Optional Docker packaging
Add reproducible runtime packaging.

Goal:
- Add Dockerfile for running the API.
- Document build and run commands with required env vars.
- Keep container default command serving FastAPI app.

Validation:
- Provide a short verification checklist for container run + health check.

## Prompt 14 - Final integration and safety pass
Perform final cross-cutting review.

Goal:
- Review for orphaned code paths and incomplete wiring.
- Ensure all endpoints are integrated with auth/config/dependencies as designed.
- Run full test suite.
- Summarize:
  - what is implemented
  - known limitations
  - recommended next enhancements

Output format:
- Use sections:
  1. Integration checks
  2. Test results
  3. Remaining risks
  4. Next steps
