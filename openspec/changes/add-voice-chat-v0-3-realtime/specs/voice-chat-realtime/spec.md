## ADDED Requirements
### Requirement: Realtime conversational pipeline
The system SHALL provide a WebSocket endpoint that streams microphone audio to Whisper, relays partial transcripts within 400ms, and emits ElevenLabs streaming audio responses without waiting for full synthesis.

#### Scenario: Bidirectional audio streaming
- **WHEN** a client connects to `/api/voice/stream` and uploads audio chunks
- **THEN** the server SHALL forward chunks to STT, emit partial transcripts, and begin TTS playback within 500ms of LLM reply.

#### Scenario: Latency budget guardrails
- **WHEN** the pipeline detects latency exceeding 400ms for STT or 500ms for first TTS chunk
- **THEN** it SHALL emit diagnostic events so the frontend can surface warnings and adjust UI state.

### Requirement: GPU liquid sphere visualization
The frontend SHALL render a Three.js shader-based liquid sphere at ??0 FPS that responds to realtime energy and emotion uniforms.

#### Scenario: Energy-driven deformation
- **WHEN** `uEnergy` increases from audio analyser input
- **THEN** the shader SHALL exaggerate surface ripple amplitude proportional to energy while maintaining ??0 FPS on a Mac M2.

#### Scenario: Emotion color mapping
- **WHEN** emotion tags change (e.g., happy?’soft)
- **THEN** the shader SHALL transition colors smoothly within 300ms without flicker using predefined gradients.

### Requirement: Emotion-synced experience
The application SHALL synchronize emotion metadata across audio playback, visual state, and ChatKit transcript presentation.

#### Scenario: Synchronized updates
- **WHEN** the backend emits an emotion update
- **THEN** the frontend SHALL update shader colors, caption text, and ChatKit message annotations within the same animation frame.

#### Scenario: Resilience to dropped events
- **WHEN** emotion events are missed due to network hiccup
- **THEN** the frontend SHALL fallback to last-known state and request a state refresh within 1 second.

### Requirement: Automated deployment and verification
The project SHALL provide CI/CD that deploys backend to Railway and frontend to Vercel on push to main, including automated smoke tests for the realtime pipeline.

#### Scenario: Successful deployment
- **WHEN** changes merge into `main`
- **THEN** CI/CD SHALL build, test, and deploy the backend to Railway and frontend to Vercel, producing accessible URLs.

#### Scenario: Realtime smoke test
- **WHEN** CI/CD deploys
- **THEN** a smoke test SHALL connect to `/api/voice/stream`, verify transcript + TTS events, and fail the pipeline if realtime flow is broken.
