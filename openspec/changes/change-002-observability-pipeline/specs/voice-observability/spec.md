## ADDED Requirements
### Requirement: Telemetry Storage Schema
The system SHALL persist Lingya Gateway telemetry in a structured data store.

#### Scenario: Session record
- **WHEN** a gateway session completes
- **THEN** a record SHALL be written to `voice_sessions` including `session_id`, `user_token`, `voice_id`, `started_at`, `ended_at`, `status`, `stt_latency_ms_p50/p95`, `tts_first_chunk_ms`, `error_count`.

#### Scenario: Metric record
- **WHEN** the gateway emits `metrics`
- **THEN** the pipeline SHALL upsert into `voice_metrics` the fields `{session_id, timestamp, avg_energy, peak_energy, pitch, emotion_estimate, latency_ms}` with retention ≥ 7 days.

### Requirement: Ingestion Endpoint
The platform SHALL expose a secure ingestion route for telemetry.

#### Scenario: Authentication
- **WHEN** gateway sends telemetry
- **THEN** the ingestion endpoint MUST verify a service token (or signed JWT) and reject unauthenticated requests.

#### Scenario: Back-pressure
- **WHEN** ingestion load exceeds thresholds
- **THEN** the pipeline SHALL buffer/batch writes (e.g., queue worker) without exceeding 5% data loss; otherwise raise an alert.

### Requirement: Observability Surfacing
The platform SHALL provide dashboards and alerts for key metrics.

#### Scenario: Dashboard slices
- **WHEN** reviewing system health
- **THEN** dashboards SHALL show avgEnergy trend, emotion distribution, session counts, and latency histograms filterable by voice_id.

#### Scenario: Alerting
- **WHEN** TTS first-chunk latency > 500 ms (p95) or error rate > 5% over 5 min
- **THEN** the system SHALL trigger an alert to the on-call channel.

### Requirement: CI Telemetry Smoke Test
The CI pipeline SHALL validate telemetry ingestion on every build.

#### Scenario: CI run
- **WHEN** GitHub Actions runs on PR/main
- **THEN** a smoke test SHALL post a synthetic session + metrics payload to the ingestion endpoint and assert the record is queryable within 60 s.

