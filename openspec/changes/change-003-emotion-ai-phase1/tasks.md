## 1. Planning
- [ ] 1.1 Select signal-processing approach (pyAudioAnalysis vs Whisper pitch) and sampling interval.
- [ ] 1.2 Define feature flag strategy (`ENABLE_EMOTION_AI_P1`) and rollout plan.
- [ ] 1.3 Align metric schema additions with Observability pipeline (new fields, retention).

## 2. Worker Implementation
- [ ] 2.1 Build Emotion AI worker/processor module (audio queue, feature extraction, smoothing).
- [ ] 2.2 Integrate worker into Gateway pipeline (subscriptions, lifecycle hooks).
- [ ] 2.3 Implement resource guardrails (CPU usage, concurrency limits, timeouts).

## 3. Metrics & Frontend
- [ ] 3.1 Extend `metrics` event payload with pitch/faith/confidence fields under feature flag.
- [ ] 3.2 Add frontend debug overlay (toggleable) to visualize real-time energy/pitch/emotion state.
- [ ] 3.3 Update observability ingestion & dashboard to include new metrics.

## 4. Testing & Rollout
- [ ] 4.1 Unit tests for worker feature extraction, smoothing, flag gating.
- [ ] 4.2 Integration tests verifying metrics emission & frontend overlay toggle.
- [ ] 4.3 Load tests ensuring <200 ms additional latency per session.
- [ ] 4.4 Canary rollout script & documentation for enabling/disabling feature flag.

