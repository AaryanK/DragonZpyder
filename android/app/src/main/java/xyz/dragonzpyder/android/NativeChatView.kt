package xyz.dragonzpyder.android

import android.content.Context
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.contentDescription
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
        fun removeAttachment()
        fun copy(value: String)
        fun speak(value: String)
    }

    data class Message(val role: String, val content: String)
    private val rows = mutableStateListOf<Message>()
    var draft by mutableStateOf("")
    var statusText by mutableStateOf("Personal agent")
    var busy by mutableStateOf(false)
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
                Row(Modifier.fillMaxWidth().heightIn(min=58.dp), verticalAlignment=Alignment.CenterVertically) {
                    ToolButton("☰", "Conversations", actions::menu)
                    Column(Modifier.weight(1f).padding(horizontal=6.dp)) {
                        Text("Personal",fontWeight=FontWeight.SemiBold,fontSize=15.sp)
                        Text(statusText, color=muted,fontSize=11.sp,maxLines=2)
                    }
                    ToolButton("⌘","Commands",actions::commands)
                    ToolButton(if(dark) "☀" else "☾","Switch appearance",actions::theme)
                    ToolButton(profileInitial,"Account",actions::account)
                }
                HorizontalDivider(color=line.copy(alpha=.55f))
                Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.TopCenter) {
                    val state=rememberLazyListState()
                    LaunchedEffect(rows.size) { if(rows.isNotEmpty()) state.scrollToItem(rows.lastIndex) }
                    LazyColumn(state=state,modifier=Modifier.widthIn(max=810.dp).fillMaxWidth(),contentPadding=PaddingValues(horizontal=12.dp,vertical=24.dp),verticalArrangement=Arrangement.spacedBy(20.dp)) {
                        if(rows.isEmpty()) item { Welcome() }
                        items(rows) { message -> MessageRow(message) }
                        if(busy && rows.isNotEmpty()) item { Row(verticalAlignment=Alignment.CenterVertically){CircularProgressIndicator(Modifier.size(16.dp),strokeWidth=2.dp);Spacer(Modifier.width(10.dp));Text(statusText,color=muted,fontSize=13.sp)} }
                    }
                }
                Box(Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=6.dp),contentAlignment=Alignment.Center) { Composer() }
            }
        }
    }
    @Composable private fun ToolButton(symbol:String,label:String,click:()->Unit) {
        IconButton(onClick=click,enabled=!busy,modifier=Modifier.sizeIn(minWidth=48.dp,minHeight=48.dp).semantics { contentDescription=label }) {
            Text(symbol,modifier=Modifier.padding(4.dp),fontSize=20.sp,color=ink)
        }
    }
    @Composable private fun Welcome() {
        Column(Modifier.fillMaxWidth().padding(horizontal=10.dp,vertical=22.dp),horizontalAlignment=Alignment.CenterHorizontally) {
            Image(painterResource(R.drawable.brand_icon),"DragonZpyder",Modifier.size(56.dp))
            Spacer(Modifier.height(22.dp))
            Text("What shall we work on?",fontSize=34.sp,lineHeight=39.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1.5).sp,textAlign=TextAlign.Center)
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
    @Composable private fun MessageRow(message:Message) {
        val user=message.role=="user"
        Column(Modifier.fillMaxWidth(),horizontalAlignment=if(user) Alignment.End else Alignment.Start) {
            Text(if(user)"You" else "DragonZpyder",fontSize=11.sp,fontWeight=FontWeight.SemiBold,color=muted,modifier=Modifier.padding(bottom=6.dp))
            Surface(color=if(user)userBubble else bg,shape=RoundedCornerShape(18.dp),modifier=if(user) Modifier.widthIn(max=620.dp) else Modifier.fillMaxWidth()) {
                Column(Modifier.padding(if(user)14.dp else 2.dp)) {
                    SelectionContainer { RichText(message.content) }
                }
            }
            if(!user) Row {
                TextButton(onClick={actions.copy(message.content)}){Text("Copy",color=muted,fontSize=12.sp)}
                TextButton(onClick={actions.speak(message.content)}){Text("Read aloud",color=muted,fontSize=12.sp)}
            }
        }
    }
    @Composable private fun RichText(content:String) {
        // Native safe rendering: no HTML, JavaScript or automatic link actions.
        val blocks=remember(content){content.split("```")}
        Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
            blocks.forEachIndexed { index, block ->
                if(block.isNotEmpty()) {
                    if(index%2==1) Surface(shape=RoundedCornerShape(12.dp),color=panel,border=BorderStroke(1.dp,line)) {
                        Text(block.trim(),fontFamily=FontFamily.Monospace,fontSize=13.sp,lineHeight=20.sp,color=ink,modifier=Modifier.fillMaxWidth().padding(12.dp))
                    } else {
                        block.lines().forEach { paragraph ->
                            val level=paragraph.takeWhile{it=='#'}.length
                            if(level in 1..6 && paragraph.drop(level).startsWith(" ")) Text(paragraph.drop(level).trim(),fontWeight=FontWeight.SemiBold,fontSize=if(level<=2)21.sp else 17.sp,color=ink)
                            else Text(paragraph.replace(Regex("^[-*] "), "• "),fontSize=16.sp,lineHeight=25.sp,color=ink)
                        }
                    }
                }
            }
        }
    }
    @Composable private fun Composer() {
        Surface(modifier=Modifier.widthIn(max=810.dp).fillMaxWidth(),shape=RoundedCornerShape(19.dp),color=panel,border=BorderStroke(1.dp,line),shadowElevation=2.dp) {
            Column(Modifier.padding(9.dp)) {
                TextField(value=draft,onValueChange={draft=it.take(12000)},placeholder={Text("Ask anything, or give DragonZpyder a task…",color=muted,fontSize=14.sp)},modifier=Modifier.fillMaxWidth(),minLines=2,maxLines=5,
                    colors=TextFieldDefaults.colors(focusedContainerColor=Color.Transparent,unfocusedContainerColor=Color.Transparent,focusedIndicatorColor=Color.Transparent,unfocusedIndicatorColor=Color.Transparent))
                if(attachmentLabel.isNotBlank()) TextButton(onClick=actions::removeAttachment,enabled=!busy){Text("×  "+attachmentLabel)}
                Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()) {
                    ToolButton("＋","Attach",actions::add)
                    TextButton(onClick=actions::mode,enabled=!busy){Text("✦ "+modeLabel,color=ink)}
                    Spacer(Modifier.weight(1f))
                    ToolButton("◉","Dictate",actions::dictate)
                    Button(onClick=actions::send,enabled=!busy&&draft.isNotBlank(),shape=RoundedCornerShape(12.dp),contentPadding=PaddingValues(0.dp),modifier=Modifier.size(48.dp),colors=ButtonDefaults.buttonColors(containerColor=accent,contentColor=Color.White)) { Text("↑",fontSize=23.sp) }
                }
            }
        }
    }
}
