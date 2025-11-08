## ADDED Requirements
### Requirement: Emotion AI Worker (Phase 1)
The system SHALL provide a feature-flagged worker that extracts low-latency audio features from Lingya Gateway sessions.

#### Scenario: Feature flag gating
- **WHEN** `ENABLE_EMOTION_AI_P1` is false
- **THEN** the worker SHALL remain inactive and metrics payloads SHALL omit pitch-specific fields.

#### Scenario: Worker activation
- **WHEN** `ENABLE_EMOTION_AI_P1` is true and audio frames arrive
- **THEN** the worker SHALL compute average energy, peak energy, pitch (Hz), and normalized confidence within 200 ms per chunk.

### Requirement: Metrics Enrichment
The system SHALL enrich gateway `metrics` events with Emotion AI outputs.

#### Scenario: Metrics payload
- **WHEN** the worker emits results
- **THEN** `metrics` events MUST include `{avg_energy, peak_energy, pitch_hz, emotion_estimate, confidence, feature_flag: "emotion_ai_p1"}` and respect existing schema.

#### Scenario: Sampling policy
- **WHEN** consecutive chunks arrive
- **THEN** the worker SHALL down-sample to a configurable interval (default 100 ms) to control CPU usage.

### Requirement: Frontend Debug Overlay
The frontend SHALL provide a developer-facing overlay to visualize Emotion AI metrics.

#### Scenario: Debug toggle
- **WHEN** a developer enables the Emotion AI debug overlay (e.g., query param or hotkey)
- **THEN** the UI SHALL display real-time energy, pitch, emotion tags, and confidence without affecting primary visuals.

### Requirement: Observability Integration
The observability pipeline SHALL store and surface the new metrics.

#### Scenario: Telemetry storage
- **WHEN** enriched metrics are emitted
- **THEN** the ingestion service SHALL persist `pitch_hz`, `confidence`, and `feature_flag` alongside existing fields.

#### Scenario: Alert thresholds
- **WHEN** pitch extraction fails (confidence < 0.2) for >1 minute
- **THEN** an alert SHALL be triggered to investigate signal quality.

