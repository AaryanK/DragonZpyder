package xyz.dragonzpyder.android

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** One 24x24 SVG-coordinate outline system, rendered as native Compose paths. */
@Composable internal fun NavigationGlyph(name:String,color:Color,size:Dp=24.dp) {
    val path=remember(name){
        PathParser().parsePathString(when(name){
            "menu" -> "M3 6H21 M3 12H17 M3 18H21"
            "new" -> "M12 5V19 M5 12H19"
            "close" -> "M6 6L18 18 M18 6L6 18"
            "search" -> "M11 3A8 8 0 1 0 11 19A8 8 0 1 0 11 3 M17 17L21 21"
            "connections" -> "M10 13A5 5 0 0 0 17 13L20 10A5 5 0 0 0 13 3L11 5 M14 11A5 5 0 0 0 7 11L4 14A5 5 0 0 0 11 21L13 19"
            "tasks" -> "M8 4H5V21H19V4H16 M8 2H16V6H8Z M8 12L10 14L14 10 M8 17H16"
            "approvals" -> "M12 3L21 7V12C21 17 17 21 12 23C7 21 3 17 3 12V7Z M8 12L11 15L16 10"
            "account" -> "M12 3A4 4 0 1 0 12 11A4 4 0 1 0 12 3 M4 21V19C4 15 8 13 12 13C16 13 20 15 20 19V21"
            "sun" -> "M12 7A5 5 0 1 0 12 17A5 5 0 1 0 12 7 M12 2V4 M12 20V22 M2 12H4 M20 12H22 M5 5L6.5 6.5 M17.5 17.5L19 19 M5 19L6.5 17.5 M17.5 6.5L19 5"
            "moon" -> "M20.5 15.5A9 9 0 0 1 8.5 3.5A9 9 0 1 0 20.5 15.5Z"
            "more" -> "M5 12H5.1 M12 12H12.1 M19 12H19.1"
            "voice" -> "M3 10V14 M7 6V18 M12 3V21 M17 6V18 M21 10V14"
            "mic" -> "M9 5A3 3 0 0 1 15 5V12A3 3 0 0 1 9 12Z M5 11V12A7 7 0 0 0 19 12V11 M12 19V22 M9 22H15"
            "attach" -> "M8 13L15 6A3 3 0 0 1 19 10L10 19A5 5 0 0 1 3 12L13 2"
            "copy" -> "M8 8H20V21H8Z M16 4H4V17"
            "speak" -> "M3 9H7L12 5V19L7 15H3Z M15 9C17 11 17 13 15 15 M18 6C22 9 22 15 18 18"
            "send" -> "M12 20V4 M5 11L12 4L19 11"
            "stop" -> "M6 6H18V18H6Z"
            else -> "M5 12H19"
        }).toPath()
    }
    Canvas(Modifier.size(size)){
        val factor=this.size.width/24f
        scale(factor,factor,pivot=Offset.Zero){
            drawPath(path,color,style=Stroke(width=if(name=="more") 3f else 1.8f,cap=StrokeCap.Round,join=StrokeJoin.Round))
        }
    }
}
