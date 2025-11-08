## 1. Research & Design
- [ ] 1.1 Evaluate WebGPU frameworks (regl vs Babylon.js vs raw WebGPU).
- [ ] 1.2 Prototype fluid simulation pipeline (height map, normal map, energy injection).
- [ ] 1.3 Draft fallback strategy for non-WebGPU browsers.

## 2. Implementation
- [ ] 2.1 Build WebGPU LiquidSphere component with emotion/pitch uniforms.
- [ ] 2.2 Implement energy-driven ripple/viscosity controls configurable via env.
- [ ] 2.3 Add runtime detection + fallback to existing Three.js shader.
- [ ] 2.4 Integrate performance monitoring hooks (FPS, GPU load).

## 3. Frontend Integration
- [ ] 3.1 Update state hooks to feed emotion/pitch data into WebGPU uniforms.
- [ ] 3.2 Provide developer controls (debug panel, tweakable parameters).
- [ ] 3.3 Update CSS/styles to accommodate new canvas/WebGPU surface.

## 4. Testing & Optimization
- [ ] 4.1 Unit/visual regression tests for rendering states.
- [ ] 4.2 Performance benchmarks across devices (M1/M2, RTX, integrated GPUs).
- [ ] 4.3 Document tuning guide, fallback path, and browser support matrix.

