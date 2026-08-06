export type CompanionEmotion =
  | "neutral"
  | "happy"
  | "embarrassed"
  | "annoyed"
  | "worried"
  | "sad"
  | "surprised"
  | "playful";

export type CompanionGesture =
  | "idle"
  | "soft_smile"
  | "look_away"
  | "hands_on_hips"
  | "lean_closer"
  | "small_wave"
  | "thinking"
  | "pout"
  | "crossed_arms"
  | "hand_to_chest"
  | "shy_hair_touch";

export type CompanionGaze = "user" | "side" | "down";
export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
};

export type CompanionReply = {
  speech: string;
  emotion: CompanionEmotion;
  intensity: number;
  gesture: CompanionGesture;
  gaze: CompanionGaze;
  memory?: string;
};

export type TouchRegion = "head" | "face" | "shoulder" | "hand" | "body";

export type RelationshipState = {
  affinity: number;
  trust: number;
  annoyance: number;
  interactionCount: number;
  touchCount: number;
};

export type CompanionContext = {
  memories: string[];
  relationship: RelationshipState;
  localTime: string;
};

export type ProviderProgress = {
  phase: "queued" | "generating" | "fallback";
  waitSeconds?: number;
};
