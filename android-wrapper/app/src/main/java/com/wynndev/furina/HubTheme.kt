package com.wynndev.furina

import androidx.activity.ComponentActivity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColors = lightColorScheme(
    primary = Color(0xFF235D9F), onPrimary = Color.White,
    primaryContainer = Color(0xFFDCEBFF), onPrimaryContainer = Color(0xFF123253),
    surface = Color(0xFFFAFCFF), background = Color(0xFFF3F7FC),
    surfaceVariant = Color(0xFFE7EDF5), onSurfaceVariant = Color(0xFF46576B),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFFA4CAFF), onPrimary = Color(0xFF10335D),
    primaryContainer = Color(0xFF203E62), onPrimaryContainer = Color(0xFFDCEBFF),
    surface = Color(0xFF111923), background = Color(0xFF0B121C),
    surfaceVariant = Color(0xFF263345), onSurfaceVariant = Color(0xFFC1CDDE),
)
@Composable internal fun FurinaHubTheme(mode: HubThemeMode, content: @Composable () -> Unit) {
    val dark = when(mode) { HubThemeMode.SYSTEM -> isSystemInDarkTheme(); HubThemeMode.DARK -> true; HubThemeMode.LIGHT -> false }
    val view = LocalView.current
    DisposableEffect(dark) {
        (view.context as? ComponentActivity)?.window?.let {
            WindowCompat.getInsetsController(it, view).apply {
                isAppearanceLightStatusBars = !dark; isAppearanceLightNavigationBars = !dark
            }
        }
        onDispose { }
    }
    MaterialTheme(colorScheme = if(dark) DarkColors else LightColors, content = content)
}

