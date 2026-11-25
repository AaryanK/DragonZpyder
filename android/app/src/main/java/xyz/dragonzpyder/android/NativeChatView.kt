package xyz.dragonzpyder.android

import android.content.Context
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.platform.ViewCompositionStrategy
import androidx.compose.ui.res.painterResource
import kotlinx.coroutines.launch
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Native chat presentation state. Existing Java host owns the authenticated API actions. */
class NativeChatView(context: Context, private val dark: Boolean, private val actions: Actions) {
    interface Actions {
        fun menu()
        fun commands()
        fun theme()
        fun account()
        fun add()
        fun mode()
        fun dictate()
        fun send()
        fun stop()
        fun removeAttachment()
        fun copy(value: String)
        fun speak(value: String)
    }

    data class Message(val role: String, val content: String)
    private val rows = mutableStateListOf<Message>()
    var draft by mutableStateOf("")
    var statusText by mutableStateOf("Personal agent")
    var busy by mutableStateOf(false)
    var streaming by mutableStateOf(false)
    var partialReply by mutableStateOf("")
    var modeLabel by mutableStateOf("Agent")
    var modelLabel by mutableStateOf("")
    var attachmentLabel by mutableStateOf("")
    var profileInitial by mutableStateOf("D")
    private val bg = if (dark) Color(0xFF0E0F11) else Color(0xFFFAF9F7)
    private val panel = if (dark) Color(0xFF242124) else Color.White
    private val ink = if (dark) Color(0xFFF6F4F1) else Color(0xFF24221F)
    private val muted = if (dark) Color(0xFFC2B8B0) else Color(0xFF70665F)
    private val line = if (dark) Color(0xFF665047) else Color(0xFFE1DAD2)
    private val accent = if (dark) Color(0xFFFF8A50) else Color(0xFFB94A21)
    private val userBubble = if (dark) Color(0xFF222922) else Color(0xFFEEEBE6)

