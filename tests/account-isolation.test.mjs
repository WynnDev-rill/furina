import assert from "node:assert/strict";
import test from "node:test";
import { sourceCallback } from "./source-function.mjs";

function listener(previous, cacheOwner = null) {
  let resets = 0;
  let user = previous ? { id: previous } : null;
  const accountRef = { current: previous };
  const handle = sourceCallback("../src/routes/index.tsx", "onAuthStateChange", {
    accountRef,
    resetAccountData: () => {
      resets++;
    },
    localStorage: { getItem: () => cacheOwner },
    STORAGE: { cacheOwner: "owner" },
    setAuthUser: (update) => {
      user = typeof update === "function" ? update(user) : update;
    },
    setAuthReady: () => {},
    fromBrowser: false,
  });
  return { handle, resets: () => resets, user: () => user, accountRef };
}

test("session expiry clears the previous account's local state", () => {
  const f = listener("account-a", "account-a");
  f.handle("SIGNED_OUT", null);
  assert.equal(f.resets(), 1);
  assert.equal(f.user(), null);
  assert.equal(f.accountRef.current, null);
});

test("an expired session at startup cannot expose cached account chats as guest data", () => {
  const f = listener(null, "account-a");
  f.handle("INITIAL_SESSION", null);
  assert.equal(f.resets(), 1);
});

test("switching accounts clears the old conversation and composer state", () => {
  const f = listener("account-a", "account-a");
  f.handle("SIGNED_IN", { user: { id: "account-b" } });
  assert.equal(f.resets(), 1);
  assert.equal(f.user().id, "account-b");
});

test("token refresh and guest startup retain their own data", () => {
  const signedIn = listener("account-a", "account-a");
  signedIn.handle("TOKEN_REFRESHED", { user: { id: "account-a" } });
  assert.equal(signedIn.resets(), 0);
  const guest = listener(null);
  guest.handle("INITIAL_SESSION", null);
  assert.equal(guest.resets(), 0);
});
