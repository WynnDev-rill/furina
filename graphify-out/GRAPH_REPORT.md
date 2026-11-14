# Graph Report - furina  (2026-11-14)

## Corpus Check
- 46 files · ~22,769 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .toml 2, .css 1)

## Summary
- 484 nodes · 768 edges · 57 communities (18 shown, 39 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `29abaa5f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- furina.functions.ts
- FurinaApp
- MainActivity.java
- index.tsx
- @tanstack/react-start
- devDependencies
- components.json
- compilerOptions
- Perbaikan Bug + Furina Lebih Hidup & Punya Pendirian
- package.json
- dependencies
- __root.tsx
- scripts
- Furina Companion
- clsx
- Furina Companion
- android-auth.ts
- react
- Routes
- DESIGN.md
- embla-carousel-react@^8.6.0
- cmdk@^1.1.1
- date-fns@^4.1.0
- @lovable.dev/cloud-auth-js
- lucide-react
- @radix-ui/react-accordion@^1.2.12
- @radix-ui/react-avatar@^1.1.11
- @radix-ui/react-context-menu@^2.2.16
- @radix-ui/react-collapsible@^1.1.12
- @radix-ui/react-menubar@^1.1.16
- @radix-ui/react-dropdown-menu@^2.1.16
- @radix-ui/react-hover-card@^1.1.15
- @radix-ui/react-label@^2.1.8
- @radix-ui/react-navigation-menu@^1.2.14
- @radix-ui/react-popover@^1.1.15
- @radix-ui/react-progress@^1.1.8
- @radix-ui/react-tooltip@^1.2.8
- react-dom@^19.2.0
- @radix-ui/react-separator@^1.1.8
- @radix-ui/react-slider@^1.3.6
- @radix-ui/react-slot@^1.2.4
- @tanstack/router-plugin@^1.167.28
- @radix-ui/react-tabs@^1.1.13
- @radix-ui/react-toggle@^1.1.10
- react-day-picker@^9.14.0
- react-hook-form@^7.71.2
- react-resizable-panels@^4.6.5
- tailwindcss@^4.2.1
- @tailwindcss/vite@^4.2.1
- tw-animate-css@^1.3.4
- vaul@^1.1.2
- vite-tsconfig-paths@^6.0.2
- pullFromCloud
- webview-android/README.md

## God Nodes (most connected - your core abstractions)
1. `FurinaApp()` - 41 edges
2. `chatWithFurina` - 20 edges
3. `MainActivity` - 20 edges
4. `compilerOptions` - 17 edges
5. `requireFurinaIdentity()` - 16 edges
6. `apiKey()` - 11 edges
7. `@tanstack/react-start` - 10 edges
8. `embed()` - 10 edges
9. `sendMessage()` - 8 edges
10. `scripts` - 7 edges

## Surprising Connections (you probably didn't know these)
- `1. Chat terbaru kadang menghilang` --references--> `sendMessage()`  [INFERRED]
  .lovable/plan.md → src/routes/index.tsx
- `FurinaApp()` --calls--> `openAndroidLogin()`  [EXTRACTED]
  src/routes/index.tsx → src/lib/android-auth.ts
- `FurinaApp()` --calls--> `isAndroidLoginPage()`  [EXTRACTED]
  src/routes/index.tsx → src/lib/android-auth.ts
- `FurinaApp()` --calls--> `androidOAuthRedirect()`  [EXTRACTED]
  src/routes/index.tsx → src/lib/android-auth.ts
- `FurinaApp()` --calls--> `returnAndroidSession()`  [EXTRACTED]
  src/routes/index.tsx → src/lib/android-auth.ts

## Import Cycles
- None detected.

## Communities (57 total, 39 thin omitted)

### Community 0 - "furina.functions.ts"
Cohesion: 0.07
Nodes (57): addMemory, AFFECTION_HITS, ALLOWED_ENT_TYPES, apiKey(), callXttsSpace(), ChatInput, ChatMsgSchema, chatWithFurina (+49 more)

### Community 1 - "FurinaApp"
Cohesion: 0.11
Nodes (21): compressImage(), fmtTime(), FurinaApp(), clearChat(), handleBgUpload(), handleImagePick(), maybeSummarize(), playTTS() (+13 more)

### Community 2 - "MainActivity.java"
Cohesion: 0.09
Nodes (3): MainActivity, WebChromeClient, WebViewClient

### Community 3 - "index.tsx"
Cohesion: 0.04
Nodes (12): ALL_FURINA_KEYS, Conversation, Msg, MsgStatus, Route, SettingsSection, settingsSections, SettingsSnapshot (+4 more)

### Community 4 - "@tanstack/react-start"
Cohesion: 0.07
Nodes (24): @supabase/supabase-js@^2.106.2, @tanstack/react-start@^1.167.50, zod@^3.24.2, @supabase/supabase-js, @tanstack/react-start, zod, lovable, lovableAuth (+16 more)

### Community 5 - "devDependencies"
Cohesion: 0.06
Nodes (35): devDependencies, eslint@^9.32.0, eslint-config-prettier@^10.1.1, @eslint/js@^9.32.0, eslint-plugin-prettier@^5.2.6, eslint-plugin-react-hooks@^5.2.0, eslint-plugin-react-refresh@^0.4.20, globals@^15.15.0 (+27 more)

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
Cohesion: 0.12
Nodes (16): input-otp@^1.4.2, @radix-ui/react-aspect-ratio@^1.1.8, @radix-ui/react-dialog@^1.1.15, @radix-ui/react-select@^2.2.6, @radix-ui/react-switch@^1.2.6, @radix-ui/react-toggle-group@^1.1.11, name, private (+8 more)

### Community 10 - "dependencies"
Cohesion: 0.12
Nodes (17): dependencies, class-variance-authority@^0.7.1, @hookform/resolvers@^5.2.2, @radix-ui/react-alert-dialog@^1.1.15, @radix-ui/react-checkbox@^1.3.3, @radix-ui/react-radio-group@^1.3.8, @radix-ui/react-scroll-area@^1.2.10, recharts@^2.15.4 (+9 more)

### Community 11 - "__root.tsx"
Cohesion: 0.14
Nodes (5): @tanstack/react-query@^5.83.0, @tanstack/react-router@^1.168.25, @tanstack/react-query, @tanstack/react-router, Route

### Community 12 - "scripts"
Cohesion: 0.29
Nodes (7): scripts, build, build:dev, dev, format, lint, preview

### Community 13 - "Furina Companion"
Cohesion: 0.33
Nodes (5): Arsitektur, Batas proyek, Furina Companion, Skill coding, Workflow

### Community 14 - "clsx"
Cohesion: 0.33
Nodes (4): clsx@^2.1.1, tailwind-merge@^3.5.0, clsx, tailwind-merge

### Community 15 - "Furina Companion"
Cohesion: 0.40
Nodes (4): Cakupan, Furina Companion, Kebutuhan pengguna, Platform

### Community 16 - "android-auth.ts"
Cohesion: 0.27
Nodes (11): androidOAuthRedirect(), decode(), encode(), FurinaSession, isAndroidLoginPage(), openAndroidLogin(), readKey(), receiveAndroidSession() (+3 more)

### Community 54 - "pullFromCloud"
Cohesion: 0.25
Nodes (8): fetchAllPages(), clearAllFurinaLocal(), deleteConversation(), logout(), pullFromCloud(), pushAllConversationsTo(), pushSettingsTo(), newConversation()

## Knowledge Gaps
- **39 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `@tanstack/react-start` connect `@tanstack/react-start` to `furina.functions.ts`, `package.json`, `index.tsx`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Should `furina.functions.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.06836055656382335 - nodes in this community are weakly interconnected._
- **Why does `FurinaApp()` connect `FurinaApp` to `android-auth.ts`, `index.tsx`, `pullFromCloud`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Should `FurinaApp` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Why does `dependencies` connect `dependencies` to `@tanstack/react-start`, `package.json`, `__root.tsx`, `clsx`, `react`, `embla-carousel-react@^8.6.0`, `cmdk@^1.1.1`, `date-fns@^4.1.0`, `@lovable.dev/cloud-auth-js`, `lucide-react`, `@radix-ui/react-accordion@^1.2.12`, `@radix-ui/react-avatar@^1.1.11`, `@radix-ui/react-context-menu@^2.2.16`, `@radix-ui/react-collapsible@^1.1.12`, `@radix-ui/react-menubar@^1.1.16`, `@radix-ui/react-dropdown-menu@^2.1.16`, `@radix-ui/react-hover-card@^1.1.15`, `@radix-ui/react-label@^2.1.8`, `@radix-ui/react-navigation-menu@^1.2.14`, `@radix-ui/react-popover@^1.1.15`, `@radix-ui/react-progress@^1.1.8`, `@radix-ui/react-tooltip@^1.2.8`, `react-dom@^19.2.0`, `@radix-ui/react-separator@^1.1.8`, `@radix-ui/react-slider@^1.3.6`, `@radix-ui/react-slot@^1.2.4`, `@tanstack/router-plugin@^1.167.28`, `@radix-ui/react-tabs@^1.1.13`, `@radix-ui/react-toggle@^1.1.10`, `react-day-picker@^9.14.0`, `react-hook-form@^7.71.2`, `react-resizable-panels@^4.6.5`, `tailwindcss@^4.2.1`, `@tailwindcss/vite@^4.2.1`, `tw-animate-css@^1.3.4`, `vaul@^1.1.2`, `vite-tsconfig-paths@^6.0.2`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Should `MainActivity.java` be split into smaller, more focused modules?**
  _Cohesion score 0.09468599033816426 - nodes in this community are weakly interconnected._
- **Should `index.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._