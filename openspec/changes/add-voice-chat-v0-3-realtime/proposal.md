# Proposal: Lingya Voice Chat v0.3 realtime upgrade

## Summary
Deliver the v0.3 release with end-to-end realtime audio pipeline, GPU-driven visuals, and deployment automation so experience exceeds v0.2 baseline.

## Motivation
- Plan mandates sub-400ms conversational latency with synchronized audio-visual feedback.
- Current v2.0 stack only supports HTTP turn-taking and 2D canvas animations.
- Need CI/CD and production-ready infrastructure to deploy to Railway (backend) and Vercel (frontend).

## Goals
- Launch WebSocket-based realtime STT + TTS loop tightly coupled with ChatKit conversation.
- Replace 2D Matter.js sphere with Three.js shader liquid sphere driven by emotion + energy uniforms.
- Synchronize emotion tags from LLM/Whisper to visuals and audio playback in <400ms.
- Automate deployments and verification pipelines for Railway backend and Vercel frontend.

## Impact
- Affected specs: voice-chat-realtime
- Affected code: `api/main.py`, `api/whisper_api.py`, new realtime services, `frontend/components/*`, `frontend/pages/VoiceChat.tsx`, deployment scripts, CI/CD workflows.
