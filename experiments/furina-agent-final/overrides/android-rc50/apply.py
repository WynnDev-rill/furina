#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import sys


BUNDLE_ID = "furina-2026.08.21-rc62-rc50"


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC50 marker missing: {label}")
    return text.replace(old, new, 1)


def between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        if replacement.strip() in text:
            return text
        raise SystemExit(f"RC50 start marker missing: {label}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"RC50 end marker missing: {label}")
    return text[:a] + replacement + text[b:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    here = Path(__file__).resolve().parent
    app = root / "bridge/app"
    java = app / "src/main/java/com/wynndev/furinaagentbridge"
    assets = app / "src/main/assets/furinahub"
    paths = {
        "html": assets / "index.html",
        "main": java / "MainActivity.java",
        "runtime": java / "BridgeRuntime.java",
        "updater": java / "BridgeUpdater.java",
        "manifest": app / "src/main/AndroidManifest.xml",
        "gradle": app / "build.gradle",
        "hub": root / "core/furina_agent/hub.py",
    }
    for path in paths.values():
        if not path.is_file():
            raise SystemExit(f"RC50 source missing: {path}")

    shutil.copyfile(here / "NativeImageEditorActivity.java", java / "NativeImageEditorActivity.java")
    shutil.copyfile(here / "vendor/fuse.min.cjs", assets / "fuse.min.cjs")
    license_dir = app / "src/main/assets/licenses"
    license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(here / "vendor/FUSE-LICENSE.txt", license_dir / "Fuse.js-Apache-2.0.txt")

    gradle = paths["gradle"].read_text(encoding="utf-8")
    gradle = once(gradle, "versionCode 10049", "versionCode 10050", "versionCode")
    gradle = once(gradle, "versionName '1.0.0-rc49'", "versionName '1.0.0-rc50'", "versionName")

    manifest = paths["manifest"].read_text(encoding="utf-8")
    manifest = once(
        manifest,
        '''        <activity
            android:name=".MainActivity"
            android:exported="true">''',
        '''        <activity
            android:name=".NativeImageEditorActivity"
            android:exported="false"
            android:screenOrientation="portrait"
            android:theme="@style/AppTheme" />
        <activity
            android:name=".MainActivity"
            android:exported="true">''',
        "native editor activity",
    )

    hub = once(
        paths["hub"].read_text(encoding="utf-8"),
        '"bridge_target": "1.0.0-rc49"',
        '"bridge_target": "1.0.0-rc50"',
        "bridge target",
    )

    runtime = paths["runtime"].read_text(encoding="utf-8")
    runtime = once(
        runtime,
        'out.put("service", "furina-bridge");',
        f'out.put("service", "furina-bridge");\n        out.put("bundle_id", "{BUNDLE_ID}");',
        "bridge bundle id",
    )

    updater = paths["updater"].read_text(encoding="utf-8")
    updater = between(
        updater,
        "    private static final String[] MANIFEST_URLS",
        "    private static final long AUTO_CHECK_INTERVAL_MS",
        '''    private static final String[] MANIFEST_URLS = new String[]{
            "https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/bundle.json"
    };
''',
        "one bundle metadata source",
    )
    updater_parse = '''                JSONObject manifest = new JSONObject(readTextAny(MANIFEST_URLS, 256 * 1024));
                if (manifest.optInt("schema", 0) != 1) throw new IllegalStateException("schema bundle tidak didukung");
                String bundleId = manifest.optString("bundle_id", "").trim();
                long latestCode = manifest.optLong("bridge_version_code", 0L);
                String latestName = manifest.optString("bridge_version", "").trim();
                String packageName = manifest.optString("package_name", "").trim();
                String url = manifest.optString("apk_url", "").trim();
                String sha = normalizeDigest(manifest.optString("apk_sha256", ""));
                String signer = normalizeDigest(manifest.optString("signer_sha256", ""));
                String coreVersion = manifest.optString("core_version", "").trim();
                String dependencyRevision = manifest.optString("dependency_revision", "").trim();
                if (bundleId.isEmpty() || coreVersion.isEmpty() || dependencyRevision.isEmpty()
                        || latestCode <= 0 || latestName.isEmpty()) {
                    throw new IllegalStateException("bundle update belum lengkap");
                }
                if (!activity.getPackageName().equals(packageName)) {
                    throw new IllegalStateException("package bundle berbeda");
                }
                if (!url.startsWith("https://github.com/WynnDev-rill/furina/releases/download/")
                        || sha.length() != 64 || signer.length() != 64) {
                    throw new IllegalStateException("metadata keamanan bundle tidak valid");
                }

'''
    updater = between(
        updater,
        "                JSONObject manifest = new JSONObject(readTextAny(MANIFEST_URLS, 256 * 1024));",
        "                remoteVersionCode = latestCode;",
        updater_parse,
        "atomic bundle parser",
    )
    updater = once(updater, "FurinaHub-Updater/15", "FurinaHub-Updater/16", "updater agent")
    updater = once(
        updater,
        'conn.setRequestProperty("User-Agent", "FurinaHub-Updater/16");',
        'conn.setRequestProperty("User-Agent", "FurinaHub-Updater/16");\n'
        '        conn.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0");\n'
        '        conn.setRequestProperty("Pragma", "no-cache");',
        "metadata cache bypass",
    )

    main = paths["main"].read_text(encoding="utf-8")
    main = once(
        main,
        "import java.io.ByteArrayOutputStream;\n",
        "import java.io.ByteArrayOutputStream;\nimport java.io.File;\nimport java.io.FileInputStream;\nimport java.io.FileOutputStream;\n",
        "native editor imports",
    )
    main = once(
        main,
        "    private static final int REQ_SAVE_IMAGE = 27;\n",
        "    private static final int REQ_SAVE_IMAGE = 27;\n"
        "    private static final int REQ_NATIVE_EDITOR = 28;\n"
        f'    private static final String EXPECTED_BUNDLE_ID = "{BUNDLE_ID}";\n'
        '    private static final String EXPECTED_CORE_VERSION = "1.0.0-rc62";\n'
        '    private static final String EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r32";\n',
        "editor and bundle constants",
    )
    main = once(
        main,
        '    private String pendingImageMime = "image/jpeg";\n',
        '    private String pendingImageMime = "image/jpeg";\n'
        "    private File pendingEditorSource;\n"
        "    private File pendingEditorOutput;\n"
        "    private volatile boolean bundleSyncChecked;\n",
        "native editor state",
    )
    main = once(
        main,
        '            String html = out.toString("UTF-8");\n'
        '            web.loadDataWithBaseURL(APP_ORIGIN, html, "text/html", "UTF-8", null);',
        '''            String html = out.toString("UTF-8");
            try (InputStream fuseIn = getAssets().open("furinahub/fuse.min.cjs");
                 ByteArrayOutputStream fuseOut = new ByteArrayOutputStream()) {
                byte[] fuseBuf = new byte[8192];
                int fuseRead;
                while ((fuseRead = fuseIn.read(fuseBuf)) >= 0) fuseOut.write(fuseBuf, 0, fuseRead);
                String fuse = fuseOut.toString("UTF-8").replace("</script", "<\\\\/script");
                String bootstrap = "const module={exports:{}};const exports=module.exports;\\n"
                        + fuse + "\\nwindow.Fuse=module.exports;";
                html = html.replace("/*__FURINAHUB_FUSE__*/", bootstrap);
            }
            web.loadDataWithBaseURL(APP_ORIGIN, html, "text/html", "UTF-8", null);''',
        "Fuse asset injection",
    )
    editor_method = '''    private void editImage(String encoded, String name, String mime) {
        try {
            byte[] bytes = Base64.decode(String.valueOf(encoded), Base64.DEFAULT);
            if (bytes.length == 0 || bytes.length > MAX_IMAGE_BYTES) throw new IllegalArgumentException("Gambar tidak valid.");
            File dir = new File(getCacheDir(), "native-editor");
            if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Cache editor tidak dapat dibuat.");
            pendingEditorSource = new File(dir, "source-" + System.currentTimeMillis());
            pendingEditorOutput = new File(dir, "result-" + System.currentTimeMillis());
            try (FileOutputStream out = new FileOutputStream(pendingEditorSource)) {
                out.write(bytes);
                out.getFD().sync();
            }
            Intent intent = new Intent(this, NativeImageEditorActivity.class)
                    .putExtra(NativeImageEditorActivity.EXTRA_SOURCE, pendingEditorSource.getAbsolutePath())
                    .putExtra(NativeImageEditorActivity.EXTRA_OUTPUT, pendingEditorOutput.getAbsolutePath())
                    .putExtra(NativeImageEditorActivity.EXTRA_NAME, String.valueOf(name == null ? "gambar" : name))
                    .putExtra(NativeImageEditorActivity.EXTRA_MIME, String.valueOf(mime));
            startActivityForResult(intent, REQ_NATIVE_EDITOR);
        } catch (Throwable error) {
            Toast.makeText(this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show();
        }
    }

'''
    main = once(
        main,
        "    private void saveImage(String encoded, String name, String mime) {",
        editor_method + "    private void saveImage(String encoded, String name, String mime) {",
        "native editor launch",
    )
    result_old = '''        if (requestCode == REQ_SAVE_IMAGE && resultCode != RESULT_OK) pendingImageSave = null;
        if (requestCode == REQ_PICK_ATTACHMENT'''
    result_new = '''        if (requestCode == REQ_SAVE_IMAGE && resultCode != RESULT_OK) pendingImageSave = null;
        if (requestCode == REQ_NATIVE_EDITOR) {
            File source = pendingEditorSource;
            File output = pendingEditorOutput;
            pendingEditorSource = null;
            pendingEditorOutput = null;
            if (resultCode == RESULT_OK && data != null && output != null && output.isFile()) {
                final String resultName = data.getStringExtra(NativeImageEditorActivity.EXTRA_NAME);
                final String resultMime = data.getStringExtra(NativeImageEditorActivity.EXTRA_MIME);
                io.execute(() -> {
                    try {
                        if (output.length() <= 0 || output.length() > MAX_IMAGE_BYTES) throw new IllegalArgumentException("Hasil editor tidak valid.");
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        try (InputStream in = new FileInputStream(output)) {
                            byte[] buffer = new byte[8192];
                            int read;
                            while ((read = in.read(buffer)) >= 0) bytes.write(buffer, 0, read);
                        }
                        emitImage(resultName, resultMime, bytes.toByteArray());
                    } catch (Throwable error) {
                        handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
                    } finally {
                        output.delete();
                        if (source != null) source.delete();
                    }
                });
            } else {
                if (output != null) output.delete();
                if (source != null) source.delete();
            }
            return;
        }
        if (requestCode == REQ_PICK_ATTACHMENT'''
    main = once(main, result_old, result_new, "native editor result")
    main = once(
        main,
        '        @JavascriptInterface public void saveImage(String encoded, String name, String mime) { handler.post(() -> MainActivity.this.saveImage(encoded, name, mime)); }\n',
        '        @JavascriptInterface public void saveImage(String encoded, String name, String mime) { handler.post(() -> MainActivity.this.saveImage(encoded, name, mime)); }\n'
        '        @JavascriptInterface public void editImage(String encoded, String name, String mime) { handler.post(() -> MainActivity.this.editImage(encoded, name, mime)); }\n',
        "native editor JavaScript bridge",
    )
    sync_method = '''    private void ensureBundleSync() {
        if (bundleSyncChecked || coreUpdateBusy || hubToken == null || hubToken.length() < 24) return;
        bundleSyncChecked = true;
        io.execute(() -> {
            try {
                JSONObject state = new JSONObject(coreRequest("GET", "/api/system", "{}"));
                String core = state.optString("core_version", "");
                String revision = state.optString("dependency_revision", "");
                String bundle = state.optString("bundle_id", "");
                if (!EXPECTED_CORE_VERSION.equals(core) || !EXPECTED_DEPENDENCY_REVISION.equals(revision)
                        || !EXPECTED_BUNDLE_ID.equals(bundle)) {
                    bundleSyncChecked = false;
                    handler.post(this::startCoreRecoveryUpdate);
                }
            } catch (Throwable ignored) {
                bundleSyncChecked = false;
            }
        });
    }

'''
    main = once(main, "    private void openTermux() {\n", sync_method + "    private void openTermux() {\n", "bundle auto-sync")
    main = main.replace(
        'setConnection("connected", "Furina Core terhubung.", false);',
        'setConnection("connected", "Furina Core terhubung.", false);\n'
        '                handler.postDelayed(this::ensureBundleSync, 1200L);',
    )

    html = paths["html"].read_text(encoding="utf-8")
    html = once(html, "<script>\nconst NATIVE=", "<script>/*__FURINAHUB_FUSE__*/</script>\n<script>\nconst NATIVE=", "Fuse marker")
    html = once(
        html,
        '<div id="memoryOnline" class="hidden"><button class="btn full" onclick="addMemoryPrompt()">+ Tambah memori</button>',
        '<div id="memoryOnline" class="hidden"><div class="pluginSearch"><input id="memorySearch" placeholder="Cari ingatan, termasuk salah ketik…" oninput="filterMemory(this.value)"></div><button class="btn full" onclick="addMemoryPrompt()">+ Tambah memori</button>',
        "memory search field",
    )
    html = between(
        html,
        "async function openImageEditor()",
        "function closeImageEditor()",
        (here / "native-editor.js").read_text(encoding="utf-8"),
        "native editor JavaScript",
    )
    html = between(
        html,
        "function renderMemory()",
        "async function loadMemory()",
        (here / "memory-search.js").read_text(encoding="utf-8"),
        "Fuse memory search",
    )

    combined = "\n".join((gradle, manifest, hub, runtime, updater, main, html))
    checks = (
        "versionCode 10050", "versionName '1.0.0-rc50'", "NativeImageEditorActivity",
        "NATIVE.editImage", "fuse.min.cjs", "window.Fuse=module.exports",
        "useTokenSearch:true", BUNDLE_ID, "bundle.json", "Cache-Control",
        "EXPECTED_CORE_VERSION", "ensureBundleSync",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit("RC50 integration incomplete: " + ", ".join(missing))

    paths["gradle"].write_text(gradle, encoding="utf-8")
    paths["manifest"].write_text(manifest, encoding="utf-8")
    paths["hub"].write_text(hub, encoding="utf-8")
    paths["runtime"].write_text(runtime, encoding="utf-8")
    paths["updater"].write_text(updater, encoding="utf-8")
    paths["main"].write_text(main, encoding="utf-8")
    paths["html"].write_text(html, encoding="utf-8")
    print("FURINAHUB_ANDROID_RC50_NATIVE_EDITOR_FUSE_BUNDLE_OK")


if __name__ == "__main__":
    main()
