package com.wynndev.furina;

import android.app.Application;

/**
 * Application entry point. The JavaScript bridge is owned exclusively by MainActivity
 * so it cannot be attached twice or survive with a different lifecycle.
 */
public final class FurinaApplication extends Application {
    @Override public void onCreate() {
        super.onCreate();
    }
}
