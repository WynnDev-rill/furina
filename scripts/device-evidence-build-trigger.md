# Device evidence APK build trigger

This tracked marker exists so the merge that finalized the login-free device-evidence backend also crosses the stable APK workflow's `scripts/**` path filter.

The resulting `main` build is the distributable APK build: it generates the exact-main enrollment token, embeds it only in that signed APK, registers only its hash through GitHub OIDC, and verifies signing/package identity before artifact upload.

Future workflow maintenance should add `engineering/device-evidence/**` directly to the stable APK trigger paths so backend evidence changes do not need a marker commit.
