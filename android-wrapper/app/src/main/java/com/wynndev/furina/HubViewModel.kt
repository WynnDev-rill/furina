package com.wynndev.furina

import android.app.Application
import androidx.lifecycle.AndroidViewModel

/** Activity recreation does not close SQLite or cancel an in-flight answer. */
class HubViewModel(application: Application) : AndroidViewModel(application) {
    val controller = NativeHubController(application)
    override fun onCleared() { controller.close() }
}
