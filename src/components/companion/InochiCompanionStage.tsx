import { useEffect, useRef, useState } from "react";

import type {
  CompanionEmotion,
  CompanionGaze,
  CompanionGesture,
  TouchRegion,
} from "@/lib/companion/types";
import { getVoiceLevel } from "@/lib/companion/voice";

type InochiCompanionStageProps = {
  emotion: CompanionEmotion;
  gesture: CompanionGesture;
  gaze: CompanionGaze;
  intensity: number;
  speaking: boolean;
  onTouch: (region: TouchRegion) => void;
};

type InochiController = {
  mount: (canvas: HTMLCanvasElement) => Promise<void> | void;
  unmount: () => Promise<void> | void;
  loadModel: (modelUrl: string, motionUrl?: string) => Promise<void>;
  resize: (width: number, height: number, devicePixelRatio: number) => Promise<void> | void;
  setCameraTransform: (x: number, y: number, scale: number) => Promise<void> | void;
  setExpressionPreset?: (
    name: string,
    options?: { weight?: number; allowMouth?: boolean },
  ) => Promise<void> | void;
  clearExpressionLayer?: (name?: string) => Promise<void> | void;
  setLipSyncValue?: (
    value: number,
    options?: {
      viseme?: "neutral" | "a" | "i" | "u" | "e" | "o";
      immediate?: boolean;
    },
  ) => Promise<void> | void;
  playEmotionAnimation?: (emotionName: string) => Promise<void> | void;
  playReactionAnimation?: (reactionName: string) => Promise<void> | void;
  getAnimationNames?: () => Promise<string[]> | string[];
  playIdleAnimations?: (
    animationNames: string[],
    options?: { shuffle?: boolean },
  ) => Promise<void> | void;
  applyInteractionImpulse?: (deltaX: number, deltaY: number) => Promise<void> | void;
};

type InochiBridgeModule = {
  createInochi2DController: (args: {
    wasmUrl: string;
    debug?: boolean;
  }) => Promise<InochiController> | InochiController;
};

const AITUBER_COMMIT = "08fb7cbae4346aac115bb2e3d04b41d2b0f827db";
const AITUBER_BASE = `https://cdn.jsdelivr.net/gh/shinshin86/aituber-onair@${AITUBER_COMMIT}/packages/core/examples/react-inochi2d-app/public/inochi2d`;
const BRIDGE_URL = `${AITUBER_BASE}/runtime/inochi_bridge.js`;
const WASM_URL = `${AITUBER_BASE}/runtime/inochi2d_bg.wasm`;
const MODEL_URL = `${AITUBER_BASE}/models/Aka.original-rig.inx`;
const MOTION_URL = `${AITUBER_BASE}/models/Aka.original.motion.json`;

const EXPRESSION_BY_EMOTION: Record<CompanionEmotion, string> = {
  neutral: "relaxed",
  happy: "happy",
  embarrassed: "relaxed",
  annoyed: "angry",
  worried: "sad",
  sad: "sad",
  surprised: "surprised",
  playful: "happy",
};

const REACTION_BY_GESTURE: Partial<Record<CompanionGesture, string>> = {
  small_wave: "flick",
  thinking: "tap",
  pout: "tap",
  crossed_arms: "flickDown",
  hand_to_chest: "tap",
  shy_hair_touch: "flickUp",
  lean_closer: "tap",
};

function resolveTouchRegion(x: number, y: number): TouchRegion {
  if (y < 0.24) return "head";
  if (y < 0.43) return "face";
  if (y < 0.62) return "shoulder";
  if ((x < 0.27 || x > 0.73) && y > 0.5) return "hand";
  return "body";
}

