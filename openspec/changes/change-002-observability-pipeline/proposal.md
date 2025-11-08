# Change: Observability Pipeline for Lingya Gateway

## Why
- Upcoming Lingya Gateway needs structured telemetry to monitor latency, emotion quality, and error rates across all sessions.
- Without a shared schema and storage plan, downstream dashboards (Supabase/Grafana) cannot ingest consistent metrics or power alerts.
- CI must validate that telemetry endpoints remain healthy as the realtime stack evolves.

## What Changes
- Define database schema (Supabase/Timescale) for session- and metric-level telemetry.
- Specify ingestion endpoints or workers responsible for batching gateway metrics.
- Add CI smoke test that exercises the telemetry route and asserts data is persisted.
- Document retention policy, alert thresholds, and authentication for observability services.
- Provide reference dashboard slices (avgEnergy timeline, emotion distribution, TTS latency heatmap).

## Impact
- Affected specs: `voice-observability`
- Affected code: gateway telemetry emitters, telemetry ingestion service, deployment configs for Supabase/Grafana, CI workflows.
- Affected tooling: new secrets (SUPABASE_URL/KEY), dashboard configuration, alerting rules.

