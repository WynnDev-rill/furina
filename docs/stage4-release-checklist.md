# Furina Stage 4 Release Hardening

## Native Android
- [ ] Verify forced update flow does not block first install.
- [ ] Verify APK update keeps application data and downloaded models.
- [ ] Verify WebView safe area and system navigation handling.
- [ ] Verify launcher icon adaptive rendering.

## AI System
- [ ] Verify Lovable AI remains the default fallback.
- [ ] Verify offline model activation/deactivation.
- [ ] Verify offline model files are separated from conversation data.
- [ ] Verify image model capability is exposed only when supported.

## Data
- [ ] Verify local backup and restore.
- [ ] Verify Google login sync does not overwrite local model files.
- [ ] Verify reinstall/update recovery behavior.

## Release Testing
- [ ] Fresh install.
- [ ] Update from previous APK.
- [ ] Offline launch.
- [ ] No-model launch.
- [ ] Low storage scenario.
