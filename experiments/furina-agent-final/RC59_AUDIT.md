# RC59 / FurinaHub RC44 system bug sweep

This release is intentionally scoped to functional regressions and unnecessary runtime paths.

Fixed defects:
- upstream RPC deadline could block forever on a silent child because stdout.readline() was blocking;
- ZeroChat updates could be dropped during fast conversations because each turn spawned a delayed thread and used a nonblocking lock;
- upstream post-turn work could start subprocesses on the response path;
- empty upstream context injected technical fallback text into the system prompt;
- LumiMuse foreground retrieval had an excessive 5 second ceiling;
- TypeScript runtime used the floating `typescript@5` range rather than an exact tested version;
- stale RC57/RC58 temporary files and the obsolete Utsuwa `.mjs` worker are removed without touching user data;
- Termux installer/update progress is visible again while detailed logs remain in the log file;
- FurinaHub RC43 image editing hid its source canvas and depended on a second Blob-URL IMG layer, leaving a black editor when that layer failed to paint;
- FurinaHub RC44 uses one visible canvas, `createImageBitmap` with data-URL fallback, decode/error status, and direct crop composition to avoid a redundant full-size merge canvas.

Regression gates:
- RC52 -> RC59 migration;
- 32 rapid turns retained in order;
- silent worker killed by wall-clock timeout;
- all four pinned upstream engines executed;
- RC44 HTML/JS syntax and obsolete preview path absence;
- Android APK build;
- signing continuity against RC43 before publishing an update APK.
