# Graph Report - furina  (2026-11-18)

## Corpus Check
- 129 files · ~54,932 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .toml 2, .css 1)

## Summary
- 834 nodes · 1734 edges · 61 communities (35 shown, 26 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c6248f15`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- furina.functions.ts
- FurinaApp
- MainActivity.java
- index.tsx
- server.ts
- devDependencies
- components.json
- compilerOptions
- Perbaikan Bug + Furina Lebih Hidup & Punya Pendirian
- package.json
- client.ts
- __root.tsx
- scripts
- Furina Companion
- clsx
- Furina Companion
- ref_node_assert
- react
- Routes
- DESIGN.md
- embla-carousel-react@^8.6.0
- dependencies
- memory-settings.tsx
- @lovable.dev/cloud-auth-js
- identity-core.ts
- nvidia-chat.server.ts
- @radix-ui/react-avatar@^1.1.11
- ai-settings-api.ts
- nvidia-catalog.ts
- gemini-chat.ts
- @radix-ui/react-dropdown-menu@^2.1.16
- ai-channel-settings.tsx
- model-fallback.ts
- NVIDIA NIM untuk percakapan utama
- Memori Furina
- nvidia-chat-routing.test.mjs
- response-feedback.ts
- example.functions.ts
- NVIDIA NIM Main Chat Implementation Plan
- Bintang penuntun
- identity-core.md
- @radix-ui/react-alert-dialog@^1.1.15
- ai-usage-stats.test.mjs
- cmdk@^1.1.1
- @radix-ui/react-checkbox@^1.3.3
- @radix-ui/react-switch@^1.2.6
- @radix-ui/react-label@^2.1.8
- ConversationHistory
- tailwindcss@^4.2.1
- nvidia-settings.browser.mjs
- @radix-ui/react-menubar@^1.1.16
- @radix-ui/react-popover@^1.1.15
- @radix-ui/react-slot@^1.2.4
- requireFurinaIdentity
- webview-android/README.md
- recharts@^2.15.4
- MemorySettings

## God Nodes (most connected - your core abstractions)
1. `FurinaApp()` - 53 edges
2. `requireFurinaIdentity()` - 44 edges
3. `chatWithFurina` - 37 edges
4. `fetchAllPages()` - 22 edges
5. `MainActivity` - 20 edges
6. `requestBackgroundAi()` - 18 edges
7. `compilerOptions` - 17 edges
8. `profileContext()` - 16 edges
9. `@tanstack/react-start` - 16 edges
10. `localCalendar()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `1. Chat terbaru kadang menghilang` --references--> `sendMessage()`  [INFERRED]
  .lovable/plan.md → src/routes/index.tsx
- `Verifikasi` --references--> `useGeminiKeys()`  [INFERRED]
  docs/audit-2026-11-17.md → src/lib/gemini-key.ts
- `fixture()` --indirect_call--> `routeNvidiaChat()`  [INFERRED]
  tests/nvidia-chat-server.test.mjs → src/lib/nvidia-chat-routing.ts
- `validator()` --indirect_call--> `routeNvidiaChat()`  [INFERRED]
  tests/nvidia-key-validation.test.mjs → src/lib/nvidia-chat-routing.ts
- `call()` --indirect_call--> `requestWithProviderFallback()`  [INFERRED]
  tests/main-chat-integration.test.mjs → src/lib/model-fallback.ts

## Import Cycles
- None detected.

## Communities (61 total, 26 thin omitted)

### Community 0 - "furina.functions.ts"
Cohesion: 0.05
Nodes (77): BirthDateSettings(), supabaseAdmin, requestBackgroundAi(), requestPersonalBackground(), ageInstructions(), birthdayContext(), birthdayInstructions(), localCalendar() (+69 more)

### Community 1 - "FurinaApp"
Cohesion: 0.07
Nodes (40): androidOAuthRedirect(), decode(), encode(), FurinaSession, isAndroidLoginPage(), openAndroidLogin(), readKey(), receiveAndroidSession() (+32 more)

### Community 2 - "MainActivity.java"
Cohesion: 0.09
Nodes (3): MainActivity, WebChromeClient, WebViewClient

### Community 3 - "index.tsx"
Cohesion: 0.06
Nodes (15): branchPrefix(), messageQuote, MessageQuote, ALL_FURINA_KEYS, Conversation, Msg, MsgStatus, Route (+7 more)

### Community 4 - "server.ts"
Cohesion: 0.21
Nodes (9): attachSupabaseAuth, consumeLastCapturedError(), renderErrorPage(), fetch(), getServerEntry(), normalizeCatastrophicSsrResponse(), ServerEntry, errorMiddleware (+1 more)

### Community 5 - "devDependencies"
Cohesion: 0.07
Nodes (31): devDependencies, eslint@^9.32.0, eslint-config-prettier@^10.1.1, @eslint/js@^9.32.0, eslint-plugin-prettier@^5.2.6, eslint-plugin-react-hooks@^5.2.0, eslint-plugin-react-refresh@^0.4.20, globals@^15.15.0 (+23 more)

### Community 6 - "components.json"
Cohesion: 0.11
Nodes (18): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+10 more)

