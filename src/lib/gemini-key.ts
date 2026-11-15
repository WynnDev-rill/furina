const encoder = new TextEncoder();

function encode(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes));
}

function decode(value: string) {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0));
}

async function cipherKey(secret: string) {
  if (!secret) throw new Error("Penyimpanan API key belum siap.");
  const material = await crypto.subtle.digest(
    "SHA-256",
    encoder.encode("furina/gemini/key/v1:" + secret),
  );
  return crypto.subtle.importKey("raw", material, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function protectGeminiKey(value: string, owner: string, secret: string) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: encoder.encode(owner) },
    await cipherKey(secret),
    encoder.encode(value),
  );
  const fingerprint = await crypto.subtle.digest("SHA-256", encoder.encode(owner + ":" + value));
  return {
    box: encode(iv) + "." + encode(new Uint8Array(data)),
    fingerprint: encode(new Uint8Array(fingerprint)),
  };
}

export async function openGeminiKey(box: string, owner: string, secret: string) {
  const [iv, data] = box.split(".");
  const decoded = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: decode(iv), additionalData: encoder.encode(owner) },
    await cipherKey(secret),
    decode(data),
  );
  return new TextDecoder().decode(decoded);
}

export function isInvalidGeminiKey(status: number, reason: string) {
  return (
    status === 401 ||
    ((status === 400 || status === 403) &&
      /\b(API_KEY_INVALID|API_KEY_EXPIRED|API_KEY_REVOKED|API key not valid)\b/i.test(reason))
  );
}

export async function useGeminiKeys<T extends { status: number }>(
  keys: string[],
  request: (key: string) => Promise<T>,
  invalid: (response: T) => Promise<boolean>,
  revoke: (key: string) => Promise<void>,
) {
  for (const key of keys) {
    const response = await request(key);
    if (response.status === 429 || !(await invalid(response))) return response;
    await revoke(key);
  }
  return null;
}
