## 1. Planning
- [ ] 1.1 Finalize storage choice (Supabase Postgres + Timescale extension vs. alternative) and retention policy.
- [ ] 1.2 Define required metrics (latency, energy, emotion, error rates) & alert thresholds with stakeholders.
- [ ] 1.3 Review proposal/spec and obtain approval.

## 2. Schema & Ingestion
- [ ] 2.1 Create `voice_sessions`, `voice_metrics` tables (DDL, indices, retention).
- [ ] 2.2 Implement telemetry ingestion endpoint/worker consuming gateway events.
- [ ] 2.3 Ensure idempotent writes & back-pressure handling (batching, rate limits).
- [ ] 2.4 Protect ingestion endpoint with service token / IP allowlist.

## 3. Pipeline Integration
- [ ] 3.1 Update gateway to emit metrics conforming to schema.
- [ ] 3.2 Add Supabase/Grafana dashboard templates (avgEnergy trend, emotion distribution, latency histogram).
- [ ] 3.3 Configure alerts (e.g., latency SLA breaches, emotion flatline, error spikes).

## 4. Automation & Testing
- [ ] 4.1 Extend GitHub Actions to create temporary telemetry sink & run smoke test.
- [ ] 4.2 Write integration tests covering ingestion success/failure, data query correctness.
- [ ] 4.3 Document runbook + onboarding steps (secrets, dashboards, alert tuning).

