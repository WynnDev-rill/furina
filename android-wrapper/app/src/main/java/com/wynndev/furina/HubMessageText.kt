package com.wynndev.furina

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Native readable message formatting; no WebView/HTML execution or remote image fetches. */
@Composable
internal fun HubMessageText(content: String) {
    val parts = remember(content) { content.split("```") }
    Column {
        parts.forEachIndexed { index, part ->
            if (index % 2 == 1) {
                val code = part.substringAfter('\n', part).trimEnd()
                Text(code, Modifier.background(MaterialTheme.colorScheme.surfaceVariant).horizontalScroll(rememberScrollState()).padding(10.dp), fontFamily = FontFamily.Monospace, fontSize = 13.sp)
            } else {
                val formatted = remember(part) {
                    buildAnnotatedString {
                        val pattern = Regex("\\*\\*(.+?)\\*\\*|`([^`]+)`|(?<!\\*)\\*([^*\n]+)\\*(?!\\*)")
                        var start = 0
                        for (match in pattern.findAll(part)) {
                            append(part.substring(start, match.range.first))
                            when {
                                match.groups[1] != null -> withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(match.groupValues[1]) }
                                match.groups[2] != null -> withStyle(SpanStyle(fontFamily = FontFamily.Monospace)) { append(match.groupValues[2]) }
                                else -> withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(match.groupValues[3]) }
                            }
                            start = match.range.last + 1
                        }
                        append(part.substring(start))
                    }
                }
                Text(formatted, style = MaterialTheme.typography.bodyLarge, lineHeight = 24.sp)
            }
        }
    }
}
