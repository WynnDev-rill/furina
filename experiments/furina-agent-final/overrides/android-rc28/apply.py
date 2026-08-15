#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC28 marker mismatch: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    html_path = app / "src/main/assets/furinahub/index.html"
    gradle = app / "build.gradle"
    for path in (main_activity, html_path, gradle):
        if not path.is_file():
            raise SystemExit(f"RC28 source missing: {path}")

    body = main_activity.read_text(encoding="utf-8")
    body = replace_once(
        body,
        'if (data.length > 2_000_000) throw new IllegalArgumentException("request terlalu besar");',
        'if (data.length > 9_000_000) throw new IllegalArgumentException("request terlalu besar");',
        "native request limit",
    )
    body = replace_once(
        body,
        '''            web.destroy();
        }
        io.shutdownNow();
''',
        '''            web.destroy();
            web = null;
        }
        io.shutdownNow();
''',
        "destroyed WebView guard",
    )
    body = replace_once(
        body,
        '''        String js = "window.FurinaHubNative&&window.FurinaHubNative.onMediaPicked(" + JSONObject.quote(payload.toString()) + ")";
        handler.post(() -> web.evaluateJavascript(js, null));
''',
        '''        String js = "window.FurinaHubNative&&window.FurinaHubNative.onMediaPicked(" + JSONObject.quote(payload.toString()) + ")";
        handler.post(() -> {
            if (web != null) web.evaluateJavascript(js, null);
        });
''',
        "media callback lifecycle",
    )
    body = replace_once(
        body,
        '''        @JavascriptInterface public void checkAppUpdate() {
            handler.post(() -> {
                appUpdateBusy = true;
''',
        '''        @JavascriptInterface public void checkAppUpdate() {
            handler.post(() -> {
                if (appUpdateBusy) return;
                appUpdateBusy = true;
''',
        "duplicate app update",
    )
    body = replace_once(
        body,
        '''        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK_ATTACHMENT''',
        '''        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_SAVE_IMAGE && resultCode != RESULT_OK) pendingImageSave = null;
        if (requestCode == REQ_PICK_ATTACHMENT''',
        "cancelled image save cleanup",
    )
    main_activity.write_text(body, encoding="utf-8")

    html = html_path.read_text(encoding="utf-8")
    html = replace_once(
        html,
        "if(result.mode==='plugin_confirmation')renderPluginConfirmation(result);else await refreshConversation()",
        "if(result.mode==='plugin_confirmation')renderPluginConfirmation(result);else if(result.mode==='device'&&result.job)renderJob(result.job);else await refreshConversation()",
        "device job rendering",
    )
    html = replace_once(
        html,
        "addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:''),null,attachment);const typing=addMsg('assistant','…');",
        "const pendingUser=addMsg('user',plain||(attachment?.kind==='text'?'File: '+attachment.name:''),null,attachment);const typing=addMsg('assistant','…');",
        "pending user message",
    )
    html = replace_once(
        html,
        "catch(e){typing.remove();addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}finally",
        "catch(e){typing.remove();pendingUser.remove();if(forcedText===undefined){input.value=plain;autoGrow(input);if(attachment){selectedAttachment=attachment;showAttachment()}}addMsg('assistant','Tidak bisa menghubungi Core: '+e.message)}finally",
        "restore failed chat input",
    )
    html = replace_once(
        html,
        "for(let i=0;i<180;i++){await new Promise(r=>setTimeout(r,800));",
        "for(let i=0;i<750;i++){await new Promise(r=>setTimeout(r,800));",
        "agent polling lifetime",
    )
    html = replace_once(
        html,
        "else history.forEach(x=>addMsg(String(x.role||x.kind||'assistant').includes('user')?'user':'assistant',x.content||x.text||'',x.id,x.attachment));}",
        "else history.forEach(x=>addMsg(String(x.role||x.kind||'assistant').includes('user')?'user':'assistant',x.content||x.text||'',x.id,x.attachment));(bootData.jobs||[]).forEach(renderJob);}",
        "restore active agent jobs",
    )
    html_path.write_text(html, encoding="utf-8")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10027", "versionCode 10028", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc27'", "versionName '1.0.0-rc28'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    checks = {
        main_activity: (
            "data.length > 9_000_000",
            "web = null;",
            "if (web != null) web.evaluateJavascript(js, null);",
            "if (appUpdateBusy) return;",
            "REQ_SAVE_IMAGE && resultCode != RESULT_OK) pendingImageSave = null;",
        ),
        html_path: (
            "result.mode==='device'&&result.job",
            "const pendingUser=addMsg",
            "pendingUser.remove();if(forcedText===undefined)",
            "for(let i=0;i<750;i++",
            "(bootData.jobs||[]).forEach(renderJob)",
        ),
        gradle: ("versionCode 10028", "versionName '1.0.0-rc28'"),
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"RC28 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_ANDROID_RC28_OK")


if __name__ == "__main__":
    main()
