#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC49 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge" / "app"
    html_path = app / "src/main/assets/furinahub/index.html"
    main_path = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    gradle_path = app / "build.gradle"
    hub_path = root / "core/furina_agent/hub.py"
    updater_path = app / "src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"
    for path in (html_path, main_path, gradle_path, hub_path, updater_path):
        if not path.is_file():
            raise SystemExit(f"RC49 source missing: {path}")

    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = once(gradle, "versionCode 10048", "versionCode 10049", "versionCode")
    gradle = once(gradle, "versionName '1.0.0-rc48'", "versionName '1.0.0-rc49'", "versionName")
    hub = once(hub_path.read_text(encoding="utf-8"), '"bridge_target": "1.0.0-rc48"', '"bridge_target": "1.0.0-rc49"', "bridge target")
    updater = once(updater_path.read_text(encoding="utf-8"), "FurinaHub-Updater/14", "FurinaHub-Updater/15", "updater agent")

    html = html_path.read_text(encoding="utf-8")
    html = once(
        html,
        ".editorStage #editorCanvas{opacity:0!important;background:none!important;z-index:0!important}",
        ".editorStage #editorCanvas{opacity:1!important;background:transparent!important;z-index:2!important}.editorPreviewImage{z-index:1!important}",
        "visible raster canvas",
    )
    html = once(
        html,
        "const ctx=c.getContext('2d');if(ctx)ctx.clearRect(0,0,c.width,c.height);d.width=c.width;d.height=c.height;stage.insertBefore(img,c.nextSibling);",
        "const ctx=c.getContext('2d',{alpha:true});if(!ctx)throw new Error('Canvas gambar tidak tersedia');ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(img,0,0,c.width,c.height);d.width=c.width;d.height=c.height;stage.insertBefore(img,c.nextSibling);",
        "rasterize preview pixels",
    )
    html = once(
        html,
        "o.drawImage(preview,sx*nx,sy*ny,sw*nx,sh*ny,0,0,sw,sh);",
        "o.drawImage(src,sx,sy,sw,sh,0,0,sw,sh);",
        "export visible raster",
    )
    html = once(
        html,
        "async function pollThinking(requestId,el){for(let i=0;i<1200&&el;i++){if(!el.isConnected&&!document.getElementById('messages'))return;",
        "async function pollThinking(requestId,el){for(let i=0;i<1200&&el;i++){if(!el.isConnected)return;",
        "stop detached progress polling",
    )

    main = main_path.read_text(encoding="utf-8")
    main = once(main, "import android.app.PendingIntent;\n", "import android.app.PendingIntent;\nimport android.content.ClipData;\nimport android.content.ContentValues;\n", "camera imports")
    main = once(main, "import android.graphics.Color;\n", "import android.graphics.Color;\nimport android.graphics.ImageDecoder;\n", "image decoder import")
    main = once(main, "    private byte[] pendingImageSave;\n", "    private byte[] pendingImageSave;\n    private Uri pendingCameraUri;\n", "pending camera field")
    old_camera = '''    private void takePhoto() {
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        if (intent.resolveActivity(getPackageManager()) == null) {
            Toast.makeText(this, "Aplikasi kamera tidak tersedia.", Toast.LENGTH_LONG).show();
            return;
        }
        startActivityForResult(intent, REQ_CAMERA);
    }'''
    new_camera = '''    private void takePhoto() {
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        if (intent.resolveActivity(getPackageManager()) == null) {
            Toast.makeText(this, "Aplikasi kamera tidak tersedia.", Toast.LENGTH_LONG).show();
            return;
        }
        try {
            ContentValues values = new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME, "furinahub-" + System.currentTimeMillis() + ".jpg");
            values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            values.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/FurinaHub");
            pendingCameraUri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
            if (pendingCameraUri == null) throw new IllegalStateException("Tidak dapat menyiapkan file kamera.");
            intent.putExtra(MediaStore.EXTRA_OUTPUT, pendingCameraUri);
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            intent.setClipData(ClipData.newRawUri("FurinaHub camera", pendingCameraUri));
            startActivityForResult(intent, REQ_CAMERA);
        } catch (Throwable error) {
            if (pendingCameraUri != null) getContentResolver().delete(pendingCameraUri, null, null);
            pendingCameraUri = null;
            Toast.makeText(this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show();
        }
    }

    private void readCameraImage(Uri uri) {
        io.execute(() -> {
            try {
                ImageDecoder.Source source = ImageDecoder.createSource(getContentResolver(), uri);
                Bitmap bitmap = ImageDecoder.decodeBitmap(source, (decoder, info, ignored) -> {
                    int width = info.getSize().getWidth(), height = info.getSize().getHeight();
                    int longest = Math.max(width, height);
                    if (longest > 4096) {
                        float scale = 4096f / longest;
                        decoder.setTargetSize(Math.max(1, Math.round(width * scale)), Math.max(1, Math.round(height * scale)));
                    }
                    decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
                });
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                bitmap.compress(Bitmap.CompressFormat.JPEG, 94, out);
                if (out.size() > MAX_IMAGE_BYTES) {
                    out.reset();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 86, out);
                }
                if (out.size() > MAX_IMAGE_BYTES) throw new IllegalArgumentException("Foto terlalu besar setelah diproses.");
                emitImage("kamera.jpg", "image/jpeg", out.toByteArray());
            } catch (Throwable error) {
                handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
            }
        });
    }'''
    main = once(main, old_camera, new_camera, "full resolution camera")
    old_result = '''        } else if (requestCode == REQ_CAMERA && resultCode == RESULT_OK && data != null && data.getExtras() != null) {
            Object raw = data.getExtras().get("data");
            if (raw instanceof Bitmap) {
                io.execute(() -> {
                    try {
                        ByteArrayOutputStream out = new ByteArrayOutputStream();
                        ((Bitmap) raw).compress(Bitmap.CompressFormat.JPEG, 92, out);
                        emitImage("kamera.jpg", "image/jpeg", out.toByteArray());
                    } catch (Throwable error) {
                        handler.post(() -> Toast.makeText(MainActivity.this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show());
                    }
                });
            }
        } else if (requestCode == REQ_SAVE_IMAGE'''
    new_result = '''        } else if (requestCode == REQ_CAMERA) {
            Uri captured = pendingCameraUri;
            pendingCameraUri = null;
            if (resultCode == RESULT_OK && captured != null) readCameraImage(captured);
            else if (captured != null) getContentResolver().delete(captured, null, null);
        } else if (requestCode == REQ_SAVE_IMAGE'''
    main = once(main, old_result, new_result, "camera result")

    combined = "\n".join((gradle, hub, updater, html, main))
    checks = (
        "versionCode 10049", "versionName '1.0.0-rc49'", '"bridge_target": "1.0.0-rc49"',
        "FurinaHub-Updater/15", "ctx.drawImage(img,0,0,c.width,c.height)",
        "o.drawImage(src,sx,sy,sw,sh", "if(!el.isConnected)return", "MediaStore.EXTRA_OUTPUT",
        "readCameraImage(Uri uri)", "ImageDecoder.ALLOCATOR_SOFTWARE",
    )
    missing = [item for item in checks if item not in combined]
    if missing:
        raise SystemExit("RC49 integration incomplete: " + ", ".join(missing))
    if 'data.getExtras().get("data")' in main:
        raise SystemExit("RC49 thumbnail camera path remains")

    gradle_path.write_text(gradle, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")
    updater_path.write_text(updater, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    main_path.write_text(main, encoding="utf-8")
    print("FURINAHUB_ANDROID_RC49_VISIBLE_EDITOR_CAMERA_OK")


if __name__ == "__main__":
    main()
