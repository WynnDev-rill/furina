(() => {
  "use strict";

  const STYLE_ID = "furina-voicevox-style";
  const BOUND = "furinaVoicevoxBound";
  const API_URL = "https://api.tts.quest/v3/voicevox/synthesis";
  const DEFAULT_SPEAKER = 8; // VOICEVOX:春日部つむぎ（ノーマル）
  const SPEAKER_KEY = "furina:voicevox:speaker";
  let currentAudio = null;
  let requestController = null;
  let activeButton = null;

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .furina-voicevox-button{display:inline-grid;place-items:center;flex:0 0 auto;min-width:38px;height:38px;padding:0 11px;border:1px solid rgba(255,255,255,.12);border-radius:999px;background:rgba(8,24,42,.44);color:#eef8ff;font:650 11px/1 system-ui;letter-spacing:.02em;cursor:pointer;-webkit-tap-highlight-color:transparent;backdrop-filter:blur(14px);transition:transform .18s cubic-bezier(.2,.8,.2,1),background .18s ease,opacity .18s ease,box-shadow .18s ease}
      .furina-voicevox-button:hover{background:rgba(73,169,235,.18);box-shadow:0 8px 25px rgba(28,119,190,.16)}
      .furina-voicevox-button:active{transform:scale(.92)}
      .furina-voicevox-button[data-playing='1']{background:rgba(62,169,232,.25);box-shadow:0 0 0 4px rgba(86,190,245,.09)}
      .furina-voicevox-button[disabled]{opacity:.45;cursor:wait}
      .furina-voicevox-inline{height:27px;min-width:0;padding:0 9px;color:rgba(220,240,252,.78);font-size:9px}
      .furina-voicevox-inline svg{width:11px;height:11px;margin-right:4px}
      .furina-voicevox-global{width:38px;padding:0;font-size:0}
      .furina-voicevox-global svg{width:16px;height:16px}
    `;
    document.head.appendChild(style);
  }

  function icon(playing = false) {
    return playing
      ? '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.6v12.8a1 1 0 0 0 1.53.85l9.5-6.4a1 1 0 0 0 0-1.7l-9.5-6.4A1 1 0 0 0 8 5.6Z"/></svg>';
  }

  function cleanText(value) {
    return String(value || "")
      .replace(/<think>[\s\S]*?<\/think>/gi, "")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[`*_>#|]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 280);
  }

  function notify(message) {
    try {
      const toast = document.createElement("div");
      toast.textContent = message;
      Object.assign(toast.style, {
        position: "fixed", left: "50%", bottom: "24px", zIndex: "99999",
        transform: "translate(-50%,12px)", opacity: "0", maxWidth: "calc(100% - 32px)",
        padding: "10px 14px", borderRadius: "14px", color: "#eef8ff",
        background: "rgba(6,22,39,.94)", border: "1px solid rgba(180,225,255,.16)",
        backdropFilter: "blur(16px)", font: "500 12px/1.4 system-ui", transition: ".2s ease",
      });
      document.body.appendChild(toast);
      requestAnimationFrame(() => { toast.style.opacity = "1"; toast.style.transform = "translate(-50%,0)"; });
      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translate(-50%,10px)";
        setTimeout(() => toast.remove(), 220);
      }, 2600);
    } catch {}
  }

  function speakerId() {
    const value = Number(localStorage.getItem(SPEAKER_KEY));
    return Number.isInteger(value) && value >= 0 ? value : DEFAULT_SPEAKER;
  }

  function setButtonState(button, state) {
    if (!button) return;
    button.disabled = state === "loading";
    button.dataset.playing = state === "playing" ? "1" : "0";
    const inline = button.classList.contains("furina-voicevox-inline");
    button.innerHTML = `${icon(state === "playing")}${inline ? (state === "loading" ? "Memuat…" : "VOICEVOX") : ""}`;
  }

  function stopVoice() {
    requestController?.abort();
    requestController = null;
    if (currentAudio) {
      try { currentAudio.pause(); currentAudio.currentTime = 0; } catch {}
      currentAudio = null;
    }
    if (activeButton) setButtonState(activeButton, "idle");
    activeButton = null;
  }

  async function speak(text, button) {
    const safe = cleanText(text);
    if (!safe || safe === "…") return;
    if (activeButton === button && currentAudio && !currentAudio.paused) {
      stopVoice();
      return;
    }
    if (!navigator.onLine) {
      notify("VOICEVOX memerlukan internet pada versi ini.");
      return;
    }

    stopVoice();
    activeButton = button;
    setButtonState(button, "loading");
    requestController = new AbortController();
    const timeout = setTimeout(() => requestController?.abort(), 30_000);

    try {
      const body = new URLSearchParams({ speaker: String(speakerId()), text: safe });
      const response = await fetch(API_URL, {
        method: "POST",
        signal: requestController.signal,
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.success || !result.mp3StreamingUrl) {
        const wait = Number(result.retryAfter || 0);
        throw new Error(wait > 0 ? `VOICEVOX sibuk. Coba lagi dalam ${wait} detik.` : (result.errorMessage || "VOICEVOX gagal membuat suara."));
      }

      currentAudio = new Audio(result.mp3StreamingUrl);
      currentAudio.preload = "auto";
      currentAudio.onplaying = () => setButtonState(button, "playing");
      currentAudio.onended = stopVoice;
      currentAudio.onerror = () => {
        notify("Audio VOICEVOX gagal diputar.");
        stopVoice();
      };
      await currentAudio.play();
    } catch (error) {
      if (error?.name !== "AbortError") notify(error instanceof Error ? error.message : "VOICEVOX gagal diputar.");
      else notify("VOICEVOX terlalu lama merespons.");
      stopVoice();
    } finally {
      clearTimeout(timeout);
      requestController = null;
    }
  }

  function latestAssistantText() {
    const hosted = [...document.querySelectorAll("main div.flex.flex-col.items-start p.whitespace-pre-wrap")]
      .map((node) => cleanText(node.textContent))
      .filter(Boolean);
    if (hosted.length) return hosted[hosted.length - 1];
    const local = [...document.querySelectorAll(".message.assistant")]
      .map((node) => cleanText(node.childNodes[0]?.textContent || node.textContent))
      .filter(Boolean);
    return local[local.length - 1] || "";
  }

  function createButton(inline, getText) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `furina-voicevox-button ${inline ? "furina-voicevox-inline" : "furina-voicevox-global"}`;
    button.setAttribute("aria-label", inline ? "Putar balasan dengan VOICEVOX" : "Putar balasan terakhir dengan VOICEVOX");
    button.title = "VOICEVOX · 春日部つむぎ";
    setButtonState(button, "idle");
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      void speak(getText(), button);
    });
    return button;
  }

  function enhanceHostedMessages() {
    document.querySelectorAll("main div.flex.flex-col.items-start").forEach((group) => {
      if (group.dataset[BOUND] === "1") return;
      const paragraph = group.querySelector("p.whitespace-pre-wrap");
      if (!paragraph || !cleanText(paragraph.textContent)) return;
      const meta = [...group.children].find((child) => child.classList?.contains("mt-1"));
      if (!meta) return;
      meta.appendChild(createButton(true, () => paragraph.textContent || ""));
      group.dataset[BOUND] = "1";
    });
  }

  function enhanceLocalMessages() {
    document.querySelectorAll(".message.assistant").forEach((message) => {
      if (message.dataset[BOUND] === "1") return;
      const meta = message.querySelector(".message-meta") || message;
      meta.appendChild(createButton(true, () => {
        const clone = message.cloneNode(true);
        clone.querySelectorAll(".message-meta,.furina-voicevox-button").forEach((node) => node.remove());
        return clone.textContent || "";
      }));
      message.dataset[BOUND] = "1";
    });
  }

  function enhanceHeader() {
    if (document.querySelector("[data-furina-voicevox-global='1']")) return;
    const host = document.querySelector("header .flex.items-center.gap-1") || document.querySelector(".top-actions");
    if (!host) return;
    const button = createButton(false, latestAssistantText);
    button.dataset.furinaVoicevoxGlobal = "1";
    host.prepend(button);
  }

  function enhance() {
    installStyles();
    enhanceHeader();
    enhanceHostedMessages();
    enhanceLocalMessages();
  }

  const observer = new MutationObserver(enhance);
  function boot() {
    enhance();
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("beforeunload", stopVoice);
    window.addEventListener("pagehide", stopVoice);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
