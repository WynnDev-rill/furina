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
    secondary = Color(0xFF4C607A), onSecondary = Color.White,
    secondaryContainer = Color(0xFFDCE7F5), onSecondaryContainer = Color(0xFF182E48),
    surface = Color(0xFFFAFCFF), background = Color(0xFFF3F7FC),
    onSurface = Color(0xFF182331), onBackground = Color(0xFF182331),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF1F5FB),
    surfaceContainer = Color(0xFFEBF0F7), surfaceContainerHigh = Color(0xFFE5EBF3),
    surfaceContainerHighest = Color(0xFFDEE6EF), surfaceTint = Color(0xFF235D9F),
    surfaceVariant = Color(0xFFE7EDF5), onSurfaceVariant = Color(0xFF46576B),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFFA4CAFF), onPrimary = Color(0xFF10335D),
    primaryContainer = Color(0xFF203E62), onPrimaryContainer = Color(0xFFDCEBFF),
    secondary = Color(0xFFB5C9E2), onSecondary = Color(0xFF20354E),
    secondaryContainer = Color(0xFF344A65), onSecondaryContainer = Color(0xFFDCE7F5),
    surface = Color(0xFF111923), background = Color(0xFF0B121C),
    onSurface = Color(0xFFE1E8F2), onBackground = Color(0xFFE1E8F2),
    surfaceContainerLowest = Color(0xFF080F18), surfaceContainerLow = Color(0xFF151F2C),
    surfaceContainer = Color(0xFF1A2635), surfaceContainerHigh = Color(0xFF233142),
    surfaceContainerHighest = Color(0xFF2D3C4F), surfaceTint = Color(0xFFA4CAFF),
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
