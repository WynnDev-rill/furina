package com.wynndev.furina

import android.app.Activity
import android.app.Application
import android.os.Bundle
import java.util.WeakHashMap

/** Keeps update checks outside MainActivity so the native shell stays focused on Furina UI/runtime. */
class FurinaApplication : Application(), Application.ActivityLifecycleCallbacks {
    private val updateManagers = WeakHashMap<MainActivity, UpdateManager>()

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(this)
    }

    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {
        if (activity !is MainActivity) return
        val manager = UpdateManager(activity)
        updateManagers[activity] = manager
        manager.register()
        manager.tryInstallPending()
        manager.checkForUpdate()
    }

    override fun onActivityResumed(activity: Activity) {
        if (activity is MainActivity) updateManagers[activity]?.tryInstallPending()
    }

    override fun onActivityDestroyed(activity: Activity) {
        if (activity is MainActivity) updateManagers.remove(activity)?.unregister()
    }

    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
}
