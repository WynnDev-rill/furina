# Graph Report - furina  (2026-11-21)

## Corpus Check
- 122 files · ~49,786 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .toml 2, .css 1)

## Summary
- 796 nodes · 1585 edges · 67 communities (37 shown, 30 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 17 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9d774f9b`
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
- dependencies
- ref_node_assert
- __root.tsx
- scripts
- Furina Companion
- clsx
- Furina Companion
- source-function.mjs
- react
- Routes
- DESIGN.md
- embla-carousel-react@^8.6.0
- package.json
- MemorySettings
- chat-continuity.ts
- identity-core.ts
- localCalendar
- model-fallback.ts
- ai-settings-api.ts
- chatWithFurina
- Audit AI dan API key Furina — 21 November 2026
- memory-policy.ts
- ai-channel-settings.tsx
- @hookform/resolvers@^5.2.2
- NVIDIA NIM untuk percakapan utama
- Memori Furina
- input-otp@^1.4.2
- response-feedback.ts
- @radix-ui/react-accordion@^1.2.12
- NVIDIA NIM Main Chat Implementation Plan
- Bintang penuntun
- identity-core.md
- @radix-ui/react-alert-dialog@^1.1.15
- @radix-ui/react-navigation-menu@^1.2.14
- Audit Furina app — 17 November 2026
- @radix-ui/react-checkbox@^1.3.3
- @radix-ui/react-radio-group@^1.3.8
- ai-usage-stats.test.mjs
- memory-settings.tsx
- @radix-ui/react-tabs@^1.1.13
- nvidia-settings.browser.mjs
- @radix-ui/react-toggle@^1.1.10
- class-variance-authority@^0.7.1
- react-day-picker@^9.14.0
- requireFurinaIdentity
- webview-android/README.md
- date-fns@^4.1.0
- @radix-ui/react-avatar@^1.1.11
- @radix-ui/react-dialog@^1.1.15
- @radix-ui/react-scroll-area@^1.2.10
- @radix-ui/react-toggle-group@^1.1.11
- react-dom@^19.2.0
- recharts@^2.15.4
- @tanstack/router-plugin@1.168.42

## God Nodes (most connected - your core abstractions)
1. `FurinaApp()` - 53 edges
2. `requireFurinaIdentity()` - 37 edges
3. `chatWithFurina` - 36 edges
4. `MainActivity` - 20 edges
5. `requestBackgroundAi()` - 18 edges
6. `compilerOptions` - 17 edges
7. `@tanstack/react-start` - 15 edges
8. `localCalendar()` - 14 edges
9. `fetchAllPages()` - 14 edges
10. `sendMessage()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `1. Chat terbaru kadang menghilang` --references--> `sendMessage()`  [INFERRED]
  .lovable/plan.md → src/routes/index.tsx
- `Verifikasi` --references--> `useGeminiKeys()`  [INFERRED]
  docs/audit-2026-11-17.md → src/lib/gemini-key.ts
- `call()` --indirect_call--> `mainChatProvider()`  [INFERRED]
  tests/main-chat-integration.test.mjs → src/lib/main-chat-provider.ts
- `call()` --indirect_call--> `requestWithProviderFallback()`  [INFERRED]
  tests/main-chat-integration.test.mjs → src/lib/model-fallback.ts
- `call()` --indirect_call--> `historyAfter()`  [INFERRED]
  tests/main-chat-integration.test.mjs → src/lib/memory-policy.ts

## Import Cycles
- None detected.

## Communities (67 total, 30 thin omitted)

### Community 0 - "furina.functions.ts"
Cohesion: 0.09
Nodes (35): recallRecentThreads(), ALLOWED_ENT_TYPES, callXttsSpace(), ChatInput, ChatMsgSchema, clearAllMemories, CloneInput, compactMemories (+27 more)

### Community 1 - "FurinaApp"
Cohesion: 0.06
Nodes (41): UserMessageText(), androidOAuthRedirect(), decode(), encode(), FurinaSession, isAndroidLoginPage(), openAndroidLogin(), readKey() (+33 more)

### Community 2 - "MainActivity.java"
Cohesion: 0.09
Nodes (3): MainActivity, WebChromeClient, WebViewClient

### Community 3 - "index.tsx"
Cohesion: 0.06
Nodes (15): branchPrefix(), messageQuote, MessageQuote, ALL_FURINA_KEYS, Conversation, Msg, MsgStatus, Route (+7 more)

### Community 4 - "server.ts"
Cohesion: 0.10
Nodes (16): @supabase/supabase-js@^2.106.2, @supabase/supabase-js, lovable, lovableAuth, SignInOptions, attachSupabaseAuth, requireSupabaseAuth, supabase (+8 more)

### Community 5 - "devDependencies"
Cohesion: 0.08
Nodes (29): devDependencies, eslint@^9.32.0, eslint-config-prettier@^10.1.1, @eslint/js@^9.32.0, eslint-plugin-prettier@^5.2.6, eslint-plugin-react-hooks@^5.2.0, eslint-plugin-react-refresh@^0.4.20, globals@^15.15.0 (+21 more)

### Community 6 - "components.json"
Cohesion: 0.11
Nodes (18): aliases, components, hooks, lib, ui, utils, iconLibrary, registries (+10 more)

### Community 7 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+10 more)

### Community 8 - "Perbaikan Bug + Furina Lebih Hidup & Punya Pendirian"
Cohesion: 0.12
Nodes (16): 1. Chat terbaru kadang menghilang, 2. Waktu riwayat sama semua, 3. Grouping riwayat, 4. Inner state ringan (di luar mood), 5. Kesadaran waktu & sesi, 6. Memori diri (self-notes), 7. Opini & bantah dalam karakter, 8. Inisiatif dalam obrolan (+8 more)

### Community 9 - "dependencies"
Cohesion: 0.06
Nodes (35): dependencies, cmdk@^1.1.1, lucide-react@^0.575.0, @radix-ui/react-aspect-ratio@^1.1.8, @radix-ui/react-collapsible@^1.1.12, @radix-ui/react-context-menu@^2.2.16, @radix-ui/react-dropdown-menu@^2.1.16, @radix-ui/react-menubar@^1.1.16 (+27 more)

### Community 10 - "ref_node_assert"
Cohesion: 0.22
Nodes (4): BackgroundProvider, requestBackgroundChain(), mainChatProvider(), messages

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

### Community 16 - "source-function.mjs"
Cohesion: 0.13
Nodes (9): typescript@^5.8.3, typescript, listener(), chatFixture(), setup(), sourceCallback(), sourceFunction(), sourceServerHandler() (+1 more)

### Community 17 - "react"
Cohesion: 0.29
Nodes (3): lucide-react, react, MessageGesture()

### Community 21 - "package.json"
Cohesion: 0.08
Nodes (24): @lovable.dev/cloud-auth-js@^1.1.2, @radix-ui/react-hover-card@^1.1.15, @radix-ui/react-label@^2.1.8, @radix-ui/react-popover@^1.1.15, @radix-ui/react-slider@^1.3.6, @radix-ui/react-slot@^1.2.4, @radix-ui/react-tooltip@^1.2.8, react-resizable-panels@^4.6.5 (+16 more)

### Community 23 - "chat-continuity.ts"
Cohesion: 0.29
Nodes (9): continuationRequest(), continuityPrompt(), RecentThread, recentThreadsAmbiguous(), shortTurns(), shouldConsiderRecent(), commonWords, RecallEntry (+1 more)

### Community 24 - "identity-core.ts"
Cohesion: 0.11
Nodes (26): getIdentityCore, updateIdentityCore, applyReview(), candidate, category, emptyIdentity(), established, evidence (+18 more)

### Community 25 - "localCalendar"
Cohesion: 0.21
Nodes (17): BirthDateSettings(), ageInstructions(), birthdayContext(), birthdayInstructions(), localCalendar(), parseBirthDate(), splitBirthdayReply(), getBirthDate (+9 more)

### Community 26 - "model-fallback.ts"
Cohesion: 0.26
Nodes (8): CHAT_MODEL_FALLBACK_ORDER, ChatModel, ChatProvider, isChatProviderFallbackStatus(), requestWithChatModelFallback(), requestWithProviderFallback(), retryDelayMs(), requestOpenRouter()

### Community 27 - "ai-settings-api.ts"
Cohesion: 0.08
Nodes (22): addGeminiKey, addNvidiaKey, addOpenRouterKey, channels, controls, g, gemini, getGeminiKeySettings (+14 more)

### Community 28 - "chatWithFurina"
Cohesion: 0.19
Nodes (15): EMBEDDING_MODEL, issueFor(), requestBackgroundAi(), apiKey(), chatWithFurina, computeTimeCtx(), extractAndStoreEntities(), extractAndStoreMemory() (+7 more)

### Community 29 - "Audit AI dan API key Furina — 21 November 2026"
Cohesion: 0.29
Nodes (6): Audit AI dan API key Furina — 21 November 2026, Bagian yang masih memerlukan referensi, Logika yang diperiksa dan dipertahankan, Perubahan, Temuan yang direproduksi dan diperbaiki, Verifikasi

### Community 30 - "memory-policy.ts"
Cohesion: 0.38
Nodes (4): defaultMemoryPolicy, historyAfter(), memorySections, unavailableMemoryPolicy

### Community 31 - "ai-channel-settings.tsx"
Cohesion: 0.12
Nodes (5): AiChannelSettings(), channels, GeminiKeySettings(), save(), update()

### Community 33 - "NVIDIA NIM untuk percakapan utama"
Cohesion: 0.25
Nodes (7): Catatan rilis, Evaluasi dan urutan model, Gratis, katalog dan validasi key, NVIDIA NIM untuk percakapan utama, Penyimpanan dan migrasi, Rotasi dan transparansi, Verifikasi

### Community 34 - "Memori Furina"
Cohesion: 0.25
Nodes (7): Cara kerja, Evaluasi kualitas, Kelanjutan lintas chat, Memori Furina, Pengambilan konteks, Penggabungan otomatis, Referensi produk dan tampilan

### Community 36 - "response-feedback.ts"
Cohesion: 0.33
Nodes (5): feedbackExamples(), feedbackExamplesSchema, feedbackPrompt(), Rating, Ratings

### Community 38 - "NVIDIA NIM Main Chat Implementation Plan"
Cohesion: 0.40
Nodes (4): NVIDIA NIM Main Chat Implementation Plan, Review focus, Tasks, Verification ledger

### Community 43 - "Audit Furina app — 17 November 2026"
Cohesion: 0.33
Nodes (5): Audit Furina app — 17 November 2026, Batas dan tindak lanjut, Status PR dan pemeriksaan hosting, Temuan dan perbaikan, Verifikasi

### Community 46 - "ai-usage-stats.test.mjs"
Cohesion: 0.70
Nodes (3): formatResetCountdown(), getUsageSharePercent(), nextJakartaMonthReset()

### Community 47 - "memory-settings.tsx"
Cohesion: 0.09
Nodes (10): ConversationHistory(), day, Entry, time, controls, Memory, MemoryData, addMemory (+2 more)

### Community 50 - "nvidia-settings.browser.mjs"
Cohesion: 0.17
Nodes (8): @tailwindcss/vite@^4.2.1, vite@^7.3.8, @vitejs/plugin-react@^5.0.4, @tailwindcss/vite, vite, @vitejs/plugin-react, api, root

### Community 54 - "requireFurinaIdentity"
Cohesion: 0.07
Nodes (56): @tanstack/react-start, zod, Settings, supabaseAdmin, addGeminiKey, addNvidiaKey, addOpenRouterKey, getAiChannelSettings (+48 more)

## Knowledge Gaps
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `@tanstack/react-start` connect `requireFurinaIdentity` to `furina.functions.ts`, `index.tsx`, `server.ts`, `dependencies`, `memory-settings.tsx`, `package.json`, `localCalendar`, `ai-channel-settings.tsx`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Should `furina.functions.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.09041835357624832 - nodes in this community are weakly interconnected._
- **Why does `FurinaApp()` connect `FurinaApp` to `index.tsx`, `response-feedback.ts`, `memory-settings.tsx`, `react`, `MemorySettings`, `requireFurinaIdentity`, `localCalendar`, `ai-channel-settings.tsx`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Should `FurinaApp` be split into smaller, more focused modules?**
  _Cohesion score 0.0649895178197065 - nodes in this community are weakly interconnected._
- **Why does `dependencies` connect `dependencies` to `server.ts`, `__root.tsx`, `clsx`, `embla-carousel-react@^8.6.0`, `package.json`, `@hookform/resolvers@^5.2.2`, `input-otp@^1.4.2`, `@radix-ui/react-accordion@^1.2.12`, `@radix-ui/react-alert-dialog@^1.1.15`, `@radix-ui/react-navigation-menu@^1.2.14`, `@radix-ui/react-checkbox@^1.3.3`, `@radix-ui/react-radio-group@^1.3.8`, `@radix-ui/react-tabs@^1.1.13`, `nvidia-settings.browser.mjs`, `@radix-ui/react-toggle@^1.1.10`, `class-variance-authority@^0.7.1`, `react-day-picker@^9.14.0`, `date-fns@^4.1.0`, `@radix-ui/react-avatar@^1.1.11`, `@radix-ui/react-dialog@^1.1.15`, `@radix-ui/react-scroll-area@^1.2.10`, `@radix-ui/react-toggle-group@^1.1.11`, `react-dom@^19.2.0`, `recharts@^2.15.4`, `@tanstack/router-plugin@1.168.42`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Should `MainActivity.java` be split into smaller, more focused modules?**
  _Cohesion score 0.09468599033816426 - nodes in this community are weakly interconnected._
- **Should `index.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.06417112299465241 - nodes in this community are weakly interconnected._