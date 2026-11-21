// Browser boundary only: no network, accounts, or actual API keys.
const channels = { chat: false, background: false, issues: [] as string[] };
type KeySettings = {
  enabled: boolean;
  eligible: boolean;
  keys: { id: string; suffix: string; invalid: boolean }[];
};
const gemini: KeySettings = {
  enabled: true,
  eligible: true,
  keys: [{ id: "test-a", suffix: "abcd", invalid: false }],
};
const openrouter: KeySettings = { enabled: false, eligible: true, keys: [] };
const nvidia: KeySettings = { enabled: false, eligible: true, keys: [] };
const pending: (() => void)[] = [];
const controls = {
  holdNextChannel: false,
  get pending() {
    return pending.length;
  },
  release() {
    for (const resolve of pending.splice(0)) resolve();
  },
};
Object.assign(globalThis, { __furinaSettingsFixture: controls });
export const getAiChannelSettings = async () => {
  const value = structuredClone(channels);
  if (controls.holdNextChannel) {
    controls.holdNextChannel = false;
    await new Promise<void>((resolve) => pending.push(resolve));
  }
  return value;
};
export const setLovableChannel = async ({
  data,
}: {
  data: { channel: "chat" | "background"; enabled: boolean };
}) => {
  channels[data.channel] = data.enabled;
};
const functions = (settings: KeySettings) => ({
  get: async () => structuredClone(settings),
  add: async ({ data }: { data: { key: string } }) => {
    settings.keys.push({ id: "test-b", suffix: data.key.slice(-4), invalid: false });
  },
  remove: async ({ data }: { data: { id: string } }) => {
    settings.keys = settings.keys.filter((key) => key.id !== data.id);
  },
  set: async ({ data }: { data: { enabled: boolean } }) => {
    settings.enabled = data.enabled;
  },
});
const g = functions(gemini),
  o = functions(openrouter),
  n = functions(nvidia);
export const getGeminiKeySettings = g.get,
  addGeminiKey = g.add,
  removeGeminiKey = g.remove,
  setGeminiProvider = g.set;
export const getOpenRouterKeySettings = o.get,
  addOpenRouterKey = o.add,
  removeOpenRouterKey = o.remove,
  setOpenRouterProvider = o.set;
export const getNvidiaKeySettings = n.get,
  addNvidiaKey = n.add,
  removeNvidiaKey = n.remove,
  setNvidiaProvider = n.set;
