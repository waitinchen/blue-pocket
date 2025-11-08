# Change: Lingya Gateway Multi-Role Orchestration

## Why
- Voice OS needs seamless switching between personas (e.g., Huangrong, Xiaoruan) without reconnecting clients.
- Current gateway handles a single voice channel per session; multi-role demands shared state, voice routing, and deterministic recovery.
- Preparing for v0.4 requires defining session state machine, channel registry, and hot-swap rules before implementation.

## What Changes
- Introduce multi-role session management: allow clients to request role changes mid-session (`voice.switch`, etc.).
- Define channel registry with lifecycle hooks (load/unload models, voice IDs, TTS/STT settings).
- Specify conflict resolution/priority rules when multiple roles compete for resources.
- Extend telemetry to capture role transitions, channel health, and cross-role latency.
- Document graceful degradation & rollback (e.g., fallback voice when target role unavailable).

## Impact
- Affected specs: `voice-gateway`
- Affected code: gateway session manager, channel registry, voice/TTS selection, telemetry, frontend/SDK handling of role switch events.
- Requires new integration tests, regression tests for session continuity, and updated observability dashboards.

