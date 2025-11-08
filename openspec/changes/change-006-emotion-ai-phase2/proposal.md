# Change: Emotion AI Phase 2 – Hybrid Signal & LLM Fusion

## Why
- Phase 1 delivers baseline pitch/energy metrics; to achieve expressive responses we must combine signal analysis with LLM emotion tags.
- Hybrid fusion enables higher confidence emotion estimates, better personalization, and richer visualization/voice modulation.
- Need a formal plan defining fusion model, feature set, and telemetry before implementation.

## What Changes
- Introduce a fusion pipeline combining signal features (energy, pitch, timbre) with LLM-generated emotion tags.
- Define confidence weighting, smoothing, and escalation rules (e.g., fallback to LLM when signal weak).
- Extend metrics/telemetry schema with fused emotion, confidence breakdown, and signal/LLM contributions.
- Update frontend & gateway to consume fused emotions for visuals and voice modulation.
- Document model training (if applicable), cost considerations, and feature flag rollout.

## Impact
- Affected specs: `emotion-ai`
- Affected code: Emotion worker, gateway metrics, telemetry ingestion, frontend overlay, possibly voice modulation parameters.
- Requires new testing strategy (dataset for evaluation, A/B flag) and monitoring for model drift.

