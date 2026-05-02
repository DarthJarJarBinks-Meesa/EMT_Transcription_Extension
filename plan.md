# Development Plan: ePCR Audio-to-Documentation Backend

## Planning Approach
This blueprint is intentionally incremental, test-first, and integration-focused. Each chunk is small enough to validate safely, while still producing visible project progress.

## Phase 0: Project Setup and Guardrails

### Step 0.1 - Initialize backend scaffold
- Create project structure (`app/`, `app/models/`, `app/services/`, `tests/`).
- Add dependency management and Python version constraints.
- Add run command and local development instructions.

### Step 0.2 - Add baseline tooling
- Configure pytest discovery and async settings.
- Add lint/format preferences if desired.
- Create `.gitignore` and environment variable example docs.

### Step 0.3 - Add first smoke test
- Implement a trivial health endpoint test and make it pass.
- Confirm CI/local test execution pipeline works before feature work.

## Phase 1: Core API Skeleton

### Step 1.1 - Build FastAPI app with lifespan
- Create app instance and lifespan startup hook.
- Validate required environment variables at startup.
- Fail fast with clear startup errors when missing secrets.

### Step 1.2 - Add health and readiness endpoints
- `GET /health` returns service status.
- `GET /health/ready` reflects dependency initialization state.
- Add tests for both endpoints.

### Step 1.3 - Configure CORS and request limits
- Add CORS middleware from env-based origins.
- Introduce upload max bytes config constant.
- Add tests or assertions for expected defaults.

## Phase 2: Authentication and Rate Limiting

### Step 2.1 - Implement API key loading
- Parse `API_KEY` and `API_KEYS`.
- Normalize separators and whitespace.
- Ensure at least one key is available.

### Step 2.2 - Add request authentication dependency
- Accept `X-API-Key` and `Authorization: Bearer`.
- Return `401` for invalid or missing credentials.
- Add focused tests for auth success/failure variants.

### Step 2.3 - Add per-client rate limiting
- Integrate SlowAPI limiter.
- Derive limiter key from hashed API key when possible.
- Fallback to remote address if unauthenticated.
- Add test coverage for key derivation behavior (unit-level if needed).

## Phase 3: File Intake and Validation

### Step 3.1 - Implement `POST /api/v1/process-audio` skeleton
- Add multipart file input.
- Wire authentication dependency into endpoint.
- Return placeholder response initially.

### Step 3.2 - Enforce file validation rules
- Reject missing filename.
- Enforce allowed audio extensions and MIME types.
- Enforce configured max upload size.
- Add tests for each rejection path and expected status code.

### Step 3.3 - Stabilize error envelope
- Standardize HTTP exception details for input failures.
- Ensure errors are actionable but do not leak internals.

## Phase 4: AI Service Integration

### Step 4.1 - Introduce service interface
- Define service abstraction with methods:
  - `transcribe_audio(audio_bytes, filename)`
  - `extract_epcr_data(transcript)`
- Add dependency injection helper for service retrieval.

### Step 4.2 - Implement STT call
- Call Groq Whisper model in blocking-safe way (thread offload).
- Normalize transcription output handling.
- Map upstream failures to internal domain errors.

### Step 4.3 - Implement structured extraction call
- Build system prompt using schema JSON.
- Request strict JSON object output from chat model.
- Parse and validate against Pydantic ePCR schema.
- Raise extraction-specific errors for malformed/empty responses.

### Step 4.4 - Complete endpoint orchestration
- Transcribe, extract, and return typed response model.
- Map:
  - extraction failures -> `422`
  - upstream provider failures -> `502`
  - unknown failures -> `500`
- Add tests with fake services for all branches.

## Phase 5: Data Models and Contracts

### Step 5.1 - Create Pydantic ePCR schema set
- Define nested models for demographics, vitals, assessment, physical exam.
- Add narrative, tagged summary, and call summary fields.
- Keep optional fields nullable for incomplete transcripts.

### Step 5.2 - Define response models
- `TranscriptionResponse` for main endpoint.
- Usage report models for admin metrics endpoint.

### Step 5.3 - Add contract assertions
- Expand tests to validate key response shape and required fields.
- Prevent accidental response contract regressions.

## Phase 6: Usage Tracking and Admin Endpoint

### Step 6.1 - Build in-memory usage tracker
- Track per-key fingerprint counters:
  - request count
  - transcribed bytes
  - full success count
- Ensure async/thread safety with lock.

### Step 6.2 - Integrate tracker with processing pipeline
- Increment request count after auth.
- Increment transcribed bytes after successful transcription.
- Increment success count only after full response success.

### Step 6.3 - Add admin usage endpoint
- Guard route behind `ADMIN_API_KEY`.
- Require `X-Admin-Key` header.
- Return sorted usage snapshot.
- Add tests for enabled, disabled, unauthorized, and data correctness cases.

## Phase 7: Developer Experience and Packaging

### Step 7.1 - Documentation
- Write README with:
  - setup
  - env variables
  - run commands
  - curl usage
  - test instructions
- Document auth patterns and admin endpoint behavior.

### Step 7.2 - Optional containerization
- Add Dockerfile for reproducible local deployment.
- Document docker build/run examples with env vars.

### Step 7.3 - Local verification checklist
- Run tests cleanly.
- Exercise curl happy path and auth rejection path.
- Confirm readiness and health endpoints.

## Phase 8: Hardening Pass

### Step 8.1 - Error handling review
- Audit endpoint and service exceptions for consistency.
- Ensure no raw stack traces or provider internals leak in responses.

### Step 8.2 - Security and privacy review
- Confirm no sensitive transcript logging by default.
- Verify key hashing is used in usage reporting.
- Confirm separation of client keys and provider key in docs and code.

### Step 8.3 - Scope freeze for MVP
- Tag MVP after passing tests and acceptance checks.
- Defer persistence, background processing, and integrations to roadmap.

## Iterative Chunk List (Ready for TDD Execution)

1. Health endpoint + test.
2. Lifespan config checks + startup tests.
3. API key loader + auth dependency + auth tests.
4. Process endpoint skeleton + multipart acceptance test.
5. File validation rules + negative tests.
6. Groq service abstraction + fake injection tests.
7. STT integration + transcription error mapping tests.
8. Structured extraction + schema validation tests.
9. Final response model wiring + success path tests.
10. Rate limiting integration + key derivation tests.
11. Usage tracker + unit tests.
12. Admin usage endpoint + auth and snapshot tests.
13. README and runbook updates.
14. Optional Docker packaging and verification.

## Definition of Done
- All planned tests pass reliably.
- API behavior matches `spec.md`.
- No endpoint remains partially wired or orphaned.
- Documentation is sufficient for a new developer to run and validate locally.
