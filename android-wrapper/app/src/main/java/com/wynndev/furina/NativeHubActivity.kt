package com.wynndev.furina

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue

class NativeHubActivity : ComponentActivity() {
    private lateinit var controller: NativeHubController
    private val model: HubViewModel by viewModels()
    private var pendingTraining = false

    private val runCommandPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            if (pendingTraining) controller.openTrainingRoom(this) else controller.connectTermux(this)
        } else controller.permissionDenied()
        pendingTraining = false
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        controller = model.controller
        pendingTraining = savedInstanceState?.getBoolean("pending_training", false) ?: false
        setContent {
            val state by controller.state.collectAsStateWithLifecycle()
            FurinaHubTheme(state.themeMode) {
                FurinaHubApp(
                    controller = controller,
                    onConnect = {
                        pendingTraining = false
                        if (controller.canRunTermux()) controller.connectTermux(this)
                        else runCommandPermission.launch(TermuxBridgeClient.RUN_COMMAND_PERMISSION)
                    },
                    onTraining = {
                        pendingTraining = true
                        if (controller.canRunTermux()) controller.openTrainingRoom(this)
                        else runCommandPermission.launch(TermuxBridgeClient.RUN_COMMAND_PERMISSION)
                    },
                    onDownload = { modelId ->
                        if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        controller.downloadAndroidModel(modelId)
                    },
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::controller.isInitialized) controller.refresh()
    }

    override fun onStop() { controller.flushDraft(); super.onStop() }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean("pending_training", pendingTraining)
        super.onSaveInstanceState(outState)
    }
}
