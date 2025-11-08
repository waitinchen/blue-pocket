# Change: Emotion AI Phase 1 Prototype

## Why
- Need low-latency emotion signals (energy, pitch, spectral features) to enrich visuals and future AI behaviors.
- Gateway/observability specs now define metrics channels; we need a first-phase worker that plugs into those contracts without destabilizing production.
- Early prototype enables tuning before investing in full ML models.

## What Changes
- Add Emotion AI worker that processes audio frames (pyAudioAnalysis or Whisper pitch) under a feature flag.
- Emit enriched `metrics` payloads (avg_energy, peak_energy, pitch, confidence tags) through Gateway.
- Surface debug overlay in frontend to validate readings without disrupting core UI.
- Provide sampling & cost controls (e.g., max CPU utilization, sampling interval).

## Impact
- Affected specs: `emotion-ai`
- Affected code: gateway metrics emitter, new worker service/module, frontend debug tools, configuration management, CI integration.
- Requires coordination with Observability pipeline to store new fields.

