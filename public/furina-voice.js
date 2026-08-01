(() => {
  const STYLE_ID = "furina-japanese-voice-style";
  const BOUND = "furinaVoiceBound";
  let browserUtterance = null;

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .furina-voice-button{display:inline-grid;place-items:center;flex:0 0 auto;width:38px;height:38px;border:1px solid rgba(255,255,255,.11);border-radius:999px;background:rgba(255,255,255,.055);color:#fff;font:600 15px/1 system-ui;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:transform .15s ease,background .15s ease}
      .furina-voice-button:active{transform:scale(.93)}
      .furina-voice-button:hover{background:rgba(74,169,236,.18)}
      .furina-voice-inline{width:auto;height:28px;padding:0 10px;gap:5px;border-radius:999px;color:rgba(220,239,252,.78);font-size:10px}
      .furina-voice-inline span{font-size:11px}
      .furina-voice-button[disabled]{opacity:.38;cursor:not-allowed}
    `;
    document.head.appendChild(style);
  }

  function cleanText(value) {
    return String(value || "")
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[`*_>#|]/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 4000);
  }

  function stopSpeech() {
    try { window.FurinaVoice?.stop?.(); } catch {}
    try { window.speechSynthesis?.cancel?.(); } catch {}
    browserUtterance = null;
  }

  function browserSpeak(text) {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const japanese = voices.find((voice) => /^ja(?:-|_)/i.test(voice.lang)) ||
      voices.find((voice) => /japan|日本|kyoko|otoya/i.test(voice.name));
    if (japanese) utterance.voice = japanese;
    utterance.lang = "ja-JP";
    utterance.rate = 1;
    utterance.pitch = 1.08;
    browserUtterance = utterance;
    utterance.onend = () => { browserUtterance = null; };
    utterance.onerror = () => { browserUtterance = null; };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function speak(text) {
    const safe = cleanText(text);
    if (!safe || safe === "…") return false;
    stopSpeech();
    try {
      if (window.FurinaVoice?.speak?.(safe)) return true;
    } catch {}
    return browserSpeak(safe);
  }

  function latestAssistantText() {
    const hosted = [...document.querySelectorAll("main p.whitespace-pre-wrap")]
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
    button.className = `furina-voice-button${inline ? " furina-voice-inline" : ""}`;
    button.setAttribute("aria-label", inline ? "Putar pesan dengan suara Jepang" : "Putar balasan terakhir dengan suara Jepang");
    button.title = inline ? "Putar dengan suara Jepang" : "Suara Jepang";
    button.innerHTML = inline ? "<span>▶</span> 日本語" : "▶";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (!speak(getText())) button.disabled = true;
    });
    return button;
  }

  function enhanceHostedMessages() {
    const chatMain = [...document.querySelectorAll("main")].find((main) =>
      main.classList.contains("absolute") && main.querySelector("p.whitespace-pre-wrap")
    );
    if (!chatMain) return;
    chatMain.querySelectorAll("div.flex.flex-col.items-start").forEach((group) => {
      if (group.dataset[BOUND] === "1") return;
      const paragraph = group.querySelector("p.whitespace-pre-wrap");
      if (!paragraph || !cleanText(paragraph.textContent)) return;
      const meta = [...group.children].find((child) => child.classList?.contains("mt-1"));
      const host = meta || group;
      host.appendChild(createButton(true, () => paragraph.textContent || ""));
      group.dataset[BOUND] = "1";
    });
  }

  function enhanceLocalMessages() {
    document.querySelectorAll(".message.assistant").forEach((message) => {
      if (message.dataset[BOUND] === "1") return;
      const meta = message.querySelector(".message-meta") || message;
      meta.appendChild(createButton(true, () => {
        const clone = message.cloneNode(true);
        clone.querySelectorAll(".message-meta,.furina-voice-button").forEach((node) => node.remove());
        return clone.textContent || "";
      }));
      message.dataset[BOUND] = "1";
    });
  }

  function enhanceHeader() {
    if (document.querySelector("[data-furina-global-voice='1']")) return;
    const hostedActions = document.querySelector("header .flex.items-center.gap-1");
    const localActions = document.querySelector(".top-actions");
    const host = hostedActions || localActions;
    if (!host) return;
    const button = createButton(false, latestAssistantText);
    button.dataset.furinaGlobalVoice = "1";
    host.prepend(button);
  }

  function enhanceFallbackLogin() {
    const button = document.getElementById("settings-online");
    if (!button || button.dataset.googleRestored === "1") return;
    button.textContent = "Masuk dengan Google";
    button.dataset.googleRestored = "1";
  }

  function enhance() {
    installStyles();
    enhanceHeader();
    enhanceHostedMessages();
    enhanceLocalMessages();
    enhanceFallbackLogin();
  }

  const observer = new MutationObserver(enhance);
  function boot() {
    enhance();
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("beforeunload", stopSpeech);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
