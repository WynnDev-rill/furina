package com.wynndev.furina;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;

import java.util.Map;
import java.util.WeakHashMap;

public final class FurinaApplication extends Application implements Application.ActivityLifecycleCallbacks {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<Activity, OfflineAiBridge> bridges = new WeakHashMap<>();

    @Override public void onCreate() {
        super.onCreate();
        registerActivityLifecycleCallbacks(this);
    }

    @Override public void onActivityResumed(Activity activity) {
        if (!(activity instanceof MainActivity) || bridges.containsKey(activity)) return;
        installWhenReady(activity, 0);
    }

    private void installWhenReady(Activity activity, int attempt) {
        if (activity.isFinishing() || activity.isDestroyed() || bridges.containsKey(activity)) return;
        WebView webView = findWebView(activity.getWindow().getDecorView());
        if (webView != null) {
            OfflineAiBridge bridge = new OfflineAiBridge(activity, webView);
            webView.addJavascriptInterface(bridge, "FurinaNative");
            bridges.put(activity, bridge);
            return;
        }
        if (attempt < 120) handler.postDelayed(() -> installWhenReady(activity, attempt + 1), 500);
    }

    private WebView findWebView(View view) {
        if (view instanceof WebView) return (WebView) view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView result = findWebView(group.getChildAt(i));
                if (result != null) return result;
            }
        }
        return null;
    }

    @Override public void onActivityDestroyed(Activity activity) {
        OfflineAiBridge bridge = bridges.remove(activity);
        if (bridge != null) bridge.destroy();
    }

    @Override public void onActivityCreated(Activity activity, Bundle state) {}
    @Override public void onActivityStarted(Activity activity) {}
    @Override public void onActivityPaused(Activity activity) {}
    @Override public void onActivityStopped(Activity activity) {}
    @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) {}
}
