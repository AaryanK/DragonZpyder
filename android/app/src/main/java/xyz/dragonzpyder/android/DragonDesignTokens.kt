package xyz.dragonzpyder.android

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Shared web V2 semantic palette for Compose and the transitional Java host.
 * prepare-brand.sh checks the cross-client tokens. Control outlines retain
 * their separately tested higher contrast; native targets remain 48dp. */
class DragonDesignTokens private constructor(val dark:Boolean) {
    val background=if(dark)Color(0xFF141415) else Color(0xFFFAFAF9)
    val surface=if(dark)Color(0xFF1D1D20) else Color(0xFFFFFFFF)
    val ink=if(dark)Color(0xFFF4F3F1) else Color(0xFF202022)
    val muted=if(dark)Color(0xFFA1A1AA) else Color(0xFF64646B)
    val accent=if(dark)Color(0xFFEE814D) else Color(0xFFB8431B)
    val onAccent=if(dark)Color(0xFF1B130E) else Color(0xFFFFFFFF)
    val outline=if(dark)Color(0xFF89766F) else Color(0xFF92867D)
    val divider=if(dark)Color(0xFF38383D) else Color(0xFFDCDCD9)
    val sidebar=if(dark)Color(0xFF141415) else Color(0xFFFAFAF9)
    val chip=if(dark)Color(0xFF1D1D20) else Color(0xFFFFFFFF)
    val bubble=if(dark)Color(0xFF27272A) else Color(0xFFF0F0EE)
    val code=if(dark)Color(0xFF27272A) else Color(0xFFF0F0EE)
    val danger=if(dark)Color(0xFFFFB4AB) else Color(0xFFB3261E)
    fun legacyColors():IntArray=listOf(background,surface,ink,muted,accent,divider,sidebar,chip,bubble,surface).map{it.toArgb()}.toIntArray()
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