### Community 7 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+10 more)

### Community 8 - "Perbaikan Bug + Furina Lebih Hidup & Punya Pendirian"
Cohesion: 0.12
Nodes (16): 1. Chat terbaru kadang menghilang, 2. Waktu riwayat sama semua, 3. Grouping riwayat, 4. Inner state ringan (di luar mood), 5. Kesadaran waktu & sesi, 6. Memori diri (self-notes), 7. Opini & bantah dalam karakter, 8. Inisiatif dalam obrolan (+8 more)

### Community 9 - "package.json"
Cohesion: 0.06
Nodes (30): class-variance-authority@^0.7.1, input-otp@^1.4.2, @radix-ui/react-hover-card@^1.1.15, @radix-ui/react-progress@^1.1.8, @radix-ui/react-radio-group@^1.3.8, @radix-ui/react-select@^2.2.6, @radix-ui/react-slider@^1.3.6, react-dom@^19.2.0 (+22 more)

### Community 10 - "client.ts"
Cohesion: 0.19
Nodes (7): @supabase/supabase-js@^2.106.2, @supabase/supabase-js, lovable, lovableAuth, SignInOptions, requireSupabaseAuth, supabase

### Community 11 - "__root.tsx"
Cohesion: 0.14
Nodes (5): @tanstack/react-query@^5.83.0, @tanstack/react-router@1.170.41, @tanstack/react-query, @tanstack/react-router, Route

### Community 12 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, build:dev, dev, format, lint, preview

### Community 13 - "Furina Companion"
Cohesion: 0.29
Nodes (6): Arsitektur, Batas proyek, Furina Companion, Identity Core, Skill coding, Workflow

### Community 14 - "clsx"
Cohesion: 0.33
Nodes (4): clsx@^2.1.1, tailwind-merge@^3.5.0, clsx, tailwind-merge

### Community 15 - "Furina Companion"
Cohesion: 0.40
Nodes (4): Cakupan, Furina Companion, Kebutuhan pengguna, Platform

### Community 16 - "ref_node_assert"
Cohesion: 0.14
Nodes (11): listener(), chatFixture(), backup, fixture(), messages, model, models, validator() (+3 more)

### Community 17 - "react"
Cohesion: 0.20
Nodes (6): lucide-react@^0.575.0, react@^19.2.0, lucide-react, react, MessageGesture(), UserMessageText()

### Community 21 - "dependencies"
Cohesion: 0.05
Nodes (39): dependencies, date-fns@^4.1.0, @hookform/resolvers@^5.2.2, @radix-ui/react-accordion@^1.2.12, @radix-ui/react-aspect-ratio@^1.1.8, @radix-ui/react-collapsible@^1.1.12, @radix-ui/react-context-menu@^2.2.16, @radix-ui/react-dialog@^1.1.15 (+31 more)

### Community 22 - "memory-settings.tsx"
Cohesion: 0.08
Nodes (12): day, Entry, time, controls, Memory, MemoryData, addMemory, clearAllMemories (+4 more)

### Community 24 - "identity-core.ts"
Cohesion: 0.11
Nodes (26): getIdentityCore, updateIdentityCore, applyReview(), candidate, category, emptyIdentity(), established, evidence (+18 more)

### Community 25 - "nvidia-chat.server.ts"
Cohesion: 0.28
Nodes (11): NvidiaChatModel, NvidiaRouteKey, NvidiaRoutingState, routeNvidiaChat(), accessCache, checkNvidiaChatEligibility(), discoverNvidiaChatModels(), freeCatalog (+3 more)

