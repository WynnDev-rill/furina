import { ContactShadows, Environment, OrbitControls, Sparkles } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { VrmAvatar } from "./VrmAvatar";

import type {
  CompanionEmotion,
  CompanionGaze,
  CompanionGesture,
  TouchRegion,
} from "@/lib/companion/types";

type CompanionStageProps = {
  emotion: CompanionEmotion;
  gesture: CompanionGesture;
  gaze: CompanionGaze;
  intensity: number;
  speaking: boolean;
  onTouch: (region: TouchRegion) => void;
};

const headTilt: Record<CompanionEmotion, number> = {
  neutral: 0,
  happy: -0.025,
  embarrassed: 0.075,
  annoyed: -0.055,
  worried: 0.045,
  sad: 0.085,
  surprised: -0.02,
  playful: -0.07,
};

const eyeOpen: Record<CompanionEmotion, number> = {
  neutral: 1,
  happy: 0.82,
  embarrassed: 0.88,
  annoyed: 0.72,
  worried: 1.05,
  sad: 0.72,
  surprised: 1.2,
  playful: 0.84,
};

function damp(object: THREE.Object3D | null, axis: "x" | "y" | "z", target: number, delta: number, speed = 6) {
  if (!object) return;
  object.rotation[axis] = THREE.MathUtils.damp(object.rotation[axis], target, speed, delta);
}

