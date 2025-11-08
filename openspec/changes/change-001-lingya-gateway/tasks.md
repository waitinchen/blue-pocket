## 1. Architecture & Design
- [ ] 1.1 Draft gateway session state diagram and channel ownership rules.
- [ ] 1.2 Align auth/rate limiting approach (JWT scope + per-IP quotas) with existing service policies.
- [ ] 1.3 Review proposal with team and secure approval.

## 2. Implementation
- [ ] 2.1 Add `LingyaGateway` module with session manager, channel registry, and telemetry hooks.
- [ ] 2.2 Update WebSocket endpoint to use gateway events (`voice.start`, `voice.data`, `voice.end`, `tts.stream`, `metrics`).
- [ ] 2.3 Implement error handling & reconnection logic (timeouts, graceful shutdown, retries).
- [ ] 2.4 Integrate JWT + rate limiter on gateway routes.
- [ ] 2.5 Expose server-side telemetry payloads for observability pipeline.

## 3. Frontend / SDK Updates
- [ ] 3.1 Update `MicRecorder` (and future SDKs) to speak the new event schema and reconnection flow.
- [ ] 3.2 Adjust ChatKit integration to consume `metrics` events for syncing visuals.
- [ ] 3.3 Add developer documentation & migration guide.

## 4. Testing & Validation
- [ ] 4.1 Unit tests for session manager, telemetry emitter, auth guard.
- [ ] 4.2 End-to-end WebSocket tests covering start/data/end flows, error cases.
- [ ] 4.3 Load test (multi-session) to confirm >95% success rate with session cleanup.
- [ ] 4.4 Update CI smoke test to validate gateway handshake + minimal stream.

