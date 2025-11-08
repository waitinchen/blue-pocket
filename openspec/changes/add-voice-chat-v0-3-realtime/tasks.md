## 1. Planning & Setup
- [ ] 1.1 Confirm v0.3 scope, success metrics, and dependencies.
- [ ] 1.2 Create `feature/v0.3-realtime` branch and align env vars.

## 2. Realtime Audio Pipeline
- [ ] 2.1 Implement Whisper realtime WebSocket bridge with energy + transcript streaming.
- [ ] 2.2 Implement ElevenLabs streaming TTS bridge with chunked audio + metadata.
- [ ] 2.3 Create orchestrator hub `/api/voice/stream` that couples STT?’LLM?’TTS.

## 3. Frontend Realtime Experience
- [ ] 3.1 Replace Matter.js sphere with Three.js shader-based liquid sphere component.
- [ ] 3.2 Wire Web Audio analyser + energy feed into shader uniforms.
- [ ] 3.3 Integrate ChatKit conversation flow with realtime events.

## 4. Emotion Agent Sync
- [ ] 4.1 Map LLM/Whisper emotion outputs to color spectrum and animation states.
- [ ] 4.2 Ensure visuals + audio respond within target latency budget.

## 5. Deployment & CI/CD
- [ ] 5.1 Produce Railway deployment config for backend.
- [ ] 5.2 Produce Vercel deployment automation for frontend.
- [ ] 5.3 Add pipeline scripts/tests verifying realtime path.

## 6. QA & Polish
- [ ] 6.1 Add diagnostics for reconnection, metrics, and latency logging.
- [ ] 6.2 Implement fluid particle polish (breathing, resonance, ripple).
- [ ] 6.3 Record demo and document release process (`v0.3 release`).
