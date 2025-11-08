import { useEffect, useRef } from "react";
import * as THREE from "three";

type LiquidSphereProps = {
  speakingEnergy?: number;
  playbackEnergy?: number;
  emotion?: string;
};

type EmotionPreset = {
  base: string;
  emotion: string;
  glow: string;
};

const emotionPresets: Record<string, EmotionPreset> = {
  happy: { base: "#fce4ff", emotion: "#ff7ecb", glow: "#ffd166" },
  soft: { base: "#dbfffa", emotion: "#99f1ff", glow: "#ffffff" },
  sad: { base: "#9cb5ff", emotion: "#477dff", glow: "#b8ccff" },
  angry: { base: "#ffb498", emotion: "#ff4b4b", glow: "#ff8a4a" },
  curious: { base: "#b9fff3", emotion: "#45e4ff", glow: "#7cf3ff" },
  neutral: { base: "#d4d5ff", emotion: "#897bff", glow: "#d1f3ff" },
};

const defaultPreset = emotionPresets.neutral;

const vertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uEnergy;
  varying float vWave;
  varying vec3 vTransformedNormal;

  void main() {
    float wave = (
      sin(position.x * 4.2 + uTime * 1.6) +
      sin(position.y * 6.8 - uTime * 1.3) +
      sin(position.z * 5.4 + uTime * 1.9)
    ) / 3.0;

    float energyFactor = clamp(uEnergy, 0.0, 1.0);
    float displacement = wave * (0.18 + energyFactor * 0.42);
    vec3 displacedPosition = position + normal * displacement;

    vWave = wave;
    vTransformedNormal = normalize(normalMatrix * normal);

    gl_Position = projectionMatrix * modelViewMatrix * vec4(displacedPosition, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform float uEnergy;
  uniform vec3 uBaseColor;
  uniform vec3 uEmotionColor;
  uniform vec3 uGlowColor;

  varying float vWave;
  varying vec3 vTransformedNormal;

  void main() {
    vec3 normal = normalize(vTransformedNormal);
    float fresnel = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 1.8);
    float pulse = 0.5 + 0.5 * sin(uTime * 3.0 + vWave * 6.0);
    float blend = clamp(pulse * (0.25 + uEnergy * 1.35), 0.0, 1.0);

    vec3 color = mix(uBaseColor, uEmotionColor, blend);
    color += uGlowColor * fresnel * (0.25 + uEnergy * 0.6);

    float alpha = clamp(0.55 + fresnel * 0.35 + uEnergy * 0.15, 0.0, 1.0);
    gl_FragColor = vec4(color, alpha);
  }
`;

const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1);

export default function LiquidSphere({
  speakingEnergy = 0,
  playbackEnergy = 0,
  emotion = "neutral",
}: LiquidSphereProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const uniformsRef = useRef<{
    uTime: { value: number };
    uEnergy: { value: number };
    uBaseColor: { value: THREE.Color };
    uEmotionColor: { value: THREE.Color };
    uGlowColor: { value: THREE.Color };
  } | null>(null);
  const energyStateRef = useRef({ current: 0, target: 0 });
  const animationRef = useRef<number>();
  const particlesRef = useRef<THREE.Points | null>(null);
  const rippleMeshRef = useRef<THREE.Mesh | null>(null);
  const rippleUniformsRef = useRef<{
    uTime: { value: number };
    uEnergy: { value: number };
    uColor: { value: THREE.Color };
  } | null>(null);
  const playbackStateRef = useRef({ current: 0, target: 0 });

  useEffect(() => {
    const mount = containerRef.current;
    if (!mount) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.z = 2.2;

    const geometry = new THREE.SphereGeometry(1, 160, 160);

    const uniforms = {
      uTime: { value: 0 },
      uEnergy: { value: 0 },
      uBaseColor: { value: new THREE.Color(defaultPreset.base) },
      uEmotionColor: { value: new THREE.Color(defaultPreset.emotion) },
      uGlowColor: { value: new THREE.Color(defaultPreset.glow) },
    };
    uniformsRef.current = uniforms;

    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader,
      transparent: true,
    });

    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const ambient = new THREE.AmbientLight(0xffffff, 0.35);
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.85);
    keyLight.position.set(2.5, 3.0, 4.0);
    scene.add(ambient);
    scene.add(keyLight);

    const particleCount = 520;
    const particleGeometry = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i += 1) {
      const vector = new THREE.Vector3().randomDirection().multiplyScalar(1.1 + Math.random() * 0.45);
      particlePositions[i * 3 + 0] = vector.x;
      particlePositions[i * 3 + 1] = vector.y;
      particlePositions[i * 3 + 2] = vector.z;
    }
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      size: 0.045,
      transparent: true,
      opacity: 0.45,
      depthWrite: false,
      color: defaultPreset.emotion,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);
    particlesRef.current = particles;

    const rippleUniforms = {
      uTime: { value: 0 },
      uEnergy: { value: 0 },
      uColor: { value: new THREE.Color(defaultPreset.glow) },
    };
    const rippleMaterial = new THREE.ShaderMaterial({
      uniforms: rippleUniforms,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */ `
        uniform float uTime;
        uniform float uEnergy;
        varying float vRadius;
        void main() {
          vec3 transformed = position;
          float pulse = 0.04 * sin(uTime * 2.2 + position.x * 3.0);
          transformed += normal * pulse * (0.5 + uEnergy * 1.2);
          vec4 mvPosition = modelViewMatrix * vec4(transformed, 1.0);
          vRadius = length(position.xy);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uEnergy;
        uniform vec3 uColor;
        varying float vRadius;
        void main() {
          float alpha = smoothstep(1.3, 0.9, vRadius);
          alpha *= 0.65 + uEnergy * 0.9;
          gl_FragColor = vec4(uColor, clamp(alpha, 0.0, 1.0));
        }
      `,
    });
    const rippleGeometry = new THREE.RingGeometry(1.05, 1.35, 256);
    const ripple = new THREE.Mesh(rippleGeometry, rippleMaterial);
    ripple.rotation.x = -Math.PI / 2;
    scene.add(ripple);
    rippleMeshRef.current = ripple;
    rippleUniformsRef.current = rippleUniforms;

    const resize = () => {
      if (!mount) return;
      const { clientWidth, clientHeight } = mount;
      const width = clientWidth || window.innerWidth;
      const height = clientHeight || window.innerHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    resize();
    window.addEventListener("resize", resize);

    const renderLoop = (time: number) => {
      const elapsed = time / 1000;
      const energy = energyStateRef.current;
      energy.current += (energy.target - energy.current) * 0.08;
      const playback = playbackStateRef.current;
      playback.current += (playback.target - playback.current) * 0.12;
      const rippleEnergy = Math.max(playback.current, energy.current * 0.85);

      const uniformsLocal = uniformsRef.current;
      if (uniformsLocal) {
        uniformsLocal.uTime.value = elapsed;
        uniformsLocal.uEnergy.value = energy.current;
      }

      if (particlesRef.current) {
        particlesRef.current.rotation.y += 0.002 + energy.current * 0.01;
        const particleMaterial = particlesRef.current.material as THREE.PointsMaterial;
        particleMaterial.size = 0.035 + energy.current * 0.07;
        particleMaterial.opacity = 0.3 + energy.current * 0.45;
      }

      if (rippleUniformsRef.current) {
        rippleUniformsRef.current.uTime.value = elapsed;
        rippleUniformsRef.current.uEnergy.value = rippleEnergy;
      }
      if (rippleMeshRef.current) {
        const rippleScale = 1.05 + rippleEnergy * 0.7 + Math.sin(elapsed * 1.8) * 0.05;
        rippleMeshRef.current.scale.setScalar(rippleScale);
        rippleMeshRef.current.rotation.z = elapsed * 0.4;
      }

      renderer.render(scene, camera);
      animationRef.current = requestAnimationFrame(renderLoop);
    };

    animationRef.current = requestAnimationFrame(renderLoop);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      window.removeEventListener("resize", resize);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      uniformsRef.current = null;
      energyStateRef.current = { current: 0, target: 0 };
      playbackStateRef.current = { current: 0, target: 0 };
      if (particlesRef.current) {
        scene.remove(particlesRef.current);
        (particlesRef.current.geometry as THREE.BufferGeometry).dispose();
        (particlesRef.current.material as THREE.PointsMaterial).dispose();
        particlesRef.current = null;
      }
      if (rippleMeshRef.current) {
        scene.remove(rippleMeshRef.current);
        rippleMeshRef.current.geometry.dispose();
        rippleMeshRef.current.material.dispose();
        rippleMeshRef.current = null;
        rippleUniformsRef.current = null;
      }
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      rendererRef.current = null;
    };
  }, []);

  useEffect(() => {
    const combined = speakingEnergy * 0.65 + playbackEnergy * 0.35;
    energyStateRef.current.target = clamp01(combined / 110);
    playbackStateRef.current.target = clamp01(playbackEnergy / 110);
  }, [speakingEnergy, playbackEnergy]);

  useEffect(() => {
    const preset = emotionPresets[emotion.toLowerCase()] ?? defaultPreset;
    const uniforms = uniformsRef.current;
    if (!uniforms) return;
    uniforms.uBaseColor.value.set(preset.base);
    uniforms.uEmotionColor.value.set(preset.emotion);
    uniforms.uGlowColor.value.set(preset.glow);
    if (particlesRef.current) {
      const particleMaterial = particlesRef.current.material as THREE.PointsMaterial;
      particleMaterial.color.set(preset.emotion);
    }
    if (rippleUniformsRef.current) {
      rippleUniformsRef.current.uColor.value.set(preset.glow);
    }
  }, [emotion]);

  return <div ref={containerRef} className="liquid-sphere-canvas" />;
}