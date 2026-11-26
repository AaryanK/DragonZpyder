package xyz.dragonzpyder.android

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/** Consistent leading icon column; text can wrap at large font scales. */
@Composable internal fun DragonNavigationRow(
    label:String, icon:String?, dark:Boolean, selected:Boolean=false,
    enabled:Boolean=true, onClick:()->Unit
){
    val t=DragonDesignTokens.of(dark)
    Surface(
        onClick=onClick, enabled=enabled,
        color=if(selected)t.bubble else androidx.compose.ui.graphics.Color.Transparent,
        contentColor=if(enabled)t.ink else t.muted,
        shape=RoundedCornerShape(10.dp),
        modifier=Modifier.fillMaxWidth().heightIn(min=DragonSizes.touch).semantics{
            if(selected)this.selected=true
        }
    ){
        Row(Modifier.padding(horizontal=12.dp,vertical=10.dp),verticalAlignment=Alignment.CenterVertically){
            if(icon!=null){
                Box(Modifier.width(32.dp),contentAlignment=Alignment.CenterStart){
                    NavigationGlyph(icon,if(enabled)t.ink else t.muted,DragonSizes.icon)
                }
                Spacer(Modifier.width(12.dp))
            }
            Text(label,style=MaterialTheme.typography.bodyMedium,
                fontWeight=if(selected)FontWeight.SemiBold else FontWeight.Normal,
                maxLines=3,overflow=TextOverflow.Ellipsis,modifier=Modifier.weight(1f))
        }
    }
}