    val view = ComposeView(context).apply {
        setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnDetachedFromWindow)
        setContent { Workspace() }
    }
    fun clearMessages() = rows.clear()
    fun append(role: String, content: String) { rows.add(Message(role, content)) }

    @Composable private fun Workspace() {
        MaterialTheme(colorScheme = if (dark) darkColorScheme(primary=accent,background=bg,surface=panel,onSurface=ink,onBackground=ink) else lightColorScheme(primary=accent,background=bg,surface=panel,onSurface=ink,onBackground=ink)) {
            Column(Modifier.fillMaxSize().background(bg)) {
                Row(Modifier.fillMaxWidth().heightIn(min=54.dp), verticalAlignment=Alignment.CenterVertically) {
                    ToolButton("menu", "Conversations", actions::menu)
                    Column(Modifier.weight(1f).padding(horizontal=6.dp)) {
                        Text("Personal",color=ink,fontWeight=FontWeight.SemiBold,fontSize=15.sp)
                        Text(statusText, color=muted,fontSize=11.sp,maxLines=2)
                    }
                    ToolButton("command","Commands",actions::commands)
                    ToolButton(if(dark) "sun" else "moon","Switch appearance",actions::theme)
                    IconButton(onClick=actions::account,enabled=!busy,modifier=Modifier.size(48.dp).semantics { contentDescription="Account" }) { Surface(shape=RoundedCornerShape(50),color=panel,border=BorderStroke(1.dp,line),modifier=Modifier.size(32.dp)) { Box(contentAlignment=Alignment.Center){Text(profileInitial,color=ink,fontWeight=FontWeight.Medium,fontSize=14.sp)} } }
                }
                HorizontalDivider(color=line.copy(alpha=.55f))
                Column(Modifier.weight(1f).fillMaxWidth(),horizontalAlignment=Alignment.CenterHorizontally) {
                    val state=rememberLazyListState()
                    val scope=rememberCoroutineScope()
                    var followLatest by remember { mutableStateOf(true) }
                    LaunchedEffect(state) {
                        snapshotFlow { state.isScrollInProgress to state.canScrollForward }.collect { (scrolling,hasMore) ->
                            if(scrolling)followLatest=!hasMore
                        }
                    }
                    LaunchedEffect(rows.size,busy,partialReply.length) {
                        if(followLatest && state.layoutInfo.totalItemsCount>0)
                            state.scrollToItem(state.layoutInfo.totalItemsCount-1)
                    }
                    LazyColumn(
                        state=state,
                        modifier=Modifier.widthIn(max=810.dp).fillMaxWidth().weight(1f),
                        contentPadding=PaddingValues(start=14.dp,end=14.dp,top=20.dp,bottom=40.dp),
                        verticalArrangement=Arrangement.spacedBy(18.dp)
                    ) {
                        if(rows.isEmpty())item { Welcome() }
                        items(rows){ message-> MessageRow(message) }
                        if(busy && rows.isNotEmpty())item {
                            Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
                                if(partialReply.isNotEmpty())MessageRow(Message("assistant",partialReply),ongoing=true)
                                Row(verticalAlignment=Alignment.CenterVertically){
                                    CircularProgressIndicator(Modifier.size(16.dp),strokeWidth=2.dp)
                                    Spacer(Modifier.width(10.dp))
                                    Text(statusText,color=muted,fontSize=13.sp)
                                }
                            }
                        }
                    }
                    if(!followLatest && rows.isNotEmpty() && state.canScrollForward)
                        OutlinedButton(
                            onClick={followLatest=true;scope.launch{state.animateScrollToItem((state.layoutInfo.totalItemsCount-1).coerceAtLeast(0))}},
                            modifier=Modifier.padding(bottom=5.dp).heightIn(min=40.dp),
                            colors=ButtonDefaults.outlinedButtonColors(containerColor=panel,contentColor=ink),
                            border=BorderStroke(1.dp,line)
                        ) { Text("↓ Latest messages",fontSize=12.sp) }
                }
                Box(Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=6.dp),contentAlignment=Alignment.Center) { Composer() }
            }
        }
    }
    @Composable private fun ToolButton(symbol:String,label:String,click:()->Unit) {
        IconButton(onClick=click,enabled=!busy,modifier=Modifier.sizeIn(minWidth=48.dp,minHeight=48.dp).semantics { contentDescription=label }) {
            Canvas(Modifier.size(21.dp)) {
                val w=size.width;val h=size.height;val stroke=1.7.dp.toPx()
                fun segment(x1:Float,y1:Float,x2:Float,y2:Float){drawLine(ink,Offset(x1*w,y1*h),Offset(x2*w,y2*h),stroke,StrokeCap.Round)}
                when(symbol){
                    "menu" -> {segment(.12f,.25f,.88f,.25f);segment(.12f,.5f,.72f,.5f);segment(.12f,.75f,.88f,.75f)}
                    "plus" -> {segment(.5f,.15f,.5f,.85f);segment(.15f,.5f,.85f,.5f)}
                    "mic" -> {drawRoundRect(ink,Offset(w*.36f,h*.08f),Size(w*.28f,h*.54f),androidx.compose.ui.geometry.CornerRadius(w*.14f),style=Stroke(stroke));drawArc(ink,0f,180f,false,Offset(w*.2f,h*.26f),Size(w*.6f,h*.5f),style=Stroke(stroke,cap=StrokeCap.Round));segment(.5f,.76f,.5f,.94f);segment(.34f,.94f,.66f,.94f)}
                    "sun" -> {drawCircle(ink,w*.22f,style=Stroke(stroke));for(k in 0..7){val a=k*Math.PI/4;val x=kotlin.math.cos(a).toFloat();val y=kotlin.math.sin(a).toFloat();segment(.5f+x*.34f,.5f+y*.34f,.5f+x*.46f,.5f+y*.46f)}}
                    "moon" -> {drawArc(ink,52f,258f,false,Offset(w*.15f,h*.09f),Size(w*.73f,h*.82f),style=Stroke(stroke,cap=StrokeCap.Round));drawArc(ink,80f,195f,false,Offset(w*.45f,h*.04f),Size(w*.48f,h*.70f),style=Stroke(stroke,cap=StrokeCap.Round))}
                    "command" -> {segment(.32f,.32f,.68f,.32f);segment(.32f,.68f,.68f,.68f);segment(.32f,.32f,.32f,.68f);segment(.68f,.32f,.68f,.68f);for(x in listOf(.22f,.78f))for(y in listOf(.22f,.78f))drawCircle(ink,w*.12f,Offset(w*x,h*y),style=Stroke(stroke))}
                }
            }
        }
    }
    @Composable private fun Welcome() {
        Column(Modifier.fillMaxWidth().padding(horizontal=10.dp,vertical=22.dp),horizontalAlignment=Alignment.CenterHorizontally) {
            Image(painterResource(R.drawable.brand_icon),"DragonZpyder",Modifier.size(56.dp));Spacer(Modifier.height(22.dp))
            Text("What shall we work on?",color=ink,fontSize=34.sp,lineHeight=39.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1.5).sp,textAlign=TextAlign.Center)
            Spacer(Modifier.height(12.dp))
            Text(if(modeLabel=="Agent") "From a quick question to a big idea. Start anywhere. We’ll find the way forward." else modelLabel,color=muted,fontSize=14.sp,lineHeight=22.sp,textAlign=TextAlign.Center,modifier=Modifier.widthIn(max=470.dp))
            Spacer(Modifier.height(24.dp))
            val prompts=listOf("Explore an idea" to "Help me think through a new idea.","Plan a project" to "Help me plan a project from scratch.","Write something" to "Help me turn my notes into a clear draft.")
            for((label,prompt) in prompts) {
                OutlinedButton(onClick={ draft=prompt },enabled=!busy,shape=RoundedCornerShape(24.dp),border=BorderStroke(1.dp,line),modifier=Modifier.heightIn(min=48.dp)) { Text(label,color=ink) }
                Spacer(Modifier.height(6.dp))
            }
        }
    }
    @Composable private fun MessageRow(message:Message,ongoing:Boolean=false) {
        val user=message.role=="user"
        if(message.role=="system"){Text(message.content,color=muted,fontSize=12.sp,lineHeight=18.sp,modifier=Modifier.fillMaxWidth().padding(vertical=4.dp));return}
        Column(Modifier.fillMaxWidth(),horizontalAlignment=if(user) Alignment.End else Alignment.Start) {
            if(!user) Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.padding(bottom=8.dp)){Image(painterResource(R.drawable.brand_icon),"DragonZpyder",Modifier.size(20.dp));Spacer(Modifier.width(7.dp));Text("DragonZpyder",fontSize=12.sp,fontWeight=FontWeight.Medium,color=muted)}
            if(user) {
                Surface(
                    color=userBubble,shape=RoundedCornerShape(18.dp),
                    modifier=Modifier.widthIn(max=620.dp)
                ) {
                    Box(Modifier.padding(horizontal=16.dp,vertical=13.dp)) {
                        SelectionContainer { Text(message.content,color=ink,fontSize=16.sp,lineHeight=24.sp,softWrap=true) }
                    }
                }
            } else {
                // Never clip assistant text against a rounded Surface edge.
                // Horizontal safe insets also preserve glyph overhang with scaled fonts.
                Box(Modifier.fillMaxWidth().padding(horizontal=12.dp,vertical=3.dp)) {
                    SelectionContainer { MarkdownBody(message.content,dark,actions::copy) }
                }
            }
            if(!user&&!ongoing) Row {
                TextButton(onClick={actions.copy(message.content)}){Text("Copy",color=muted,fontSize=12.sp)}
                TextButton(onClick={actions.speak(message.content)}){Text("Read aloud",color=muted,fontSize=12.sp)}
            }
        }
    }
    @Composable private fun Composer() {
        Surface(modifier=Modifier.widthIn(max=810.dp).fillMaxWidth(),shape=RoundedCornerShape(22.dp),color=panel,border=BorderStroke(1.dp,line),shadowElevation=0.dp) {
            Column(Modifier.padding(horizontal=9.dp,vertical=6.dp)) {
                BasicTextField(value=draft,onValueChange={draft=it},modifier=Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=9.dp).semantics { contentDescription="Message input"; testTag="message_input" },minLines=1,maxLines=5,textStyle=TextStyle(color=ink,fontSize=16.sp,lineHeight=23.sp),cursorBrush=SolidColor(accent),decorationBox={inner->Box{if(draft.isEmpty())Text("Ask anything, or give DragonZpyder a task…",color=muted,fontSize=14.sp,lineHeight=23.sp);inner()}})
                if(draft.length>(if(modeLabel=="AI Mesh") 5000 else 12000)) Text("Message exceeds this mode’s input limit. Shorten it before sending.",color=MaterialTheme.colorScheme.error,fontSize=12.sp,modifier=Modifier.padding(horizontal=8.dp))
                if(attachmentLabel.isNotBlank()) TextButton(onClick=actions::removeAttachment,enabled=!busy){Text("×  "+attachmentLabel)}
                Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()) {
                    ToolButton("plus","Attach",actions::add)
                    TextButton(onClick=actions::mode,enabled=!busy){Text("✦ "+modeLabel,color=ink)}
                    Spacer(Modifier.weight(1f))
                    ToolButton("mic","Dictate",actions::dictate)
                    Button(onClick={if(streaming)actions.stop() else actions.send()},enabled=streaming||(!busy&&draft.isNotBlank()&&draft.length<=(if(modeLabel=="AI Mesh") 5000 else 12000)),shape=RoundedCornerShape(50),contentPadding=PaddingValues(0.dp),modifier=Modifier.size(48.dp).semantics{contentDescription=if(streaming)"Stop response" else "Send message"},colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFB94A21),contentColor=Color.White,disabledContainerColor=line.copy(alpha=.35f),disabledContentColor=muted)) { Text(if(streaming)"■" else "↑",fontSize=23.sp) }
                }
            }
        }
    }
}