function OriginalAvatar({ emotion, gesture, gaze, intensity, speaking, onTouch }: CompanionStageProps) {
  const root = useRef<THREE.Group>(null);
  const torso = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const face = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const leftEye = useRef<THREE.Group>(null);
  const rightEye = useRef<THREE.Group>(null);
  const leftIris = useRef<THREE.Mesh>(null);
  const rightIris = useRef<THREE.Mesh>(null);
  const leftBrow = useRef<THREE.Mesh>(null);
  const rightBrow = useRef<THREE.Mesh>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const hairBack = useRef<THREE.Group>(null);
  const hairLeft = useRef<THREE.Group>(null);
  const hairRight = useRef<THREE.Group>(null);
  const waveHand = useRef<THREE.Group>(null);
  const blinkSeed = useMemo(() => Math.random() * 3.8, []);

  useFrame(({ clock, pointer }, delta) => {
    const t = clock.elapsedTime;
    const power = 0.55 + intensity * 0.65;
    const gazeX = gaze === "side" ? -0.46 : gaze === "down" ? 0.02 : pointer.x * 0.34;
    const gazeY = gaze === "down" ? -0.28 : pointer.y * 0.18;

    if (root.current) {
      root.current.position.y = -1.72 + Math.sin(t * 1.25) * 0.022;
      root.current.rotation.y = THREE.MathUtils.damp(root.current.rotation.y, pointer.x * 0.07, 4, delta);
      root.current.rotation.z = Math.sin(t * 0.58) * 0.006;
    }

    if (torso.current) {
      const lean = gesture === "lean_closer" ? 0.09 : gesture === "pout" ? -0.025 : 0;
      torso.current.rotation.x = THREE.MathUtils.damp(torso.current.rotation.x, lean, 5, delta);
      torso.current.rotation.z = THREE.MathUtils.damp(
        torso.current.rotation.z,
        gesture === "hands_on_hips" ? -0.025 : gesture === "shy_hair_touch" ? 0.035 : 0,
        5,
        delta,
      );
    }

    if (head.current) {
      head.current.rotation.x = THREE.MathUtils.damp(
        head.current.rotation.x,
        headTilt[emotion] + (gaze === "down" ? 0.07 : pointer.y * 0.025),
        5,
        delta,
      );
      head.current.rotation.y = THREE.MathUtils.damp(
        head.current.rotation.y,
        gaze === "side" ? -0.22 : pointer.x * 0.1,
        5,
        delta,
      );
      head.current.rotation.z = THREE.MathUtils.damp(
        head.current.rotation.z,
        emotion === "embarrassed" ? 0.045 : emotion === "playful" ? -0.04 : emotion === "sad" ? 0.025 : 0,
        5,
        delta,
      );
    }

    const blinkPhase = (t + blinkSeed) % 4.4;
    const blinking = blinkPhase > 4.17 || (blinkPhase > 2.22 && blinkPhase < 2.29);
    const targetEye = blinking ? 0.055 : eyeOpen[emotion];
    if (leftEye.current) leftEye.current.scale.y = THREE.MathUtils.damp(leftEye.current.scale.y, targetEye, 24, delta);
    if (rightEye.current) rightEye.current.scale.y = THREE.MathUtils.damp(rightEye.current.scale.y, targetEye, 24, delta);
    if (leftIris.current) {
      leftIris.current.position.x = THREE.MathUtils.damp(leftIris.current.position.x, gazeX * 0.032, 9, delta);
      leftIris.current.position.y = THREE.MathUtils.damp(leftIris.current.position.y, gazeY * 0.025, 9, delta);
    }
    if (rightIris.current) {
      rightIris.current.position.x = THREE.MathUtils.damp(rightIris.current.position.x, gazeX * 0.032, 9, delta);
      rightIris.current.position.y = THREE.MathUtils.damp(rightIris.current.position.y, gazeY * 0.025, 9, delta);
    }

    if (mouth.current) {
      const syllable = speaking
        ? 0.32 + Math.abs(Math.sin(t * 12.5) * 0.58 + Math.sin(t * 7.2) * 0.18)
        : emotion === "surprised" ? 0.5 : emotion === "happy" || emotion === "playful" ? 0.16 : 0.09;
      mouth.current.scale.y = THREE.MathUtils.damp(mouth.current.scale.y, syllable, 18, delta);
      mouth.current.scale.x = THREE.MathUtils.damp(
        mouth.current.scale.x,
        emotion === "annoyed" ? 0.72 : emotion === "surprised" ? 0.78 : 1,
        10,
        delta,
      );
      mouth.current.rotation.z = THREE.MathUtils.damp(
        mouth.current.rotation.z,
        emotion === "playful" ? -0.08 : emotion === "sad" ? 0.05 : 0,
        8,
        delta,
      );
    }

    const browConcern = emotion === "worried" || emotion === "sad";
    const browAnnoyed = emotion === "annoyed";
    if (leftBrow.current && rightBrow.current) {
      leftBrow.current.rotation.z = THREE.MathUtils.damp(leftBrow.current.rotation.z, browAnnoyed ? -0.18 : browConcern ? 0.14 : -0.035, 10, delta);
      rightBrow.current.rotation.z = THREE.MathUtils.damp(rightBrow.current.rotation.z, browAnnoyed ? 0.18 : browConcern ? -0.14 : 0.035, 10, delta);
      leftBrow.current.position.y = THREE.MathUtils.damp(leftBrow.current.position.y, emotion === "surprised" ? 0.335 : 0.29, 10, delta);
      rightBrow.current.position.y = THREE.MathUtils.damp(rightBrow.current.position.y, emotion === "surprised" ? 0.335 : 0.29, 10, delta);
    }

    const leftTargets = { x: 0.03, y: 0, z: -0.08 };
    const rightTargets = { x: 0.03, y: 0, z: 0.08 };
    if (gesture === "hands_on_hips") {
      leftTargets.x = -0.2; leftTargets.z = -0.72;
      rightTargets.x = -0.2; rightTargets.z = 0.72;
    } else if (gesture === "crossed_arms" || gesture === "pout") {
      leftTargets.x = -0.38; leftTargets.y = 0.12; leftTargets.z = -0.92;
      rightTargets.x = -0.38; rightTargets.y = -0.12; rightTargets.z = 0.92;
    } else if (gesture === "hand_to_chest") {
      rightTargets.x = -0.62; rightTargets.y = -0.18; rightTargets.z = 0.72;
    } else if (gesture === "shy_hair_touch") {
      rightTargets.x = -1.25; rightTargets.y = -0.18; rightTargets.z = 0.42;
    } else if (gesture === "small_wave") {
      rightTargets.x = -1.18; rightTargets.z = 0.2;
    } else if (gesture === "thinking") {
      rightTargets.x = -1.02; rightTargets.y = -0.12; rightTargets.z = 0.32;
    } else if (gesture === "lean_closer") {
      leftTargets.x = -0.12; leftTargets.z = -0.25;
      rightTargets.x = -0.12; rightTargets.z = 0.25;
    }
    damp(leftArm.current, "x", leftTargets.x * power, delta, 7);
    damp(leftArm.current, "y", leftTargets.y, delta, 7);
    damp(leftArm.current, "z", leftTargets.z * power, delta, 7);
    damp(rightArm.current, "x", rightTargets.x * power, delta, 7);
    damp(rightArm.current, "y", rightTargets.y, delta, 7);
    damp(rightArm.current, "z", rightTargets.z * power, delta, 7);

    if (waveHand.current) {
      waveHand.current.rotation.z = gesture === "small_wave" ? Math.sin(t * 7) * 0.22 : 0;
    }

    if (hairBack.current) hairBack.current.rotation.z = Math.sin(t * 0.92) * 0.012 - pointer.x * 0.012;
    if (hairLeft.current) hairLeft.current.rotation.z = THREE.MathUtils.damp(hairLeft.current.rotation.z, 0.06 + Math.sin(t * 1.15) * 0.025 - pointer.x * 0.025, 4, delta);
    if (hairRight.current) hairRight.current.rotation.z = THREE.MathUtils.damp(hairRight.current.rotation.z, -0.06 - Math.sin(t * 1.08) * 0.025 - pointer.x * 0.025, 4, delta);
    if (face.current) face.current.position.y = Math.sin(t * 1.25) * 0.0015;
  });

  const irisColor = emotion === "annoyed" ? "#bb7ad8" : emotion === "surprised" ? "#b8eea7" : "#a8dfa0";
  const cheekOpacity = emotion === "embarrassed" ? 0.72 : emotion === "happy" || emotion === "playful" ? 0.3 : 0.08;
  const cardigan = "#f1dfcf";
  const cardiganShade = "#d9c1b0";
  const hair = "#e982ab";
  const hairLight = "#f3a0bd";

  return (
    <group ref={root} position={[0, -1.72, 0]}>
      <group ref={torso} position={[0, 0, 0]} onPointerDown={(event) => { event.stopPropagation(); onTouch("body"); }}>
        <mesh position={[0, 0.56, 0]} scale={[1.02, 1.22, 0.66]} castShadow>
          <capsuleGeometry args={[0.58, 1.05, 12, 28]} />
          <meshToonMaterial color={cardigan} />
        </mesh>
        <mesh position={[0, 0.83, 0.54]} scale={[0.74, 0.62, 0.1]}>
          <sphereGeometry args={[0.69, 32, 24]} />
          <meshToonMaterial color="#fff8f0" />
        </mesh>
        <mesh position={[0, 0.63, 0.65]} scale={[0.24, 0.42, 0.05]}>
          <capsuleGeometry args={[0.14, 0.3, 8, 16]} />
          <meshToonMaterial color="#f6eae1" />
        </mesh>
        <mesh position={[0, 0.12, 0.62]} scale={[0.82, 0.08, 0.09]}>
          <torusGeometry args={[0.48, 0.065, 12, 32, Math.PI]} />
          <meshToonMaterial color={cardiganShade} />
        </mesh>
        {[0.2, 0.47, 0.74].map((y) => (
          <mesh key={y} position={[0, y, 0.69]}>
            <sphereGeometry args={[0.055, 18, 12]} />
            <meshStandardMaterial color="#b5947b" roughness={0.7} metalness={0.15} />
          </mesh>
        ))}
        <mesh position={[0, -0.52, 0]} scale={[1.18, 0.75, 0.76]}>
          <sphereGeometry args={[0.82, 32, 22]} />
          <meshToonMaterial color="#6a405e" />
        </mesh>
        <mesh position={[0, 1.23, 0.06]}>
          <cylinderGeometry args={[0.19, 0.22, 0.35, 24]} />
          <meshToonMaterial color="#ffd9cf" />
        </mesh>
        <mesh position={[0, 1.18, 0.27]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.26, 0.022, 10, 28, Math.PI * 1.45]} />
          <meshStandardMaterial color="#d8b48b" metalness={0.5} roughness={0.35} />
        </mesh>

        <group ref={leftArm} position={[-0.74, 0.92, 0]} onPointerDown={(event) => { event.stopPropagation(); onTouch("shoulder"); }}>
          <mesh position={[0, -0.54, 0]} rotation={[0, 0, -0.06]} castShadow>
            <capsuleGeometry args={[0.22, 0.92, 10, 20]} />
            <meshToonMaterial color={cardigan} />
          </mesh>
          <mesh position={[-0.03, -1.14, 0.02]} onPointerDown={(event) => { event.stopPropagation(); onTouch("hand"); }}>
            <sphereGeometry args={[0.21, 24, 18]} />
            <meshToonMaterial color="#ffd9cf" />
          </mesh>
          <mesh position={[0.08, -0.48, 0.21]} rotation={[0, 0, 0.12]} scale={[0.45, 1.8, 0.12]}>
            <boxGeometry args={[0.11, 0.45, 0.07]} />
            <meshToonMaterial color={cardiganShade} />
          </mesh>
        </group>

        <group ref={rightArm} position={[0.74, 0.92, 0]} onPointerDown={(event) => { event.stopPropagation(); onTouch("shoulder"); }}>
          <mesh position={[0, -0.54, 0]} rotation={[0, 0, 0.06]} castShadow>
            <capsuleGeometry args={[0.22, 0.92, 10, 20]} />
            <meshToonMaterial color={cardigan} />
          </mesh>
          <group ref={waveHand} position={[0.03, -1.14, 0.02]} onPointerDown={(event) => { event.stopPropagation(); onTouch("hand"); }}>
            <mesh>
              <sphereGeometry args={[0.21, 24, 18]} />
              <meshToonMaterial color="#ffd9cf" />
            </mesh>
          </group>
          <mesh position={[-0.08, -0.48, 0.21]} rotation={[0, 0, -0.12]} scale={[0.45, 1.8, 0.12]}>
            <boxGeometry args={[0.11, 0.45, 0.07]} />
            <meshToonMaterial color={cardiganShade} />
          </mesh>
        </group>
      </group>

      <group ref={head} position={[0, 2.05, 0]} onPointerDown={(event) => { event.stopPropagation(); onTouch("head"); }}>
        <group ref={hairBack} position={[0, 0.05, -0.28]}>
          <mesh scale={[1.08, 1.14, 0.82]} castShadow>
            <sphereGeometry args={[0.79, 48, 32]} />
            <meshToonMaterial color={hair} />
          </mesh>
          <mesh position={[0, -0.76, -0.16]} scale={[0.92, 1.18, 0.55]}>
            <capsuleGeometry args={[0.52, 0.96, 12, 28]} />
            <meshToonMaterial color={hair} />
          </mesh>
        </group>

        <mesh scale={[1, 1.08, 0.88]} castShadow>
          <sphereGeometry args={[0.71, 48, 36]} />
          <meshToonMaterial color="#ffddd4" />
        </mesh>

        <group ref={hairLeft} position={[-0.55, -0.18, -0.06]}>
          <mesh rotation={[0.03, 0.08, 0.12]} scale={[0.42, 1.5, 0.34]}>
            <capsuleGeometry args={[0.24, 0.92, 10, 20]} />
            <meshToonMaterial color={hair} />
          </mesh>
          <mesh position={[-0.03, -0.78, 0.03]} rotation={[0, 0, -0.08]} scale={[0.24, 0.76, 0.22]}>
            <capsuleGeometry args={[0.2, 0.7, 8, 18]} />
            <meshToonMaterial color={hairLight} />
          </mesh>
        </group>
        <group ref={hairRight} position={[0.55, -0.18, -0.06]}>
          <mesh rotation={[0.03, -0.08, -0.12]} scale={[0.42, 1.5, 0.34]}>
            <capsuleGeometry args={[0.24, 0.92, 10, 20]} />
            <meshToonMaterial color={hair} />
          </mesh>
          <mesh position={[0.03, -0.78, 0.03]} rotation={[0, 0, 0.08]} scale={[0.24, 0.76, 0.22]}>
            <capsuleGeometry args={[0.2, 0.7, 8, 18]} />
            <meshToonMaterial color={hairLight} />
          </mesh>
        </group>

        <mesh position={[0, 0.5, 0.32]} rotation={[0.1, 0, -0.06]} scale={[0.74, 0.62, 0.15]}>
          <sphereGeometry args={[0.56, 34, 22]} />
          <meshToonMaterial color={hairLight} />
        </mesh>
        <mesh position={[-0.28, 0.43, 0.53]} rotation={[0, 0.18, 0.2]} scale={[0.27, 0.72, 0.1]}>
          <capsuleGeometry args={[0.16, 0.46, 8, 16]} />
          <meshToonMaterial color={hairLight} />
        </mesh>
        <mesh position={[0.25, 0.43, 0.54]} rotation={[0, -0.18, -0.16]} scale={[0.31, 0.76, 0.1]}>
          <capsuleGeometry args={[0.16, 0.48, 8, 16]} />
          <meshToonMaterial color={hairLight} />
        </mesh>
        <mesh position={[0.51, 0.3, 0.55]} rotation={[0.08, -0.25, -0.27]} scale={[0.21, 0.66, 0.1]}>
          <capsuleGeometry args={[0.14, 0.42, 8, 16]} />
          <meshToonMaterial color={hair} />
        </mesh>

        <group position={[0.52, 0.47, 0.61]} rotation={[0, 0, -0.15]}>
          <mesh rotation={[0, 0, Math.PI / 4]}>
            <boxGeometry args={[0.15, 0.15, 0.035]} />
            <meshStandardMaterial color="#e8bf6b" metalness={0.6} roughness={0.25} />
          </mesh>
          <mesh position={[0.13, -0.06, 0]} rotation={[0, 0, Math.PI / 4]}>
            <boxGeometry args={[0.1, 0.1, 0.035]} />
            <meshStandardMaterial color="#f0d797" metalness={0.55} roughness={0.28} />
          </mesh>
        </group>

        <group ref={face} position={[0, 0, 0.635]} onPointerDown={(event) => { event.stopPropagation(); onTouch("face"); }}>
          <group ref={leftEye} position={[-0.235, 0.11, 0]}>
            <mesh scale={[1.22, 0.88, 0.45]}>
              <sphereGeometry args={[0.125, 28, 18]} />
              <meshBasicMaterial color="#fffdfb" />
            </mesh>
            <mesh ref={leftIris} position={[0, 0, 0.107]} scale={[0.75, 1, 0.35]}>
              <sphereGeometry args={[0.083, 24, 16]} />
              <meshToonMaterial color={irisColor} />
            </mesh>
            <mesh position={[0, -0.002, 0.154]} scale={[0.6, 0.86, 0.28]}>
              <sphereGeometry args={[0.052, 18, 12]} />
              <meshBasicMaterial color="#68466f" />
            </mesh>
            <mesh position={[-0.018, 0.03, 0.186]}>
              <sphereGeometry args={[0.015, 12, 8]} />
              <meshBasicMaterial color="#ffffff" />
            </mesh>
          </group>
          <group ref={rightEye} position={[0.235, 0.11, 0]}>
            <mesh scale={[1.22, 0.88, 0.45]}>
              <sphereGeometry args={[0.125, 28, 18]} />
              <meshBasicMaterial color="#fffdfb" />
            </mesh>
            <mesh ref={rightIris} position={[0, 0, 0.107]} scale={[0.75, 1, 0.35]}>
              <sphereGeometry args={[0.083, 24, 16]} />
              <meshToonMaterial color={irisColor} />
            </mesh>
            <mesh position={[0, -0.002, 0.154]} scale={[0.6, 0.86, 0.28]}>
              <sphereGeometry args={[0.052, 18, 12]} />
              <meshBasicMaterial color="#68466f" />
            </mesh>
            <mesh position={[-0.018, 0.03, 0.186]}>
              <sphereGeometry args={[0.015, 12, 8]} />
              <meshBasicMaterial color="#ffffff" />
            </mesh>
          </group>

          <mesh ref={leftBrow} position={[-0.235, 0.29, 0.03]} rotation={[0, 0, -0.035]} scale={[1.25, 0.23, 0.2]}>
            <capsuleGeometry args={[0.035, 0.16, 6, 12]} />
            <meshBasicMaterial color="#9e5577" />
          </mesh>
          <mesh ref={rightBrow} position={[0.235, 0.29, 0.03]} rotation={[0, 0, 0.035]} scale={[1.25, 0.23, 0.2]}>
            <capsuleGeometry args={[0.035, 0.16, 6, 12]} />
            <meshBasicMaterial color="#9e5577" />
          </mesh>

          <mesh position={[0, -0.01, 0.035]} scale={[0.3, 0.54, 0.2]}>
            <sphereGeometry args={[0.065, 16, 12]} />
            <meshToonMaterial color="#efb4aa" />
          </mesh>
          <mesh ref={mouth} position={[0, -0.24, 0.025]} scale={[1, 0.1, 0.32]}>
            <sphereGeometry args={[0.092, 24, 14]} />
            <meshToonMaterial color={emotion === "annoyed" ? "#98516b" : "#c86982"} />
          </mesh>
          <mesh position={[-0.37, -0.08, -0.004]} scale={[1, 0.3, 0.18]}>
            <sphereGeometry args={[0.12, 18, 12]} />
            <meshBasicMaterial color="#ef8fa7" transparent opacity={cheekOpacity} />
          </mesh>
          <mesh position={[0.37, -0.08, -0.004]} scale={[1, 0.3, 0.18]}>
            <sphereGeometry args={[0.12, 18, 12]} />
            <meshBasicMaterial color="#ef8fa7" transparent opacity={cheekOpacity} />
          </mesh>
        </group>

        <group position={[-0.74, -0.05, 0.06]}>
          <mesh>
            <torusGeometry args={[0.09, 0.018, 10, 22]} />
            <meshStandardMaterial color="#e8c38f" metalness={0.65} roughness={0.25} />
          </mesh>
          <mesh position={[0, -0.12, 0]} rotation={[0, 0, Math.PI / 4]}>
            <boxGeometry args={[0.09, 0.09, 0.025]} />
            <meshStandardMaterial color="#f1cfa0" metalness={0.5} roughness={0.3} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

type Quality = "low" | "medium" | "high";

function detectQuality(): Quality {
  if (typeof navigator === "undefined") return "medium";
  const cores = navigator.hardwareConcurrency ?? 4;
  const memory = (navigator as unknown as { deviceMemory?: number }).deviceMemory ?? 4;
  if (cores <= 4 || memory <= 3) return "low";
  if (cores >= 8 && memory >= 8) return "high";
  return "medium";
}

export function CompanionStage(props: CompanionStageProps & { quality?: Quality }) {
  const [quality, setQuality] = useState<Quality>("medium");
  const [mode, setMode] = useState<"loading" | "vrm" | "procedural">("loading");
  const [active, setActive] = useState(true);

  useEffect(() => {
    setQuality(props.quality ?? detectQuality());
  }, [props.quality]);

  useEffect(() => {
    const onVisibility = () => setActive(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const dpr: [number, number] = quality === "low" ? [1, 1.1] : quality === "high" ? [1, 2] : [1, 1.6];

  return (
    <div className="relative h-full min-h-[460px] w-full overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_50%_24%,rgba(255,206,224,0.32),transparent_34%),radial-gradient(circle_at_20%_74%,rgba(155,132,255,0.18),transparent_35%),linear-gradient(180deg,#24192e_0%,#100d19_76%)]">
      <Canvas
        camera={{ position: [0, 1.32, 1.75], fov: 30 }}
        dpr={dpr}
        frameloop={active ? "always" : "demand"}
        gl={{ antialias: quality !== "low", alpha: true, powerPreference: "high-performance" }}
        shadows={quality !== "low"}
      >
        <ambientLight intensity={1.25} />
        <hemisphereLight args={["#ffe6ef", "#342345", 1.45]} />
        <directionalLight position={[3.5, 5.5, 4.2]} intensity={2.35} color="#fff0f5" castShadow={quality !== "low"} />
        <directionalLight position={[-4, 2.5, 2]} intensity={1.15} color="#c8beff" />
        <pointLight position={[0, 2.2, 3]} intensity={0.8} color="#ffbad2" distance={6} />
        <Suspense fallback={null}>
          {mode === "procedural" ? (
            <group position={[0, 1.3, 0]} scale={0.52}>
              <OriginalAvatar {...props} />
            </group>
          ) : (
            <VrmAvatar
              {...props}
              quality={quality}
              onReady={() => setMode("vrm")}
              onFailed={() => setMode("procedural")}
            />
          )}
          {quality !== "low" && (
            <Sparkles count={26} scale={[1.6, 2, 1]} position={[0, 1.2, 0]} size={1.4} speed={0.2} opacity={0.26} color="#ffd7e5" />
          )}
          <ContactShadows position={[0, 0.001, 0]} opacity={0.32} scale={2.4} blur={2.5} far={2} />
          <Environment preset="city" environmentIntensity={0.24} />
        </Suspense>
        <OrbitControls
          enablePan={false}
          enableZoom={false}
          minPolarAngle={Math.PI * 0.43}
          maxPolarAngle={Math.PI * 0.57}
          minAzimuthAngle={-0.3}
          maxAzimuthAngle={0.3}
          target={[0, 1.3, 0]}
        />
      </Canvas>

      {mode === "loading" && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-4 py-2 text-[11px] text-white/60 backdrop-blur-xl">
            <span className="size-2 animate-ping rounded-full bg-pink-300" />
            Memuat model 3D…
          </div>
        </div>
      )}
      <div className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-inset ring-white/10" />
    </div>
  );
}
