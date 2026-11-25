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
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
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
        fun newChat()
        fun connections()
        fun tasks()
        fun approvals()
        fun openConversation(id:String)
        fun voice()
    }

    data class Message(val role: String, val content: String)
    private val rows = mutableStateListOf<Message>()
    private data class Conversation(val id:String,val title:String)
    private var conversations by mutableStateOf(listOf<Conversation>())
    private var selectedConversation by mutableStateOf("")
    private var drawerRequest by mutableIntStateOf(0)
    private var historyError by mutableStateOf(false)
    var voiceAvailable by mutableStateOf(false)
    fun openDrawer(){drawerRequest++;historyError=false}
    fun setConversationHistory(history:org.json.JSONArray,selected:String){
        conversations=(0 until history.length()).mapNotNull{history.optJSONObject(it)?.let{row->
            val id=row.optString("id")
            if(id.isBlank())null else Conversation(id,row.optString("title").ifBlank{"Untitled conversation"})
        }}.distinctBy{it.id}
        selectedConversation=selected
    }
    fun markHistoryError(){historyError=true}
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
        setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnDetachedFromWindowOrReleasedFromPool)
        setContent { Workspace() }
    }
    fun clearMessages() = rows.clear()
    fun append(role: String, content: String) { rows.add(Message(role, content)) }

    @Composable private fun Workspace() {
        MaterialTheme(colorScheme = if (dark) darkColorScheme(primary=accent,background=bg,surface=panel,onSurface=ink,onBackground=ink) else lightColorScheme(primary=accent,background=bg,surface=panel,onSurface=ink,onBackground=ink)) {
            val drawer=rememberDrawerState(DrawerValue.Closed)
            val drawerScope=rememberCoroutineScope()
            LaunchedEffect(drawerRequest){if(drawerRequest>0)drawer.open()}
            ModalNavigationDrawer(drawerState=drawer,gesturesEnabled=false,drawerContent={
                ModalDrawerSheet(modifier=Modifier.widthIn(max=320.dp).fillMaxWidth(.88f),drawerContainerColor=bg,drawerContentColor=ink){
                    NavigationDrawerContent(close={drawerScope.launch{drawer.close()}},select={action->drawerScope.launch{drawer.close();action()}})
                }
            }){
            Column(Modifier.fillMaxSize().background(bg)) {
                Row(Modifier.fillMaxWidth().heightIn(min=58.dp).padding(horizontal=4.dp),verticalAlignment=Alignment.CenterVertically){
                    ToolButton("menu","Conversations",actions::menu)
                    Column(Modifier.weight(1f).padding(horizontal=6.dp)){
                        Text("DragonZpyder",color=ink,fontWeight=FontWeight.SemiBold,fontSize=17.sp,maxLines=1,overflow=TextOverflow.Ellipsis,modifier=Modifier.semantics{heading()})
                        Text(statusText,color=muted,fontSize=11.sp,maxLines=1,overflow=TextOverflow.Ellipsis,modifier=Modifier.semantics{liveRegion=LiveRegionMode.Polite})
                    }
                    ToolButton("new","New chat",actions::newChat)
                    ToolButton("more","More options",actions::commands)
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
                                    Text(statusText,color=muted,fontSize=13.sp,modifier=Modifier.semantics{liveRegion=LiveRegionMode.Polite})
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
    }
    @Composable private fun ToolButton(symbol:String,label:String,click:()->Unit) {
        IconButton(onClick=click,enabled=!busy,modifier=Modifier.size(48.dp).semantics{contentDescription=label}){
            NavigationGlyph(symbol,ink)
        }
    }
    @Composable private fun NavigationDrawerContent(close:()->Unit,select:(()->Unit)->Unit){
        var query by remember{mutableStateOf("")}
        val filtered=conversations.filter{it.title.contains(query.trim(),ignoreCase=true)}
        Column(Modifier.fillMaxSize().padding(horizontal=12.dp)){
            Row(Modifier.fillMaxWidth().heightIn(min=60.dp),verticalAlignment=Alignment.CenterVertically){
                Image(painterResource(R.drawable.brand_icon),null,Modifier.size(32.dp))
                Spacer(Modifier.width(10.dp))
                Text("DragonZpyder",color=ink,fontWeight=FontWeight.SemiBold,fontSize=17.sp,modifier=Modifier.weight(1f),maxLines=1,overflow=TextOverflow.Ellipsis)
                IconButton(onClick=close,modifier=Modifier.size(48.dp).semantics{contentDescription="Close menu"}){NavigationGlyph("close",muted)}
            }
            Button(onClick={select(actions::newChat)},enabled=!busy,shape=RoundedCornerShape(14.dp),modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),colors=ButtonDefaults.buttonColors(containerColor=accent,contentColor=if(dark)Color(0xFF17110D) else Color.White)){
                NavigationGlyph("new",if(dark)Color(0xFF17110D) else Color.White)
                Spacer(Modifier.width(10.dp));Text("New chat",fontWeight=FontWeight.Medium)
            }
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value=query,onValueChange={query=it},singleLine=true,placeholder={Text("Search conversations",fontSize=13.sp)},leadingIcon={NavigationGlyph("search",muted,22.dp)},modifier=Modifier.fillMaxWidth().semantics{contentDescription="Find conversations"},shape=RoundedCornerShape(14.dp),colors=OutlinedTextFieldDefaults.colors(unfocusedBorderColor=line,focusedBorderColor=accent))
            Spacer(Modifier.height(8.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth(),contentPadding=PaddingValues(top=2.dp,bottom=12.dp)){
                item{DrawerSection("Workspace")}
                item{DrawerRow("connections","Connections & tools",false){select(actions::connections)}}
                item{DrawerRow("tasks","Tasks",false){select(actions::tasks)}}
                item{DrawerRow("approvals","Approvals",false){select(actions::approvals)}}
                item{DrawerSection("Conversations")}
                if(historyError)item{Text("Could not refresh history",color=muted,fontSize=12.sp,modifier=Modifier.padding(10.dp))}
                if(filtered.isEmpty())item{Text(if(query.isBlank())"No conversations yet" else "No matching conversations",color=muted,fontSize=13.sp,modifier=Modifier.padding(10.dp))}
                items(filtered,key={it.id}){item->
                    NavigationDrawerItem(label={Text(item.title,maxLines=2,overflow=TextOverflow.Ellipsis,fontSize=14.sp,lineHeight=19.sp)},selected=item.id==selectedConversation,onClick={if(!busy)select{actions.openConversation(item.id)}},shape=RoundedCornerShape(10.dp),modifier=Modifier.heightIn(min=48.dp),colors=NavigationDrawerItemDefaults.colors(selectedContainerColor=userBubble,unselectedContainerColor=Color.Transparent,selectedTextColor=ink,unselectedTextColor=ink))
                }
                item{DrawerSection("Preferences")}
                item{DrawerRow("account","Account & security",false){select(actions::account)}}
                item{DrawerRow(if(dark)"sun" else "moon",if(dark)"Light appearance" else "Dark appearance",false){select(actions::theme)}}
                item{DrawerRow("more","All commands",false){select(actions::commands)}}
            }
        }
    }
    @Composable private fun DrawerSection(title:String){
        Text(title,color=muted,fontSize=11.sp,fontWeight=FontWeight.SemiBold,modifier=Modifier.padding(start=12.dp,top=14.dp,bottom=6.dp).semantics{heading()})
    }
    @Composable private fun DrawerRow(icon:String,label:String,selected:Boolean,click:()->Unit){
        NavigationDrawerItem(label={Text(label,fontSize=14.sp,maxLines=2,overflow=TextOverflow.Ellipsis)},selected=selected,onClick={if(!busy)click()},icon={NavigationGlyph(icon,ink)},shape=RoundedCornerShape(10.dp),modifier=Modifier.heightIn(min=48.dp),colors=NavigationDrawerItemDefaults.colors(selectedContainerColor=userBubble,unselectedContainerColor=Color.Transparent,selectedTextColor=ink,unselectedTextColor=ink))
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
        if(message.role=="receipt"){
            var expanded by remember(message.content){mutableStateOf(false)}
            OutlinedCard(Modifier.fillMaxWidth()){
                Column(Modifier.padding(12.dp)){
                    TextButton(onClick={expanded=!expanded},modifier=Modifier.heightIn(min=48.dp)){Text(if(expanded)"Hide execution receipt" else "View execution receipt")}
                    if(expanded)SelectionContainer{Text(message.content,color=ink,fontSize=13.sp,lineHeight=20.sp)}
                }
            }
            return
        }
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
                IconButton(onClick={actions.copy(message.content)},modifier=Modifier.semantics{contentDescription="Copy"}){NavigationGlyph("copy",muted,22.dp)}
                IconButton(onClick={actions.speak(message.content)},modifier=Modifier.semantics{contentDescription="Read aloud"}){NavigationGlyph("speak",muted,22.dp)}
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
                    ToolButton("attach","Attach",actions::add)
                    TextButton(onClick=actions::mode,enabled=!busy){Text(modeLabel,color=ink)}
                    Spacer(Modifier.weight(1f))
                    ToolButton("mic","Dictate",actions::dictate)
                    if(voiceAvailable&&!busy&&draft.isBlank()&&attachmentLabel.isBlank()) ToolButton("voice","Live voice",actions::voice) else Button(onClick={if(streaming)actions.stop() else actions.send()},enabled=streaming||(!busy&&(draft.isNotBlank()||(modeLabel=="AI Mesh"&&attachmentLabel.isNotBlank()))&&draft.length<=(if(modeLabel=="AI Mesh") 5000 else 12000)),shape=RoundedCornerShape(50),contentPadding=PaddingValues(0.dp),modifier=Modifier.size(48.dp).semantics{contentDescription=if(streaming)"Stop response" else "Send message"},colors=ButtonDefaults.buttonColors(containerColor=Color(0xFFB94A21),contentColor=Color.White,disabledContainerColor=line.copy(alpha=.35f),disabledContentColor=muted)) { NavigationGlyph(if(streaming)"stop" else "send",if(streaming||draft.isNotBlank()||attachmentLabel.isNotBlank())Color.White else muted) }
                }
            }
        }
    }
}
