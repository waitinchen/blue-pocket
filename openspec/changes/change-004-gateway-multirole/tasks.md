## 1. Design & Alignment
- [ ] 1.1 Draft multi-role session state machine (idle → listening → speaking, role transitions).
- [ ] 1.2 Define channel registry schema (role metadata, STT/TTS bindings, priority).
- [ ] 1.3 Review design with stakeholders and obtain approval.

## 2. Gateway Enhancements
- [ ] 2.1 Implement channel registry & hot-swap logic in LingyaGateway.
- [ ] 2.2 Add `voice.switch`, `voice.role_status`, and related events.
- [ ] 2.3 Handle concurrency conflicts (simultaneous switches, resource contention).
- [ ] 2.4 Extend session telemetry with role change metrics.

## 3. Frontend & SDK Updates
- [ ] 3.1 Update MicRecorder / client SDKs to request role changes and display role states.
- [ ] 3.2 Ensure ChatKit integration reflects active role (labels, colors, prompts).
- [ ] 3.3 Provide migration notes & developer docs for multi-role support.

## 4. Testing & Observability
- [ ] 4.1 Unit tests for registry, switch logic, failure recovery.
- [ ] 4.2 End-to-end tests covering multi-role conversations and reconnection.
- [ ] 4.3 Load tests simulating concurrent role switches (SLA < 600ms).
- [ ] 4.4 Update dashboards (role distribution, switch latency) and alerting.

