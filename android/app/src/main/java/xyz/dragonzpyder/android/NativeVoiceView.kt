package xyz.dragonzpyder.android

import android.content.Context
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.ViewCompositionStrategy
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.*

/** Website-inspired orb, drawn natively. Animation is driven by provider
 * conversation state, not simulated microphone levels. */
class NativeVoiceView(context:Context, private val callbacks:Actions) {
    interface Actions {
        fun mute(muted:Boolean)
        fun end()
    }
    var status by mutableStateOf("Connecting…")
    private var muted by mutableStateOf(false)
    val view=ComposeView(context).apply{
        setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnDetachedFromWindowOrReleasedFromPool)
        setContent { Screen() }
    }

    @Composable private fun Screen(){
        val tokens=DragonDesignTokens.of(true)
        val ink=tokens.ink
        val warm=tokens.accent
        val inactive=status.contains("failed",true)||status.contains("ended",true)||status.contains("timed out",true)
        val active=(!muted&&!inactive&&(status.startsWith("Listening")||status.startsWith("Speaking")))
        DragonTheme(true){
            Column(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF171719),Color(0xFF0B0D11)))).systemBarsPadding().padding(horizontal=22.dp,vertical=14.dp),horizontalAlignment=Alignment.CenterHorizontally){
                Row(Modifier.fillMaxWidth().heightIn(min=52.dp),verticalAlignment=Alignment.CenterVertically){
                    Column(Modifier.weight(1f)){
                        Text("DragonZpyder",fontSize=18.sp,fontWeight=FontWeight.SemiBold,color=ink)
                        Text("Live voice",fontSize=12.sp,color=warm)
                    }
                    IconButton(onClick=callbacks::end,modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription="Close live voice"}){
                        NavigationGlyph("close",ink,26.dp)
                    }
                }
                Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.Center){
                    Orb(active,muted||inactive)
                }
                Text(if(muted&&!inactive)"Microphone muted" else status,modifier=Modifier.fillMaxWidth().semantics{liveRegion=LiveRegionMode.Polite},color=ink,fontSize=20.sp,textAlign=TextAlign.Center,fontWeight=FontWeight.Medium)
                Spacer(Modifier.height(8.dp))
                Text("Audio-only session · no external tool access",fontSize=12.sp,color=Color(0xFFB9B5B0),textAlign=TextAlign.Center)
                Spacer(Modifier.height(24.dp))
                Row(Modifier.fillMaxWidth().padding(bottom=12.dp),horizontalArrangement=Arrangement.Center,verticalAlignment=Alignment.CenterVertically){
                    Column(horizontalAlignment=Alignment.CenterHorizontally){
                        FilledTonalIconButton(onClick={muted=!muted;callbacks.mute(muted)},enabled=!inactive,modifier=Modifier.size(64.dp).semantics{contentDescription=if(muted)"Unmute microphone" else "Mute microphone"},shape=CircleShape){
                            NavigationGlyph("mic",if(muted)warm else ink,28.dp)
                        }
                        Spacer(Modifier.height(8.dp));Text(if(muted)"Unmute" else "Mute",fontSize=12.sp,color=ink)
                    }
                    Spacer(Modifier.width(28.dp))
                    Column(horizontalAlignment=Alignment.CenterHorizontally){
                        FilledIconButton(onClick=callbacks::end,modifier=Modifier.size(64.dp).semantics{contentDescription="End voice session"},colors=IconButtonDefaults.filledIconButtonColors(containerColor=Color(0xFFC44941),contentColor=Color.White),shape=CircleShape){
                            NavigationGlyph("close",Color.White,28.dp)
                        }
                        Spacer(Modifier.height(8.dp));Text("End",fontSize=12.sp,color=ink)
                    }
                }
            }
        }
    }

    @Composable private fun Orb(active:Boolean,dimmed:Boolean){
        val transition=rememberInfiniteTransition(label="orb")
        val phase by transition.animateFloat(0f,2f*PI.toFloat(),infiniteRepeatable(tween(4200,easing=LinearEasing)),label="orb rotation")
        val amplitude by animateFloatAsState(if(active)1f else .22f,tween(380),label="orb state")
        Canvas(Modifier.fillMaxWidth().widthIn(max=340.dp).aspectRatio(1f)){
            val c=center
            val radius=min(size.width,size.height)*.31f
            val opacity=if(dimmed).35f else 1f
            val pulse=radius*(1f+sin(phase*2)*.045f*amplitude)
            drawCircle(Brush.radialGradient(listOf(Color(0xFFEE8B56).copy(alpha=.20f*opacity),Color.Transparent),center=c,radius=pulse*1.62f),radius=pulse*1.62f,center=c)
            drawCircle(Brush.radialGradient(listOf(Color(0xFF71472F),Color(0xFF392F3A),Color(0xFF17191E)),center=c-Offset(radius*.3f,radius*.35f),radius=pulse*1.5f),radius=pulse,center=c,alpha=opacity)
            for(i in 0..11){
                val path=Path()
                val band=(i-5.5f)/6f
                for(k in 0..180){
                    val angle=k*2f*PI.toFloat()/180
                    val modulation=1f+.055f*amplitude*sin(angle*5+phase+i*.31f)
                    val x=c.x+cos(angle)*pulse*(.96f-.12f*abs(band))*modulation
                    val y=c.y+sin(angle)*pulse*(.25f+.58f*abs(band))*modulation+band*pulse*.22f
                    if(k==0)path.moveTo(x,y) else path.lineTo(x,y)
                }
                path.close()
                drawPath(path,if(i%3==0)Color(0xFFF6B58A).copy(alpha=.66f*opacity) else Color(0xFFBD795B).copy(alpha=.38f*opacity),style=Stroke(width=1.2.dp.toPx()))
            }
            drawCircle(Color(0xFFF4A470).copy(alpha=.7f*opacity),pulse,c,style=Stroke(1.3.dp.toPx()))
        }
    }
}
