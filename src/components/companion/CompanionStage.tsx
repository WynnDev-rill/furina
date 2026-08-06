import { ContactShadows, Environment, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";

import type { CompanionEmotion, TouchRegion } from "@/lib/companion/types";

type CompanionStageProps = {
  emotion: CompanionEmotion;
  speaking: boolean;
  onTouch: (region: TouchRegion) => void;
};

type AvatarProps = CompanionStageProps;

const expressionTilt: Record<CompanionEmotion, number> = {
  neutral: 0,
  happy: -0.035,
  embarrassed: 0.08,
  annoyed: -0.07,
  worried: 0.055,
  sad: 0.08,
  surprised: -0.02,
  playful: -0.09,
};

function ProceduralAvatar({ emotion, speaking, onTouch }: AvatarProps) {
  const root = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const leftEye = useRef<THREE.Mesh>(null);
  const rightEye = useRef<THREE.Mesh>(null);
  const blinkSeed = useMemo(() => Math.random() * 4, []);

  useFrame(({ clock, pointer }, delta) => {
    const time = clock.elapsedTime;
    if (root.current) {
      root.current.position.y = -1.1 + Math.sin(time * 1.35) * 0.025;
      root.current.rotation.y = THREE.MathUtils.damp(
        root.current.rotation.y,
        pointer.x * 0.12,
        4,
        delta,
      );
    }
    if (head.current) {
      head.current.rotation.x = THREE.MathUtils.damp(
        head.current.rotation.x,
        expressionTilt[emotion] + pointer.y * 0.045,
        5,
        delta,
      );
      head.current.rotation.z = THREE.MathUtils.damp(
        head.current.rotation.z,
        emotion === "embarrassed" ? 0.045 : emotion === "playful" ? -0.04 : 0,
        5,
        delta,
      );
    }

    const blinkWave = Math.sin((time + blinkSeed) * 0.72);
    const blinking = blinkWave > 0.992;
    const eyeScale = blinking ? 0.08 : emotion === "happy" ? 0.78 : 1;
    if (leftEye.current) leftEye.current.scale.y = THREE.MathUtils.damp(leftEye.current.scale.y, eyeScale, 20, delta);
    if (rightEye.current) rightEye.current.scale.y = THREE.MathUtils.damp(rightEye.current.scale.y, eyeScale, 20, delta);

    if (mouth.current) {
      const talking = speaking ? 0.65 + Math.abs(Math.sin(time * 12)) * 0.75 : 0.25;
      mouth.current.scale.y = THREE.MathUtils.damp(mouth.current.scale.y, talking, 18, delta);
      mouth.current.scale.x = THREE.MathUtils.damp(
        mouth.current.scale.x,
        emotion === "annoyed" ? 0.72 : emotion === "surprised" ? 0.8 : 1,
        10,
        delta,
      );
    }
  });

  const eyeColor = emotion === "annoyed" ? "#9d6cbe" : "#a9df9e";
  const cheekOpacity = emotion === "embarrassed" ? 0.8 : emotion === "happy" ? 0.35 : 0.12;

  return (
    <group ref={root} position={[0, -1.1, 0]}>
      <group onPointerDown={(event) => { event.stopPropagation(); onTouch("body"); }}>
        <mesh position={[0, 0.15, 0]} scale={[1.08, 1.32, 0.72]}>
          <capsuleGeometry args={[0.68, 1.1, 10, 24]} />
          <meshToonMaterial color="#f5e5da" />
        </mesh>
        <mesh position={[0, 0.75, 0.57]} scale={[0.92, 0.62, 0.12]}>
          <sphereGeometry args={[0.72, 32, 24]} />
          <meshToonMaterial color="#fff9f2" />
        </mesh>
        <mesh position={[-0.79, 0.18, 0.03]} rotation={[0, 0, -0.12]} onPointerDown={(event) => { event.stopPropagation(); onTouch("shoulder"); }}>
          <capsuleGeometry args={[0.22, 1.15, 8, 16]} />
          <meshToonMaterial color="#f3e1d2" />
        </mesh>
        <mesh position={[0.79, 0.18, 0.03]} rotation={[0, 0, 0.12]} onPointerDown={(event) => { event.stopPropagation(); onTouch("shoulder"); }}>
          <capsuleGeometry args={[0.22, 1.15, 8, 16]} />
          <meshToonMaterial color="#f3e1d2" />
        </mesh>
        <mesh position={[-0.92, -0.62, 0.1]} onPointerDown={(event) => { event.stopPropagation(); onTouch("hand"); }}>
          <sphereGeometry args={[0.2, 20, 16]} />
          <meshToonMaterial color="#ffd9ce" />
        </mesh>
        <mesh position={[0.92, -0.62, 0.1]} onPointerDown={(event) => { event.stopPropagation(); onTouch("hand"); }}>
          <sphereGeometry args={[0.2, 20, 16]} />
          <meshToonMaterial color="#ffd9ce" />
        </mesh>
      </group>

      <group ref={head} position={[0, 1.66, 0]} onPointerDown={(event) => { event.stopPropagation(); onTouch("head"); }}>
        <mesh position={[0, 0, -0.12]} scale={[1.12, 1.12, 0.92]}>
          <sphereGeometry args={[0.72, 48, 32]} />
          <meshToonMaterial color="#ffddd4" />
        </mesh>

        <mesh position={[0, 0.18, -0.37]} scale={[1.24, 1.25, 0.86]}>
          <sphereGeometry args={[0.76, 40, 28, 0, Math.PI * 2, 0, Math.PI * 0.74]} />
          <meshToonMaterial color="#ef86ac" side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[-0.54, -0.12, -0.27]} rotation={[0.06, 0.16, 0.14]} scale={[0.38, 1.45, 0.32]}>
          <capsuleGeometry args={[0.25, 1.02, 10, 18]} />
          <meshToonMaterial color="#ed84aa" />
        </mesh>
        <mesh position={[0.55, -0.12, -0.27]} rotation={[0.06, -0.16, -0.14]} scale={[0.38, 1.45, 0.32]}>
          <capsuleGeometry args={[0.25, 1.02, 10, 18]} />
          <meshToonMaterial color="#ed84aa" />
        </mesh>
        <mesh position={[0.03, 0.54, 0.41]} rotation={[0.1, 0, -0.08]} scale={[0.62, 0.68, 0.12]}>
          <sphereGeometry args={[0.55, 28, 18]} />
          <meshToonMaterial color="#f49abc" />
        </mesh>

        <group position={[0, 0.05, 0.61]} onPointerDown={(event) => { event.stopPropagation(); onTouch("face"); }}>
          <mesh ref={leftEye} position={[-0.25, 0.08, 0]} scale={[1, 1, 0.45]}>
            <sphereGeometry args={[0.115, 24, 16]} />
            <meshToonMaterial color={eyeColor} />
          </mesh>
          <mesh ref={rightEye} position={[0.25, 0.08, 0]} scale={[1, 1, 0.45]}>
            <sphereGeometry args={[0.115, 24, 16]} />
            <meshToonMaterial color={eyeColor} />
          </mesh>
          <mesh position={[-0.25, 0.088, 0.105]} scale={[1, 1, 0.3]}>
            <sphereGeometry args={[0.047, 18, 12]} />
            <meshBasicMaterial color="#4b365e" />
          </mesh>
          <mesh position={[0.25, 0.088, 0.105]} scale={[1, 1, 0.3]}>
            <sphereGeometry args={[0.047, 18, 12]} />
            <meshBasicMaterial color="#4b365e" />
          </mesh>
          <mesh ref={mouth} position={[0, -0.23, 0.035]} scale={[1, 0.25, 0.35]}>
            <sphereGeometry args={[0.09, 20, 12]} />
            <meshToonMaterial color={emotion === "annoyed" ? "#9e536b" : "#c86f83"} />
          </mesh>
          <mesh position={[-0.38, -0.1, -0.005]} scale={[1, 0.32, 0.2]}>
            <sphereGeometry args={[0.12, 16, 10]} />
            <meshBasicMaterial color="#f28fa4" transparent opacity={cheekOpacity} />
          </mesh>
          <mesh position={[0.38, -0.1, -0.005]} scale={[1, 0.32, 0.2]}>
            <sphereGeometry args={[0.12, 16, 10]} />
            <meshBasicMaterial color="#f28fa4" transparent opacity={cheekOpacity} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

export function CompanionStage(props: CompanionStageProps) {
  return (
    <div className="h-full min-h-[420px] w-full overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_50%_30%,rgba(255,210,225,0.42),transparent_42%),linear-gradient(180deg,#221b33_0%,#11101c_72%)]">
      <Canvas
        camera={{ position: [0, 1.1, 5.4], fov: 34 }}
        dpr={[1, 1.65]}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <ambientLight intensity={1.35} />
        <directionalLight position={[3, 5, 4]} intensity={2.2} color="#fff1f6" />
        <directionalLight position={[-4, 2, 2]} intensity={1.1} color="#b9b5ff" />
        <Suspense fallback={null}>
          <ProceduralAvatar {...props} />
          <ContactShadows position={[0, -2.15, 0]} opacity={0.42} scale={4.5} blur={2.4} far={4} />
          <Environment preset="city" environmentIntensity={0.28} />
        </Suspense>
        <OrbitControls
          enablePan={false}
          enableZoom={false}
          minPolarAngle={Math.PI * 0.42}
          maxPolarAngle={Math.PI * 0.58}
          target={[0, 0.6, 0]}
        />
      </Canvas>
    </div>
  );
}
