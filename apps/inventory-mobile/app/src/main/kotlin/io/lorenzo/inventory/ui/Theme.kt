package io.lorenzo.inventory.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import io.lorenzo.inventory.R

val Geist = FontFamily(Font(R.font.geist))
val Newsreader = FontFamily(Font(R.font.newsreader))
private val Light =
    lightColorScheme(
        primary = Color(0xFF1769C2),
        onPrimary = Color.White,
        primaryContainer = Color(0xFFDCEBFA),
        onPrimaryContainer = Color(0xFF08131F),
        secondary = Color(0xFF7B2638),
        tertiary = Color(0xFF775A24),
        background = Color(0xFFFBFAF7),
        onBackground = Color(0xFF08131F),
        surface = Color(0xFFFBFAF7),
        onSurface = Color(0xFF08131F),
        surfaceVariant = Color(0xFFF4EFE5),
        onSurfaceVariant = Color(0xFF4B5967),
        surfaceContainer = Color(0xFFF4EFE5),
        outline = Color(0xFF78838C),
    )
private val Dark =
    darkColorScheme(
        primary = Color(0xFF86BEF7),
        onPrimary = Color(0xFF08131F),
        primaryContainer = Color(0xFF123E68),
        onPrimaryContainer = Color(0xFFDCEBFA),
        secondary = Color(0xFFE7A5B3),
        tertiary = Color(0xFFD9B675),
        background = Color(0xFF08131F),
        onBackground = Color(0xFFF4EFE5),
        surface = Color(0xFF08131F),
        onSurface = Color(0xFFF4EFE5),
        surfaceVariant = Color(0xFF182633),
        onSurfaceVariant = Color(0xFFBAC5D0),
        surfaceContainer = Color(0xFF13212E),
        outline = Color(0xFF8795A3),
    )

@Composable
fun LorenzoTheme(content: @Composable () -> Unit) {
    val base = Typography()
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) Dark else Light,
        typography =
            Typography(
                displaySmall =
                    TextStyle(fontFamily = Newsreader, fontSize = 36.sp, lineHeight = 42.sp),
                headlineLarge =
                    TextStyle(fontFamily = Newsreader, fontSize = 32.sp, lineHeight = 38.sp),
                headlineMedium =
                    TextStyle(fontFamily = Newsreader, fontSize = 28.sp, lineHeight = 34.sp),
                titleLarge =
                    base.titleLarge.copy(fontFamily = Geist, fontWeight = FontWeight.SemiBold),
                titleMedium =
                    base.titleMedium.copy(fontFamily = Geist, fontWeight = FontWeight.Medium),
                bodyLarge = base.bodyLarge.copy(fontFamily = Geist),
                bodyMedium = base.bodyMedium.copy(fontFamily = Geist),
                bodySmall = base.bodySmall.copy(fontFamily = Geist),
                labelLarge = base.labelLarge.copy(fontFamily = Geist),
                labelMedium = base.labelMedium.copy(fontFamily = Geist),
            ),
        content = content,
    )
}
