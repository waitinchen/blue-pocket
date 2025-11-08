## ADDED Requirements
### Requirement: Lingya Gateway Session Control
The platform SHALL provide a gateway service that manages end-to-end STT/TTS sessions for Lingya Voice OS clients.

#### Scenario: Session lifecycle
- **WHEN** a client sends `voice.start`
- **THEN** the gateway SHALL allocate a session ID, bind the requested voice channel, and respond with acknowledgement or error.

#### Scenario: Media streaming
- **WHEN** a client streams chunks via `voice.data`
- **THEN** the gateway SHALL forward audio to the configured STT channel, enforce byte-size/time limits, and emit partial transcripts as `metrics` events within 400 ms.

#### Scenario: Session closure
- **WHEN** the client sends `voice.end` _or_ the gateway detects timeout
- **THEN** the gateway SHALL flush pending transcripts, finalize telemetry, release resources, and emit `session.closed`.

### Requirement: Gateway Event Schema
The gateway SHALL expose a canonical WebSocket event contract for clients.

#### Scenario: Required events
- **WHEN** a session is active
- **THEN** the gateway MUST handle inbound events `voice.start`, `voice.data`, `voice.end` and emit outbound events `voice.ack`, `tts.stream`, `metrics`, `session.closed`, `error`.

#### Scenario: Event payload format
- **WHEN** events are exchanged
- **THEN** payloads MUST include `session_id`, `timestamp`, and schema-specific fields (e.g., `chunk` base64 for `voice.data`, `latency_ms` for `tts.stream`, `{avg_energy, peak_energy, emotion_estimate, pitch}` for `metrics`).

### Requirement: Gateway Telemetry & Policy
The gateway SHALL enforce security policies and produce telemetry suitable for observability.

#### Scenario: Authentication & quota
- **WHEN** a client establishes a session
- **THEN** the gateway SHALL validate a signed JWT scoped to `voice-session` and apply per-IP and per-token rate limits (default 100 requests/minute).

#### Scenario: Telemetry emission
- **WHEN** a session completes
- **THEN** the gateway SHALL emit telemetry containing session duration, STT latency percentiles, TTS first-chunk latency, average energy, peak energy, emotion estimate, and error counts for ingestion by the observability pipeline.

#### Scenario: Error handling
- **WHEN** STT or TTS channels raise recoverable errors
- **THEN** the gateway SHALL emit an `error` event with code/context and attempt one retry before failing the session.

