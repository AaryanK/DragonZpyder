package xyz.dragonzpyder.android

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Shared brand palette for Compose and the transitional Java host. */
class DragonDesignTokens private constructor(val dark:Boolean) {
    val background=if(dark)Color(0xFF0E0F11) else Color(0xFFFAF9F7)
    val surface=if(dark)Color(0xFF242124) else Color.White
    val ink=if(dark)Color(0xFFF6F4F1) else Color(0xFF24221F)
    val muted=if(dark)Color(0xFFC2B8B0) else Color(0xFF70665F)
    val accent=if(dark)Color(0xFFFF8A50) else Color(0xFFA83F1B)
    val onAccent=if(dark)Color(0xFF17110D) else Color.White
    val outline=if(dark)Color(0xFF89766F) else Color(0xFF92867D)
    val divider=if(dark)Color(0xFF665047) else Color(0xFFE1DAD2)
    val sidebar=if(dark)Color(0xFF141416) else Color(0xFFF3F1EE)
    val chip=if(dark)Color(0xFF1A191C) else Color(0xFFF6F3EF)
    val bubble=if(dark)Color(0xFF222922) else Color(0xFFEEEBE6)
    val code=if(dark)Color(0xFF353034) else Color(0xFFECE7E2)
    val danger=if(dark)Color(0xFFFFB4AB) else Color(0xFFB3261E)
    fun legacyColors():IntArray=intArrayOf(background,surface,ink,muted,accent,divider,sidebar,chip,bubble,surface).map{it.toArgb()}.toIntArray()
    companion object {
        private val lightTokens=DragonDesignTokens(false)
        private val darkTokens=DragonDesignTokens(true)
        @JvmStatic fun of(dark:Boolean)=if(dark)darkTokens else lightTokens
    }
}
internal object DragonSizes {
    val touch=48.dp
    val icon=24.dp
    val compactGap=8.dp
    val gap=16.dp
    val contentMax=810.dp
    val body=16.sp
    val bodyLine=24.sp
}
@Composable internal fun DragonTheme(dark:Boolean,content:@Composable ()->Unit){
    val t=DragonDesignTokens.of(dark)
    val scheme=if(dark)darkColorScheme(primary=t.accent,onPrimary=t.onAccent,background=t.background,surface=t.surface,onSurface=t.ink,onBackground=t.ink,onSurfaceVariant=t.muted,outline=t.outline,outlineVariant=t.divider,error=t.danger)
        else lightColorScheme(primary=t.accent,onPrimary=t.onAccent,background=t.background,surface=t.surface,onSurface=t.ink,onBackground=t.ink,onSurfaceVariant=t.muted,outline=t.outline,outlineVariant=t.divider,error=t.danger)
    MaterialTheme(colorScheme=scheme,content=content)
}
