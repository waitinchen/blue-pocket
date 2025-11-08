# Change: Lingya Gateway Architecture

## Why
- Current realtime pipeline couples Whisper STT, LLM routing, and ElevenLabs streaming in a single endpoint, making multi-channel expansion brittle.
- We need a single control plane for all Lingya Voice OS sessions before scaling to multiple roles or external clients.
- Establishing a formal contract for session lifecycle and telemetry enables downstream observability and Emotion AI to hook into the same events.

## What Changes
- Introduce `LingyaGateway` component responsible for session admission, channel orchestration, and uniform WebSocket event schema.
- Define client/server events for voice streams (`voice.start`, `voice.data`, `voice.end`, `tts.stream`, `metrics`), including required fields and timing guarantees.
- Specify session lifecycle states, resource ownership, and error/retry semantics.
- Document telemetry requirements (latency, energy, emotion estimates) emitted per session for observability pipeline.
- Align auth/rate-limiting strategy (JWT + quota) across Gateway entrypoints.

## Impact
- Affected specs: `voice-gateway`
- Affected code: `api/main.py`, new gateway module(s), WebSocket handlers, session state manager, authentication middleware, integration tests, client SDKs (`MicRecorder`, ChatKit hooks).
- Affected infra: CI smoke tests, deployment configs referencing new gateway routes.

