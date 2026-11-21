import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

const modulePath = process.env.FURINA_PLAYWRIGHT_MODULE;
if (!modulePath)
  throw new Error(
    "Set FURINA_PLAYWRIGHT_MODULE to an installed Playwright module; browser tests never use production accounts.",
  );
const { chromium } = await import(modulePath);
const root = resolve(import.meta.dirname, "..");
const temporary = await mkdtemp(join(tmpdir(), "furina-ai-ui-"));
const api = join(root, "tests/fixtures/ai-settings-api.ts");
await writeFile(
  join(temporary, "index.html"),
  `<html lang="id" class="dark"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/main.tsx"></script></body></html>`,
);
await writeFile(
  join(temporary, "main.tsx"),
  `import React from 'react'; import {createRoot} from 'react-dom/client';
import {AiChannelSettings} from '/@fs/${root}/src/components/ai-channel-settings.tsx';
import '/@fs/${root}/src/styles.css';
createRoot(document.getElementById('root')).render(<main className="settings-detail glass-surface" style={{width:'calc(100% - 24px)',maxWidth:520,margin:'12px auto'}}><h1>AI dan API Key</h1><AiChannelSettings userId="test-account" openAccount={()=>{}}/></main>);`,
);
const server = await createServer({
  root: temporary,
  configFile: false,
  plugins: [react(), tailwind()],
  resolve: {
    alias: [
      { find: "@/lib/ai-usage.functions", replacement: api },
      {
        find: "@tanstack/react-start",
        replacement: join(root, "tests/fixtures/server-fn-hook.ts"),
      },
      { find: "@", replacement: join(root, "src") },
      { find: /^react-dom(\/.*)?$/, replacement: join(root, "node_modules/react-dom") + "$1" },
      { find: /^react(\/.*)?$/, replacement: join(root, "node_modules/react") + "$1" },
    ],
  },
  server: { host: "127.0.0.1", port: 8082, strictPort: true, fs: { allow: [root, temporary] } },
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({
    executablePath: process.env.FURINA_CHROMIUM_PATH ?? "/usr/bin/chromium",
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 412, height: 915 } });
  await page.addInitScript(() => {
    const original = window.setInterval.bind(window);
    window.__furinaPollCallbacks = [];
    window.setInterval = (fn, ms, ...args) => {
      if (ms === 12000) window.__furinaPollCallbacks.push(fn);
      return original(fn, ms, ...args);
    };
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:8082");
  const input = page.locator("#furina-gemini-key");
  await input.waitFor();
  assert.equal(
    await page.getByRole("combobox", { name: "Percakapan utama", exact: true }).count(),
    0,
  );
  assert.equal(await page.getByText("NVIDIA NIM", { exact: true }).count(), 0);
  await input.fill("synthetic-gemini-key-1234");
  await page
    .getByRole("region", { name: "API key Gemini", exact: true })
    .getByRole("button", { name: "Simpan", exact: true })
    .click();
  await page.getByRole("button", { name: "Hapus API key berakhiran 1234" }).waitFor();
  assert.equal(await input.inputValue(), "");
  await page.getByRole("button", { name: "Hapus API key berakhiran 1234" }).click();
  await page
    .getByRole("button", { name: "Hapus API key berakhiran 1234" })
    .waitFor({ state: "detached" });
  const providerToggle = page.getByRole("switch", { name: "Gunakan API key Gemini", exact: true });
  await providerToggle.click();
  await page.getByText("API key Gemini nonaktif.", { exact: true }).waitFor();
  await providerToggle.click();
  await page.getByText("Gemini diprioritaskan.", { exact: true }).waitFor();
  const background = page.getByRole("combobox", { name: "Pekerjaan latar belakang", exact: true });
  await background.click();
  await page.getByRole("option", { name: "NVIDIA", exact: true }).click();
  await page.locator("#furina-nvidia-key").waitFor();
  assert.equal(await input.count(), 1);
  await background.click();
  await page.getByRole("option", { name: "OpenRouter", exact: true }).click();
  await page.locator("#furina-openrouter-key").waitFor();
  for (const theme of ["dark", "light"]) {
    await page.evaluate(
      (theme) => document.documentElement.classList.toggle("dark", theme === "dark"),
      theme,
    );
    for (const width of [320, 412, 1024]) {
      await page.setViewportSize({ width, height: 915 });
      assert.equal(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        false,
        `overflow ${theme}/${width}`,
      );
      const input = page.locator("#furina-gemini-key");
      await input.focus();
      await page.keyboard.type("nvapi-keyboard");
      assert.equal(await input.inputValue(), "nvapi-keyboard");
      await input.fill("");
      const style = await page
        .locator(".settings-group")
        .first()
        .evaluate((el) => ({
          border: getComputedStyle(el).borderRadius,
          background: getComputedStyle(el).backgroundColor,
        }));
      assert.equal(style.border, "14px");
      assert.notEqual(style.background, "rgba(0, 0, 0, 0)");
      await page.screenshot({ path: join(temporary, `${theme}-${width}.png`), fullPage: true });
    }
  }
  await page.evaluate(() => {
    window.__furinaSettingsFixture.holdNextChannel = true;
    window.__furinaPollCallbacks[0]();
  });
  await page.waitForFunction(() => window.__furinaSettingsFixture.pending > 0);
  const channelToggle = page.locator("#lovable-chat");
  await channelToggle.click();
  await page.waitForFunction(
    () => document.querySelector("#lovable-chat")?.getAttribute("aria-checked") === "true",
  );
  await page.evaluate(() => window.__furinaSettingsFixture.release());
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  assert.equal(
    await channelToggle.getAttribute("aria-checked"),
    "true",
    "stale polling cannot undo a saved toggle",
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  await input.focus();
  await input.evaluate((el) => {
    el.dispatchEvent(new CompositionEvent("compositionstart", { data: "" }));
    el.dispatchEvent(new CompositionEvent("compositionend", { data: "フリーナ" }));
  });
  await input.fill("フリーナ");
  assert.equal(await input.inputValue(), "フリーナ");
  await input.fill("");
  await page.keyboard.press("Tab");
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      passed: true,
      widths: [320, 412, 1024],
      themes: ["dark", "light"],
      checks: [
        "retired main provider absent",
        "key add/clear",
        "Gemini activation",
        "key delete",
        "independent background",
        "keyboard",
        "no overflow",
        "glass tokens",
        "poll race",
        "reduced motion and composition",
      ],
      screenshots: temporary,
    }),
  );
} finally {
  await browser?.close();
  await server.close();
}
