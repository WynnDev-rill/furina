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
  | "pout";

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
  gaze: "user" | "side" | "down";
};

export type TouchRegion = "head" | "face" | "shoulder" | "hand" | "body";
