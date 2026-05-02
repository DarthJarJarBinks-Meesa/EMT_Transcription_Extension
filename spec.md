# ePCR Audio-to-Documentation Backend Specification

## 1. Project Overview

### 1.1 Problem Statement
EMTs and EMS students often lose time converting spoken field details into complete, structured ePCR documentation. This project creates a backend API that accepts EMS encounter audio and returns:
- A raw transcript
- Structured ePCR fields
- Narrative outputs suitable for handoff and charting

### 1.2 Project Goal
Build a secure, testable, API-first backend that transforms uploaded EMS audio into clinically useful documentation artifacts with minimal manual data entry.

### 1.3 Primary Users
- EMS students practicing report writing
- EMTs or supervisors prototyping charting workflows
- Frontend/app developers integrating audio documentation tools

### 1.4 Non-Goals (Current Scope)
- No persistent database storage in initial version
- No direct mobile client in this project
- No automated EHR/ePCR vendor integration
- No full HIPAA compliance certification package (deployment team responsibility)

## 2. Product Requirements

### 2.1 Core User Story
As an authenticated API client, I can upload an audio file from an EMS encounter and receive a transcript plus structured ePCR output, so I can quickly draft documentation.

### 2.2 Functional Requirements

#### FR-1: Audio Processing Endpoint
- Provide `POST /api/v1/process-audio`.
- Accept multipart form upload with field name `file`.
- Require API authentication for every request.
- Validate file presence, extension, MIME type, and max size.

#### FR-2: Speech-to-Text
- Transcribe accepted audio using an external STT model.
- Return transcript text as `raw_transcript`.

#### FR-3: Structured ePCR Extraction
- Transform transcript into a strict schema with:
  - Demographics
  - Vitals
  - Assessment details
  - Physical exam by body region
  - Interventions
  - Narrative
  - Clinical tagged summary
  - Plain-English call summary
- Use schema validation before returning results.

#### FR-4: Health and Readiness
- Provide:
  - `GET /health` for liveness
  - `GET /health/ready` for readiness of initialized dependencies

#### FR-5: Per-Key Usage Reporting
- Track usage counters keyed by SHA-256 fingerprint of client API key.
- Provide `GET /admin/usage` only when `ADMIN_API_KEY` is configured.
- Require admin auth header for usage endpoint.

#### FR-6: Authentication and Authorization
- Support either:
  - `X-API-Key` header
  - `Authorization: Bearer <token>`
- Allow one or more valid client keys from environment configuration.
- Reject missing/invalid keys with `401`.

#### FR-7: Rate Limiting
- Apply configurable rate limit to `POST /api/v1/process-audio`.
- Prefer per-client-key limiting; fallback to IP when key is absent.

### 2.3 Error Handling Requirements
- Return clear HTTP errors for:
  - Missing file (`400`)
  - Unsupported media/extension (`415`)
  - Oversized payload (`413`)
  - Invalid/missing auth (`401`)
  - Extraction failures (`422`)
  - Upstream AI failures (`502`)
  - Unhandled server failures (`500`)

### 2.4 Configuration Requirements
Environment-driven configuration:
- `GROQ_API_KEY` (required)
- `API_KEY` and/or `API_KEYS` (at least one required)
- `ADMIN_API_KEY` (optional, enables usage endpoint)
- `ALLOWED_ORIGINS` (optional CORS list)
- `MAX_UPLOAD_BYTES` (optional upload cap)
- `RATE_LIMIT` (optional throttling policy)

Server startup must fail fast if required secrets are missing.

## 3. Architecture and Technical Constraints

### 3.1 Tech Stack
- Python 3.10+
- FastAPI for HTTP layer
- Pydantic models for strict response validation
- Groq client for STT + structured extraction
- SlowAPI for rate limiting
- Pytest for automated tests

### 3.2 High-Level Flow
1. Client sends authenticated multipart audio upload.
2. API validates auth and input constraints.
3. API sends audio bytes to STT service.
4. API sends transcript to extraction model with schema constraints.
5. API validates model output against Pydantic schema.
6. API returns transcript + ePCR object.
7. Usage counters are updated per API key fingerprint.

### 3.3 Security and Privacy Constraints
- Never expose provider key to clients.
- Use separate client API keys from model provider key.
- Track only hashed key fingerprints in usage reports.
- Avoid logging PHI-rich transcript content in production logs.

### 3.4 Operational Constraints
- Initial release keeps usage stats in memory only.
- Metrics reset on process restart.
- Any durable analytics/billing requires future persistence layer.

## 4. Data Contract

### 4.1 Output Shape
Top-level API response:
- `raw_transcript: string`
- `epcr_data: object`

`epcr_data` includes nested sections:
- `demographics`
- `vitals`
- `assessment`
- `physical_exam`
- `interventions`
- `narrative`
- `clinical_tagged_summary`
- `call_summary`

### 4.2 Data Quality Rules
- Unknown or unstated fields use null/empty defaults as schema defines.
- Extraction must produce valid JSON object matching schema.
- Narrative outputs should be medically coherent and chronological.
- No fabricated findings beyond transcript evidence.

## 5. API Contract

### 5.1 Endpoints
- `POST /api/v1/process-audio`
- `GET /health`
- `GET /health/ready`
- `GET /admin/usage`

### 5.2 Auth Headers
Client endpoint auth:
- `X-API-Key: <client-secret>` or
- `Authorization: Bearer <client-secret>`

Admin endpoint auth:
- `X-Admin-Key: <admin-secret>`

## 6. Testing Requirements

### 6.1 Minimum Automated Test Coverage
- Health and readiness endpoints
- Auth success/failure paths
- API key loading logic (`API_KEY`, `API_KEYS`, merged behavior)
- Successful audio processing path
- Unsupported file rejection
- Extraction failure mapping to `422`
- Upstream service failure mapping to `502`
- Admin usage enabled/disabled behavior
- Usage counter correctness for request/transcription/success dimensions

### 6.2 Test Design Principles
- Use fake service implementations to avoid live model dependency.
- Keep tests deterministic and fast.
- Verify both status codes and response payload structure.

## 7. Acceptance Criteria

The MVP is complete when all are true:
- Server boots only with required env config.
- Authenticated users can upload valid audio and receive structured output.
- Invalid auth and invalid file inputs fail with correct status codes.
- Health/readiness endpoints return expected states.
- Rate limit is active and configurable.
- Admin usage endpoint works when configured and is unavailable otherwise.
- Test suite passes locally in a clean environment.

## 8. Risks and Mitigations

- **Model output drift**: enforce schema validation and strict parser errors.
- **Latency spikes**: isolate blocking model calls in worker threads.
- **Key leakage risk**: use separate secrets for provider and clients; hash keys in metrics.
- **Scope creep**: keep MVP backend-only and in-memory for usage data.

## 9. Future Enhancements

- Persistent storage for usage and audit metadata
- Background job queue for large audio workloads
- Multi-tenant key management and rotation tooling
- ePCR vendor integrations and export formats
- Enhanced observability dashboards and alerting
