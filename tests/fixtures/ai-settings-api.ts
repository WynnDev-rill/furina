// Browser-test boundary only: no network, real accounts or actual API keys.
const state = {
  mainProvider: "gemini",
  chat: false,
  background: false,
  issues: [] as string[],
  nvidia: {
    enabled: true,
    eligible: true,
    model: "minimaxai/minimax-m3.1-flash",
    notice: null,
    keys: [{ id: "test-a", suffix: "abcd", invalid: false, enabled: true }],
  },
};
const copy = <T>(value: T): T => structuredClone(value);
const pendingChannels: (() => void)[] = [];
const pendingKeys: (() => void)[] = [];
const controls = {
  holdNextChannel: false,
  holdNextKeys: false,
  get pending() {
    return pendingChannels.length + pendingKeys.length;
  },
  release() {
    for (const resolve of [...pendingChannels.splice(0), ...pendingKeys.splice(0)]) resolve();
  },
};
Object.assign(globalThis, { __furinaSettingsFixture: controls });
export const getAiChannelSettings = async () => {
  const value = copy(state);
  if (controls.holdNextChannel) {
    controls.holdNextChannel = false;
    await new Promise<void>((resolve) => pendingChannels.push(resolve));
  }
  return value;
};
export const setLovableChannel = async ({
  data,
}: {
  data: { channel: "chat" | "background"; enabled: boolean };
}) => {
  state[data.channel] = data.enabled;
};
export const setChatProviderSelection = async ({ data }: { data: { provider: string } }) => {
  state.mainProvider = data.provider;
};
export const getNvidiaChatKeySettings = async () => {
  const value = copy(state.nvidia);
  if (controls.holdNextKeys) {
    controls.holdNextKeys = false;
    await new Promise<void>((resolve) => pendingKeys.push(resolve));
  }
  return value;
};
export const setNvidiaChatProvider = async ({ data }: { data: { enabled: boolean } }) => {
  state.nvidia.enabled = data.enabled;
};
export const addNvidiaChatKey = async ({ data }: { data: { key: string } }) => {
  state.nvidia.keys.push({
    id: "test-b",
    suffix: data.key.slice(-4),
    invalid: false,
    enabled: true,
  });
};
export const removeNvidiaChatKey = async ({ data }: { data: { id: string } }) => {
  state.nvidia.keys = state.nvidia.keys.filter((key) => key.id !== data.id);
};
export const setNvidiaChatKeyEnabled = async ({
  data,
}: {
  data: { id: string; enabled: boolean };
}) => {
  const key = state.nvidia.keys.find((key) => key.id === data.id);
  if (key) key.enabled = data.enabled;
};
export const getGeminiKeySettings = async () => ({ enabled: false, eligible: true, keys: [] });
export const getOpenRouterKeySettings = getGeminiKeySettings;
export const getNvidiaKeySettings = getGeminiKeySettings;
export const addGeminiKey = async () => {};
export const removeGeminiKey = addGeminiKey;
export const setGeminiProvider = addGeminiKey;
export const addOpenRouterKey = addGeminiKey;
export const removeOpenRouterKey = addGeminiKey;
export const setOpenRouterProvider = addGeminiKey;
export const addNvidiaKey = addGeminiKey;
export const removeNvidiaKey = addGeminiKey;
export const setNvidiaProvider = addGeminiKey;
