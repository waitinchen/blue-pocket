## ADDED Requirements
### Requirement: Hybrid Emotion Fusion
The system SHALL fuse signal-based and LLM-based emotion estimates.

#### Scenario: Fusion output
- **WHEN** both signal features and LLM tags are available
- **THEN** the worker SHALL emit `fused_emotion`, `signal_confidence`, `llm_confidence`, and `combined_confidence`.

#### Scenario: Fallback
- **WHEN** signal confidence < threshold OR LLM unavailable
- **THEN** the fusion engine SHALL rely on the available source and report the reason in telemetry.

### Requirement: Performance & Latency
The fusion pipeline SHALL respect latency budgets.

#### Scenario: Real-time latency
- **WHEN** Emotion AI Phase 2 is enabled
- **THEN** additional processing SHALL add < 250 ms latency per chunk at p95.

### Requirement: Telemetry Extension
The telemetry pipeline SHALL capture fusion metrics.

#### Scenario: Metrics payload
- **WHEN** emitting gateway metrics
- **THEN** payloads SHALL include `{fused_emotion, signal_confidence, llm_confidence, combined_confidence}`.

#### Scenario: Drift monitoring
- **WHEN** signal and LLM confidence diverge (> 0.5 difference) for > 1 minute
- **THEN** the system SHALL emit an alert for Emotion AI drift.

