import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import mireiAsset from "@/assets/mirei.vrm.asset.json";
import type {
  CompanionEmotion,
  CompanionGaze,
  CompanionGesture,
  TouchRegion,
} from "@/lib/companion/types";
import { getVoiceLevel } from "@/lib/companion/voice";

export const VRM_MODEL_URL = mireiAsset.url;

type VrmAvatarProps = {
  emotion: CompanionEmotion;
  gesture: CompanionGesture;
  gaze: CompanionGaze;
  intensity: number;
  speaking: boolean;
  onTouch: (region: TouchRegion) => void;
  onReady: () => void;
  onFailed: () => void;
  quality: "low" | "medium" | "high";
};

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyVrm = any;

const EXPRESSION_BY_EMOTION: Record<CompanionEmotion, { name: string; weight: number }[]> = {
  neutral: [{ name: "neutral", weight: 0.35 }],
  happy: [{ name: "happy", weight: 0.85 }],
  embarrassed: [
    { name: "happy", weight: 0.28 },
    { name: "relaxed", weight: 0.45 },
  ],
  annoyed: [{ name: "angry", weight: 0.72 }],
  worried: [{ name: "sad", weight: 0.5 }],
  sad: [{ name: "sad", weight: 0.85 }],
  surprised: [{ name: "surprised", weight: 0.8 }],
  playful: [
    { name: "happy", weight: 0.62 },
    { name: "relaxed", weight: 0.25 },
  ],
};

const ALL_EXPRESSIONS = ["neutral", "happy", "angry", "sad", "relaxed", "surprised"] as const;

type ArmPose = {
  upperL: [number, number, number];
  lowerL: [number, number, number];
  upperR: [number, number, number];
  lowerR: [number, number, number];
};

const REST_POSE: ArmPose = {
  upperL: [0.05, 0, 1.28],
  lowerL: [0, -0.18, 0.16],
  upperR: [0.05, 0, -1.28],
  lowerR: [0, 0.18, -0.16],
};

function pose(partial: Partial<ArmPose>): ArmPose {
  return { ...REST_POSE, ...partial };
}

const GESTURE_POSE: Record<CompanionGesture, ArmPose> = {
  idle: REST_POSE,
  soft_smile: pose({ upperL: [0.02, 0, 1.24], upperR: [0.02, 0, -1.24] }),
  look_away: pose({ upperL: [0.08, 0, 1.3], upperR: [0.1, 0, -1.22] }),
  hands_on_hips: pose({
    upperL: [0.1, 0, 0.95],
    lowerL: [0, -1.15, 0.3],
    upperR: [0.1, 0, -0.95],
    lowerR: [0, 1.15, -0.3],
  }),
  lean_closer: pose({ upperL: [0.18, 0, 1.15], upperR: [0.18, 0, -1.15] }),
  small_wave: pose({
    upperR: [0.05, 0, -0.35],
    lowerR: [0, 0.35, -0.55],
  }),
  thinking: pose({
    upperR: [0.1, 0, -0.55],
    lowerR: [0.15, 1.1, -0.9],
    upperL: [0.08, 0, 1.18],
    lowerL: [0, -0.55, 0.32],
  }),
  pout: pose({
    upperL: [0.12, 0, 0.72],
    lowerL: [0, -1.35, 0.42],
    upperR: [0.12, 0, -0.72],
    lowerR: [0, 1.35, -0.42],
  }),
  crossed_arms: pose({
    upperL: [0.16, 0, 0.68],
    lowerL: [0, -1.5, 0.5],
    upperR: [0.16, 0, -0.68],
    lowerR: [0, 1.5, -0.5],
  }),
  hand_to_chest: pose({
    upperR: [0.12, 0, -0.7],
    lowerR: [0, 1.35, -0.7],
  }),
  shy_hair_touch: pose({
    upperR: [0.05, 0, -0.42],
    lowerR: [0.1, 0.55, -1.45],
  }),
};

const HEAD_TILT: Record<CompanionEmotion, number> = {
  neutral: 0,
  happy: -0.03,
  embarrassed: 0.09,
  annoyed: -0.06,
  worried: 0.05,
  sad: 0.11,
  surprised: -0.03,
  playful: -0.08,
};

type Hitbox = { region: TouchRegion; bone: string; radius: number; offset: [number, number, number] };