### Community 27 - "ai-settings-api.ts"
Cohesion: 0.08
Nodes (17): addNvidiaKey, addOpenRouterKey, controls, copy(), getAiChannelSettings(), getNvidiaChatKeySettings(), getNvidiaKeySettings, getOpenRouterKeySettings (+9 more)

### Community 28 - "nvidia-catalog.ts"
Cohesion: 0.21
Nodes (9): accessible, availableNvidiaChatModels(), catalogSchema, createNvidiaCatalogLoader(), label, quality(), resource, access (+1 more)

### Community 29 - "gemini-chat.ts"
Cohesion: 0.21
Nodes (11): ChatPart, GEMINI_BASE, GEMINI_MODELS, GeminiChatMessage, GeminiPart, GeminiReply, requestGeminiCompletion(), toGeminiContent() (+3 more)

### Community 31 - "ai-channel-settings.tsx"
Cohesion: 0.13
Nodes (5): AiChannelSettings(), channels, GeminiKeySettings(), save(), update()

### Community 32 - "model-fallback.ts"
Cohesion: 0.36
Nodes (7): CHAT_MODEL_FALLBACK_ORDER, ChatModel, ChatProvider, isChatProviderFallbackStatus(), requestWithChatModelFallback(), requestWithProviderFallback(), retryDelayMs()

### Community 33 - "NVIDIA NIM untuk percakapan utama"
Cohesion: 0.29
Nodes (6): Evaluasi dan urutan model, Gratis, katalog dan validasi key, NVIDIA NIM untuk percakapan utama, Penyimpanan dan migrasi, Rotasi dan transparansi, Verifikasi

### Community 34 - "Memori Furina"
Cohesion: 0.25
Nodes (7): Cara kerja, Evaluasi kualitas, Kelanjutan lintas chat, Memori Furina, Pengambilan konteks, Penggabungan otomatis, Referensi produk dan tampilan

### Community 35 - "nvidia-chat-routing.test.mjs"
Cohesion: 0.33
Nodes (3): a, b, keys

### Community 36 - "response-feedback.ts"
Cohesion: 0.33
Nodes (5): feedbackExamples(), feedbackExamplesSchema, feedbackPrompt(), Rating, Ratings

### Community 38 - "NVIDIA NIM Main Chat Implementation Plan"
Cohesion: 0.40
Nodes (4): NVIDIA NIM Main Chat Implementation Plan, Review focus, Tasks, Verification ledger

### Community 42 - "ai-usage-stats.test.mjs"
Cohesion: 0.70
Nodes (3): formatResetCountdown(), getUsageSharePercent(), nextJakartaMonthReset()

### Community 50 - "nvidia-settings.browser.mjs"
Cohesion: 0.17
Nodes (8): @tailwindcss/vite@^4.2.1, vite@^7.3.8, @vitejs/plugin-react@^5.0.4, @tailwindcss/vite, vite, @vitejs/plugin-react, api, root

### Community 54 - "requireFurinaIdentity"
Cohesion: 0.07
Nodes (63): Audit Furina app — 17 November 2026, Batas dan tindak lanjut, Status PR dan pemeriksaan hosting, Temuan dan perbaikan, Verifikasi, @tanstack/react-start, zod, Settings (+55 more)

## Knowledge Gaps
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `@tanstack/react-start` connect `requireFurinaIdentity` to `furina.functions.ts`, `index.tsx`, `server.ts`, `example.functions.ts`, `package.json`, `client.ts`, `dependencies`, `memory-settings.tsx`, `ai-channel-settings.tsx`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Should `furina.functions.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.05238796549547654 - nodes in this community are weakly interconnected._
- **Why does `zod` connect `requireFurinaIdentity` to `furina.functions.ts`, `index.tsx`, `response-feedback.ts`, `example.functions.ts`, `package.json`, `dependencies`, `identity-core.ts`, `nvidia-catalog.ts`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Should `FurinaApp` be split into smaller, more focused modules?**
  _Cohesion score 0.06676342525399129 - nodes in this community are weakly interconnected._
- **Why does `FurinaApp()` connect `FurinaApp` to `furina.functions.ts`, `index.tsx`, `response-feedback.ts`, `ConversationHistory`, `react`, `requireFurinaIdentity`, `MemorySettings`, `ai-channel-settings.tsx`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Should `MainActivity.java` be split into smaller, more focused modules?**
  _Cohesion score 0.09468599033816426 - nodes in this community are weakly interconnected._
- **Should `index.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.06417112299465241 - nodes in this community are weakly interconnected._