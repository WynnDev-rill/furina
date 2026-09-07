package com.wynndev.furina

import android.app.Activity
import android.app.Application
import android.os.Bundle
import java.util.WeakHashMap

/** Keeps update checks outside MainActivity so the native shell stays focused on Furina UI/runtime. */
class FurinaApplication : Application(), Application.ActivityLifecycleCallbacks {
    private val updateManagers = WeakHashMap<Activity, UpdateManager>()

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(this)
    }

    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) {
        if (activity !is MainActivity && activity !is NativeHubActivity) return
        val manager = UpdateManager(activity)
        updateManagers[activity] = manager
        manager.register()
        manager.tryInstallPending()
        manager.checkForUpdate()
    }

    override fun onActivityResumed(activity: Activity) {
        updateManagers[activity]?.tryInstallPending()
    }

    override fun onActivityDestroyed(activity: Activity) {
        updateManagers.remove(activity)?.unregister()
    }

    override fun onActivityStarted(activity: Activity) = Unit
    fun checkUpdate(activity: Activity) { updateManagers[activity]?.checkForUpdate(manual = true) }
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
}
