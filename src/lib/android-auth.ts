const callback = "furina_android_callback";
const pendingKey = "furina:androidAuthPending";
const browserKey = "furina:androidAuthBrowser";
const lifetime = 10 * 60 * 1000;

type FurinaSession = { access_token: string; refresh_token: string };

function encode(data: Uint8Array) {
  return btoa(String.fromCharCode(...data))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

function decode(value: string) {
  return Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/")), (char) =>
    char.charCodeAt(0),
  );
}

function readKey(storageKey: string): string | null {
  const saved = sessionStorage.getItem(storageKey);
  if (!saved) return null;
  const [key, timestamp] = saved.split(".");
  if (!Number.isFinite(Number(timestamp)) || Date.now() - Number(timestamp) > lifetime) {
    sessionStorage.removeItem(storageKey);
    return null;
  }
  return key;
}

export function openAndroidLogin() {
  const key = encode(crypto.getRandomValues(new Uint8Array(32)));
  const url = new URL("/", window.location.origin);
  url.searchParams.set(callback, "1");
  url.hash = `android-key=${key}`;
  sessionStorage.setItem(pendingKey, `${key}.${Date.now()}`);
  window.location.assign(url);
}

export function isAndroidLoginPage() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has(callback)) return false;
  const key = new URLSearchParams(url.hash.slice(1)).get("android-key");
  if (key && /^[A-Za-z0-9_-]{43}$/.test(key)) {
    sessionStorage.setItem(browserKey, `${key}.${Date.now()}`);
    url.hash = "";
    history.replaceState(history.state, "", url);
  }
  return true;
}

export function androidOAuthRedirect() {
  const url = new URL("/", window.location.origin);
  url.searchParams.set(callback, "1");
  return url.href;
}

export async function returnAndroidSession(session: FurinaSession) {
  const savedKey = readKey(browserKey);
  if (!savedKey) throw new Error("Sesi penghubung kedaluwarsa. Mulai ulang dari aplikasi Furina.");
  const key = await crypto.subtle.importKey("raw", decode(savedKey), "AES-GCM", false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const payload = new TextEncoder().encode(
    JSON.stringify({ access_token: session.access_token, refresh_token: session.refresh_token }),
  );
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, payload);
  sessionStorage.removeItem(browserKey);
  return `furina-webview://auth-return?payload=${encode(iv)}.${encode(new Uint8Array(encrypted))}`;
}

export async function receiveAndroidSession(fragment: string): Promise<FurinaSession> {
  const savedKey = readKey(pendingKey);
  const [iv, cipher] = fragment.split(".");
  if (!savedKey || !iv || !cipher) throw new Error("Sesi penghubung kedaluwarsa. Coba login lagi.");
  const key = await crypto.subtle.importKey("raw", decode(savedKey), "AES-GCM", false, ["decrypt"]);
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: decode(iv) },
    key,
    decode(cipher),
  );
  const session = JSON.parse(new TextDecoder().decode(decrypted)) as FurinaSession;
  if (!session.access_token || !session.refresh_token)
    throw new Error("Sesi Google tidak lengkap.");
  sessionStorage.removeItem(pendingKey);
  return session;
}
