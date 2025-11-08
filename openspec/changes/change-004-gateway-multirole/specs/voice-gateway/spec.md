## ADDED Requirements
### Requirement: Multi-Role Session Management
The gateway SHALL support multiple personas within a single client session.

#### Scenario: Role activation
- **WHEN** a client sends `voice.switch` with `role_id`
- **THEN** the gateway SHALL acknowledge, allocate the requested STT/TTS channel, and emit `voice.role_status` with the new role and channel health.

#### Scenario: Role fallback
- **WHEN** the requested role is unavailable (channel unhealthy or quota exceeded)
- **THEN** the gateway SHALL emit `voice.role_status` with failure reason and retain the previous role.

### Requirement: Channel Registry
The gateway SHALL maintain a registry of voice roles with configuration metadata.

#### Scenario: Channel metadata
- **WHEN** the gateway starts
- **THEN** it MUST load channel descriptors (voice_id, STT model, max concurrency) and make them queryable via `voice.roles`.

#### Scenario: Hot-swap semantics
- **WHEN** switching roles mid-session
- **THEN** the registry SHALL enforce cooldowns, priority weights, and fallback voice IDs as defined in configuration.

### Requirement: Telemetry for Multi-Role
The gateway SHALL emit telemetry covering role transitions.

#### Scenario: Role telemetry
- **WHEN** a role switch completes
- **THEN** metrics SHALL record `{session_id, from_role, to_role, switch_latency_ms, channel_health}`.

#### Scenario: Observability
- **WHEN** role switch failure rate > 5% over 5 minutes
- **THEN** an alert SHALL trigger for investigation.

