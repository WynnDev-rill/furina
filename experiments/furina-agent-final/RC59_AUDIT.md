# RC59 / FurinaHub RC44 system bug sweep

This release is intentionally scoped to functional regressions and unnecessary runtime paths.

Fixed defects:
- upstream RPC deadline could block forever on a silent child because stdout.readline() was blocking;
- ZeroChat updates could be dropped during fast conversations because each turn spawned a delayed thread and used a nonblocking lock;
- local memory consolidation had the same lossy thread-per-turn/nonblocking-lock pattern, so some turns could never reach consolidation;
- upstream post-turn work could start subprocesses on the response path;
- empty upstream context injected technical fallback text into the system prompt;
- LumiMuse foreground retrieval had an excessive 5 second ceiling;
- TypeScript runtime used the floating `typescript@5` range rather than an exact tested version;
- stale RC57/RC58 temporary files and the obsolete Utsuwa `.mjs` worker are removed without touching user data;
- Termux installer/update progress is visible again while detailed logs remain in the log file;
- FurinaHub RC43 image editing hid its source canvas and depended on a second Blob-URL IMG layer, leaving a black editor when that layer failed to paint;
- the first RC44 fallback could itself wait forever when `img.decode()` failed after the image error event had already fired; RC44 now checks `complete` correctly and has an 8 second decode deadline;
- FurinaHub RC44 uses one visible canvas, `createImageBitmap` with bounded data-URL fallback, decode/error status, and direct crop composition to avoid a redundant full-size merge canvas;
- the active CI workflow still carried the obsolete RC28 filename and duplicated brittle hard-coded blob hashes; it is replaced by one RC29 workflow that validates hashes from the installer bindings themselves;
- the initial RC44 publication draft built/uploaded a debug APK and omitted canonical `bridge.json`; publication now restores the existing release keystore, builds `assembleRelease`, verifies signer continuity against RC43, and publishes the immutable RC44 APK plus bridge metadata required by the in-app updater.

Regression gates:
- RC52 -> RC59 migration;
- 32 rapid turns retained in order in both companion queues;
- silent worker killed by wall-clock timeout;
- all four pinned upstream engines executed;
- exact TypeScript 5.9.3 runtime;
- RC44 HTML/JS syntax, bounded decode fallback, and obsolete preview path absence;
- Android debug APK build on PR;
- signed release APK identity and signer continuity against RC43 before publishing;
- live Core manifest and FurinaHub bridge metadata after publication.
