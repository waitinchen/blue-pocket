# Change: WebGPU Liquid Sphere Visualization Upgrade

## Why
- Current Three.js shader emulates fluid visuals but lacks true interference, viscosity, and GPU-level control required for v0.4 “wow” experience.
- WebGPU (via regl/Babylon.js) unlocks realistic surface simulation, multi-pass rendering, and better performance across devices.
- Need a formal plan before replacing the core visual component.

## What Changes
- Migrate LiquidSphere visualization from Canvas/Three.js to WebGPU-based pipeline (regl or Babylon.js).
- Introduce shader architecture supporting fluid dynamics (height maps, normal maps, energy injection).
- Define interfaces for emotion/pitch-driven uniforms and front-end performance fallbacks.
- Update build tooling (feature detection, graceful fallback to existing shader).
- Document performance targets (≥ 60 FPS, GPU utilization thresholds) and testing strategy.

## Impact
- Affected specs: `visualization`
- Affected code: `frontend/components/LiquidSphere`, rendering hooks, emotion-driven uniforms, build config, possibly new worker for GPU updates.
- Affected infra: Requires browser feature detection, fallback path, testing matrix (WebGPU-capable devices).

