## ADDED Requirements
### Requirement: WebGPU Fluid Visualization
The LiquidSphere SHALL render using WebGPU to simulate fluid interference.

#### Scenario: Feature detection
- **WHEN** the client supports WebGPU
- **THEN** the visualization SHALL use the WebGPU renderer; otherwise it SHALL fallback to the Three.js shader.

#### Scenario: Fluid dynamics
- **WHEN** emotion/pitch metrics change
- **THEN** the renderer SHALL update fluid height maps and normal maps to reflect energy, pitch, and emotion transitions within 100 ms.

### Requirement: Performance Targets
The visualization SHALL meet defined performance goals.

#### Scenario: Frame rate
- **WHEN** running on M1/M2 or equivalent desktop GPUs
- **THEN** the renderer SHALL maintain ≥ 60 FPS under normal load.

#### Scenario: Resource monitoring
- **WHEN** GPU usage exceeds configurable thresholds
- **THEN** the system SHALL log warnings or downgrade effects.

### Requirement: Developer Controls
The visualization SHALL provide tuning hooks for developers.

#### Scenario: Debug interface
- **WHEN** debug mode is enabled
- **THEN** developers SHALL be able to adjust viscosity, energy scaling, and fluid parameters at runtime.

