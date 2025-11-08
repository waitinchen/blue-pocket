## 1. Planning & Data
- [ ] 1.1 Collect representative dataset (audio + LLM tags) for evaluation.
- [ ] 1.2 Define fusion strategy (weights, smoothing, fallback rules).
- [ ] 1.3 Review privacy/cost implications with stakeholders.

## 2. Fusion Engine Implementation
- [ ] 2.1 Extend EmotionAI worker with signal feature extraction (spectral features, timbre).
- [ ] 2.2 Implement LLM tag ingestion and confidence scoring.
- [ ] 2.3 Build fusion module producing final `emotion`, `confidence_breakdown`.
- [ ] 2.4 Add feature flag (`ENABLE_EMOTION_AI_P2`) and gradual rollout plan.

## 3. Gateway & Telemetry
- [ ] 3.1 Update gateway metrics payload with fused emotion fields.
- [ ] 3.2 Persist new fields in Supabase (signal_confidence, llm_confidence, fused_emotion).
- [ ] 3.3 Add alerting for drift (e.g., signal vs LLM mismatch > threshold).

## 4. Frontend & Voice Modulation
- [ ] 4.1 Update overlay/visuals to display fused emotion info and confidences.
- [ ] 4.2 Expose API for dynamic voice modulation (voice settings adjusted per emotion).
- [ ] 4.3 Document developer guide for using fused emotion data.

## 5. Testing & Evaluation
- [ ] 5.1 Offline accuracy tests comparing fused output vs labelled data.
- [ ] 5.2 Real-time integration tests measuring added latency (< 250 ms).
- [ ] 5.3 Monitor production metrics during A/B rollout and adjust weights.