const HITBOXES: Hitbox[] = [
  { region: "head", bone: "head", radius: 0.14, offset: [0, 0.11, -0.01] },
  { region: "face", bone: "head", radius: 0.1, offset: [0, 0.03, 0.1] },
  { region: "shoulder", bone: "leftUpperArm", radius: 0.09, offset: [0, 0, 0] },
  { region: "shoulder", bone: "rightUpperArm", radius: 0.09, offset: [0, 0, 0] },
  { region: "hand", bone: "leftHand", radius: 0.09, offset: [0, 0, 0] },
  { region: "hand", bone: "rightHand", radius: 0.09, offset: [0, 0, 0] },
  { region: "body", bone: "chest", radius: 0.2, offset: [0, 0.02, 0.02] },
];

function damp(current: number, target: number, lambda: number, delta: number) {
  return THREE.MathUtils.damp(current, target, lambda, delta);
}

export function VrmAvatar({
  emotion,
  gesture,
  gaze,
  intensity,
  speaking,
  onTouch,
  onReady,
  onFailed,
  quality,
}: VrmAvatarProps) {
  const { camera } = useThree();
  const [vrm, setVrm] = useState<AnyVrm | null>(null);
  const root = useRef<THREE.Group>(null);
  const hitRefs = useRef<(THREE.Mesh | null)[]>([]);
  const blinkSeed = useMemo(() => Math.random() * 4, []);
  const mouthRef = useRef(0);
  const lookTarget = useMemo(() => new THREE.Object3D(), []);
  const bonePosition = useMemo(() => new THREE.Vector3(), []);

  useEffect(() => {
    let disposed = false;
    let loaded: AnyVrm | null = null;

    void (async () => {
      try {
        const [{ GLTFLoader }, vrmModule] = await Promise.all([
          import("three/examples/jsm/loaders/GLTFLoader.js"),
          import("@pixiv/three-vrm"),
        ]);
        const loader = new GLTFLoader();
        loader.register((parser) => new vrmModule.VRMLoaderPlugin(parser));
        const gltf = await loader.loadAsync(VRM_MODEL_URL);
        const instance = gltf.userData.vrm as AnyVrm;
        if (!instance) throw new Error("model has no VRM data");
        if (disposed) {
          vrmModule.VRMUtils.deepDispose(gltf.scene);
          return;
        }
        vrmModule.VRMUtils.removeUnnecessaryVertices(gltf.scene);
        vrmModule.VRMUtils.combineSkeletons(gltf.scene);
        instance.scene.traverse((object: THREE.Object3D) => {
          object.frustumCulled = false;
          const mesh = object as THREE.Mesh;
          if (mesh.isMesh) {
            mesh.castShadow = quality !== "low";
            mesh.receiveShadow = false;
          }
        });
        instance.scene.rotation.y = Math.PI;
        loaded = instance;
        setVrm(instance);
        onReady();
      } catch (error) {
        console.error("VRM load failed", error);
        if (!disposed) onFailed();
      }
    })();

    return () => {
      disposed = true;
      if (loaded) {
        void import("@pixiv/three-vrm").then((module) => module.VRMUtils.deepDispose(loaded!.scene));
      }
    };
    // Load once; quality only affects shadow flags on first build.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!vrm) return;
    camera.add(lookTarget);
    lookTarget.position.set(0, 0, -1);
    vrm.lookAt && (vrm.lookAt.target = lookTarget);
    return () => {
      camera.remove(lookTarget);
    };
  }, [camera, lookTarget, vrm]);

  useFrame(({ clock, pointer }, delta) => {
    if (!vrm) return;
    const step = Math.min(delta, 0.05);
    const t = clock.elapsedTime;
    const power = 0.55 + intensity * 0.6;
    const humanoid = vrm.humanoid;

    // Expressions
    const manager = vrm.expressionManager;
    if (manager) {
      const targets = new Map<string, number>();
      for (const item of EXPRESSION_BY_EMOTION[emotion]) {
        targets.set(item.name, item.weight * (0.55 + intensity * 0.55));
      }
      for (const name of ALL_EXPRESSIONS) {
        const current = manager.getValue(name) ?? 0;
        manager.setValue(name, damp(current, targets.get(name) ?? 0, 7, step));
      }

      const blinkPhase = (t + blinkSeed) % 4.6;
      const blinking = blinkPhase > 4.42 || (blinkPhase > 2.3 && blinkPhase < 2.38);
      manager.setValue("blink", damp(manager.getValue("blink") ?? 0, blinking ? 1 : 0, 26, step));

      const level = speaking ? getVoiceLevel() : 0;
      const procedural = speaking
        ? 0.22 + Math.abs(Math.sin(t * 11.5) * 0.5 + Math.sin(t * 6.4) * 0.16)
        : 0;
      const target = speaking ? (level >= 0 ? Math.min(1, level * 1.15) : procedural) : 0;
      mouthRef.current = damp(mouthRef.current, target, 22, step);
      manager.setValue("aa", mouthRef.current * 0.85);
      manager.setValue("ih", mouthRef.current * 0.22);
      manager.setValue("ou", mouthRef.current * 0.14);
    }

    // Gaze
    if (vrm.lookAt) {
      const targetX = gaze === "side" ? -0.7 : gaze === "down" ? 0 : pointer.x * 0.55;
      const targetY = gaze === "down" ? -0.75 : pointer.y * 0.35;
      lookTarget.position.x = damp(lookTarget.position.x, targetX, 5, step);
      lookTarget.position.y = damp(lookTarget.position.y, targetY, 5, step);
    }

    if (humanoid) {
      const setBone = (name: string, x: number, y: number, z: number, lambda = 6) => {
        const node = humanoid.getNormalizedBoneNode(name) as THREE.Object3D | null;
        if (!node) return;
        node.rotation.x = damp(node.rotation.x, x, lambda, step);
        node.rotation.y = damp(node.rotation.y, y, lambda, step);
        node.rotation.z = damp(node.rotation.z, z, lambda, step);
      };

      const breathe = Math.sin(t * 1.2) * 0.014;
      const lean = gesture === "lean_closer" ? 0.11 : gesture === "pout" ? -0.03 : 0;

      setBone("hips", breathe * 0.4, pointer.x * 0.05, 0, 4);
      setBone("spine", lean * 0.5 + breathe, 0, Math.sin(t * 0.6) * 0.01, 5);
      setBone("chest", lean * 0.4 + breathe * 0.8, pointer.x * 0.04, 0, 5);
      setBone(
        "neck",
        HEAD_TILT[emotion] * 0.4 + (gaze === "down" ? 0.1 : 0),
        gaze === "side" ? -0.16 : pointer.x * 0.07,
        emotion === "embarrassed" ? 0.03 : 0,
        6,
      );
      setBone(
        "head",
        HEAD_TILT[emotion] * 0.6 + (gaze === "down" ? 0.12 : pointer.y * 0.04),
        gaze === "side" ? -0.2 : pointer.x * 0.1,
        emotion === "embarrassed" ? 0.06 : emotion === "playful" ? -0.06 : emotion === "sad" ? 0.04 : 0,
        6,
      );

      const armPose = GESTURE_POSE[gesture] ?? REST_POSE;
      const sway = Math.sin(t * 1.05) * 0.02;
      const waving = gesture === "small_wave" ? Math.sin(t * 8) * 0.32 : 0;

      setBone("leftUpperArm", armPose.upperL[0], armPose.upperL[1], armPose.upperL[2] * power + sway, 7);
      setBone("leftLowerArm", armPose.lowerL[0], armPose.lowerL[1] * power, armPose.lowerL[2], 7);
      setBone("rightUpperArm", armPose.upperR[0], armPose.upperR[1], armPose.upperR[2] * power - sway, 7);
      setBone(
        "rightLowerArm",
        armPose.lowerR[0],
        armPose.lowerR[1] * power,
        armPose.lowerR[2] + waving,
        gesture === "small_wave" ? 18 : 7,
      );
      setBone("leftHand", 0, 0, 0.05, 6);
      setBone("rightHand", 0, 0, -0.05 + waving * 0.3, 8);

      // Keep the invisible touch targets glued to their bones.
      HITBOXES.forEach((hitbox, index) => {
        const mesh = hitRefs.current[index];
        const node = humanoid.getNormalizedBoneNode(hitbox.bone) as THREE.Object3D | null;
        if (!mesh || !node) return;
        node.getWorldPosition(bonePosition);
        mesh.position.set(
          bonePosition.x + hitbox.offset[0],
          bonePosition.y + hitbox.offset[1],
          bonePosition.z + hitbox.offset[2],
        );
      });
    }

    if (root.current) {
      root.current.position.y = Math.sin(t * 1.25) * 0.006;
    }

    vrm.update(step);
  });

  if (!vrm) return null;

  return (
    <group ref={root}>
      <primitive object={vrm.scene} />
      {HITBOXES.map((hitbox, index) => (
        <mesh
          key={`${hitbox.region}-${hitbox.bone}`}
          ref={(mesh: THREE.Mesh | null) => {
            hitRefs.current[index] = mesh;
          }}
          onPointerDown={(event) => {
            event.stopPropagation();
            onTouch(hitbox.region);
          }}
        >
          <sphereGeometry args={[hitbox.radius, 10, 8]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}
