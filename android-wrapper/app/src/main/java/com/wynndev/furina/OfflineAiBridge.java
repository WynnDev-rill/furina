package com.wynndev.furina;

import android.app.Activity;
import android.content.Intent;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONObject;

public final class OfflineAiBridge {
    private final Activity activity;
    private final WebView webView;
    private final OfflineModelEngine engine;

    public OfflineAiBridge(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        this.engine = new OfflineModelEngine(activity);
    }

    @JavascriptInterface
    public String getStatus() {
        try {
            String modelId = engine.activeModelId();
            JSONObject result = new JSONObject();
            result.put("activeModelId", modelId);
            result.put("installed", !modelId.isEmpty() && engine.isInstalled(modelId));
            result.put("busy", engine.isBusy());
            result.put("supportsImage", false);
            return result.toString();
        } catch (Exception e) {
            return "{\"installed\":false,\"busy\":false}";
        }
    }

    @JavascriptInterface
    public void openModelManager() {
        activity.runOnUiThread(() -> activity.startActivity(new Intent(activity, ModelManagerActivity.class)));
    }

    @JavascriptInterface
    public void cancelGeneration() {
        engine.cancel();
    }

    @JavascriptInterface
    public void generate(String requestJson) {
        String requestId = "offline";
        try {
            requestId = new JSONObject(requestJson).optString("requestId", "offline");
        } catch (Exception ignored) {}
        final String id = requestId;

        engine.generate(requestJson, new OfflineModelEngine.Callback() {
            @Override public void onToken(String token) {
                dispatch("furina-native-token", id, token, null);
            }

            @Override public void onComplete() {
                dispatch("furina-native-complete", id, "", null);
            }

            @Override public void onError(String message) {
                dispatch("furina-native-error", id, "", message);
            }
        });
    }

    private void dispatch(String event, String requestId, String token, String error) {
        activity.runOnUiThread(() -> {
            try {
                JSONObject detail = new JSONObject();
                detail.put("requestId", requestId);
                if (!token.isEmpty()) detail.put("token", token);
                if (error != null) detail.put("error", error);
                String script = "window.dispatchEvent(new CustomEvent(" + JSONObject.quote(event) + "," +
                    "{detail:" + detail.toString() + "}));";
                webView.evaluateJavascript(script, null);
            } catch (Exception ignored) {}
        });
    }

    public void destroy() {
        engine.shutdown();
    }
}