export function InochiCompanionStage({
  emotion,
  gesture,
  gaze,
  intensity,
  speaking,
  onTouch,
}: InochiCompanionStageProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const controllerRef = useRef<InochiController | null>(null);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof window === "undefined") return;

    const probe = document.createElement("canvas");
    const supported = Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
    if (!supported) {
      setStatus("error");
      setError("WebGL tidak tersedia pada perangkat ini.");
      return;
    }

    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;
    let controller: InochiController | null = null;

    const resize = async () => {
      if (!controller || disposed) return;
      const parent = canvas.parentElement;
      const width = Math.max(1, parent?.clientWidth || canvas.clientWidth || 1);
      const height = Math.max(1, parent?.clientHeight || canvas.clientHeight || 1);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
      await Promise.resolve(controller.resize(width, height, dpr));
    };

    void (async () => {
      try {
        const bridge = (await import(
          /* @vite-ignore */ BRIDGE_URL
        )) as Partial<InochiBridgeModule>;
        if (typeof bridge.createInochi2DController !== "function") {
          throw new Error("runtime bridge Inochi2D tidak valid");
        }

        controller = await bridge.createInochi2DController({
          wasmUrl: WASM_URL,
          debug: false,
        });
        if (disposed) {
          await Promise.resolve(controller.unmount());
          return;
        }

        controllerRef.current = controller;
        await Promise.resolve(controller.mount(canvas));
        await controller.loadModel(MODEL_URL, MOTION_URL);
        await Promise.resolve(controller.setCameraTransform(0, 1450, 0.32));
        await resize();

        try {
          const animationNames = await Promise.resolve(controller.getAnimationNames?.() ?? []);
          if (animationNames.length && controller.playIdleAnimations) {
            await Promise.resolve(
              controller.playIdleAnimations(animationNames.slice(0, 4), { shuffle: true }),
            );
          }
        } catch {
          // The model still works without optional motion groups.
        }

        if (typeof ResizeObserver !== "undefined") {
          resizeObserver = new ResizeObserver(() => {
            void resize();
          });
          resizeObserver.observe(canvas.parentElement ?? canvas);
        }

        if (!disposed) {
          setStatus("ready");
          setError("");
        }
      } catch (reason) {
        console.error("Inochi2D initialization failed", reason);
        if (!disposed) {
          setStatus("error");
          setError("Inochi2D gagal dimuat. Mode VRM tetap bisa digunakan.");
        }
      }
    })();

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      controllerRef.current = null;
      if (controller) void Promise.resolve(controller.unmount());
    };
  }, []);

  useEffect(() => {
    const controller = controllerRef.current;
    if (!controller || status !== "ready") return;

    const preset = EXPRESSION_BY_EMOTION[emotion];
    void Promise.resolve(
      controller.setExpressionPreset?.(preset, {
        weight: Math.min(1, 0.55 + intensity * 0.45),
        allowMouth: true,
      }),
    ).catch(() => undefined);
    void Promise.resolve(controller.playEmotionAnimation?.(preset)).catch(() => undefined);

    const reaction = REACTION_BY_GESTURE[gesture];
    if (reaction) {
      void Promise.resolve(controller.playReactionAnimation?.(reaction)).catch(() => undefined);
    }
  }, [emotion, gesture, intensity, status]);

  useEffect(() => {
    if (status !== "ready") return;
    let frame = 0;
    let stopped = false;

    const tick = () => {
      if (stopped) return;
      const controller = controllerRef.current;
      if (controller?.setLipSyncValue) {
        const measured = speaking ? getVoiceLevel() : 0;
        const procedural = speaking
          ? 0.18 + Math.abs(Math.sin(performance.now() * 0.013)) * 0.46
          : 0;
        const mouth = speaking ? Math.min(1, measured > 0.01 ? measured * 1.18 : procedural) : 0;
        void Promise.resolve(
          controller.setLipSyncValue(mouth, {
            viseme: mouth > 0.55 ? "a" : mouth > 0.25 ? "e" : "neutral",
            immediate: true,
          }),
        ).catch(() => undefined);
      }
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      void Promise.resolve(
        controllerRef.current?.setLipSyncValue?.(0, { viseme: "neutral", immediate: true }),
      ).catch(() => undefined);
    };
  }, [speaking, status]);

  useEffect(() => {
    if (status !== "ready" || gaze === "user") return;
    const controller = controllerRef.current;
    if (!controller) return;
    void Promise.resolve(
      controller.applyInteractionImpulse?.(gaze === "side" ? -12 : 0, gaze === "down" ? 9 : 0),
    ).catch(() => undefined);
  }, [gaze, status]);

  return (
    <div className="relative h-full min-h-[460px] overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_50%_30%,rgba(255,196,220,0.16),transparent_33%),linear-gradient(180deg,#211329_0%,#120d1c_55%,#0c0a13_100%)] shadow-2xl">
      <canvas
        ref={canvasRef}
        className="h-full min-h-[460px] w-full touch-none"
        aria-label="Inochi2D character stage"
        onPointerDown={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          pointerRef.current = { x: event.clientX, y: event.clientY };
          const x = (event.clientX - rect.left) / Math.max(1, rect.width);
          const y = (event.clientY - rect.top) / Math.max(1, rect.height);
          onTouch(resolveTouchRegion(x, y));
        }}
        onPointerMove={(event) => {
          const previous = pointerRef.current;
          if (!previous) return;
          const dx = event.clientX - previous.x;
          const dy = event.clientY - previous.y;
          pointerRef.current = { x: event.clientX, y: event.clientY };
          void Promise.resolve(controllerRef.current?.applyInteractionImpulse?.(dx * 0.45, dy * 0.3)).catch(
            () => undefined,
          );
        }}
        onPointerUp={() => {
          pointerRef.current = null;
        }}
        onPointerCancel={() => {
          pointerRef.current = null;
        }}
      />

      <div className="pointer-events-none absolute inset-x-0 top-3 flex justify-center px-3">
        <div className="rounded-full border border-pink-100/10 bg-black/35 px-3 py-1.5 text-[9px] uppercase tracking-[0.14em] text-pink-100/60 backdrop-blur-xl">
          Inochi2D · experimental 2.5D rig
        </div>
      </div>

      {status !== "ready" && (
        <div className="absolute inset-0 grid place-items-center bg-[#0d0914]/65 p-6 text-center backdrop-blur-sm">
          <div className="max-w-xs rounded-2xl border border-white/10 bg-black/35 px-5 py-4 shadow-xl">
            <div className="text-sm font-medium text-pink-100">
              {status === "loading" ? "Memuat Inochi2D…" : "Inochi2D tidak tersedia"}
            </div>
            {error && <p className="mt-2 text-xs leading-relaxed text-white/55">{error}</p>}
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 rounded-xl border border-white/8 bg-black/35 px-2.5 py-1.5 text-[9px] leading-relaxed text-white/42 backdrop-blur-xl">
        Base rig: Aka · CC BY 4.0 · target visual mengikuti palet Mirei
      </div>
    </div>
  );
}
