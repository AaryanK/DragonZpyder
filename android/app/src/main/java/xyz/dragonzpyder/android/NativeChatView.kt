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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
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
        fun files()
        fun saveArtifact(metadata:String)
    }

    data class Message(val role: String, val content: String)
    private val rows = mutableStateListOf<Message>()
    private val presentation=ChatPresentationState()
    private var commands by mutableStateOf<List<CommandItem>?>(null)
    fun showCommands(names:Array<String>,icons:Array<String>,actions:Array<Runnable>){
        require(names.size==icons.size&&names.size==actions.size)
        commands=names.indices.map{CommandItem(names[it],icons[it],actions[it])}
    }
    private data class Conversation(val id:String,val title:String)
    private var conversations by mutableStateOf(listOf<Conversation>())
    private var selectedConversation by mutableStateOf("")
    private var drawerRequest by mutableIntStateOf(0)
    private var historyError by mutableStateOf(false)
    var voiceAvailable:Boolean
        get()=presentation.snapshot.voiceAvailable
        set(value){presentation.update{it.copy(voiceAvailable=value)}}
    var filesAvailable:Boolean
        get()=presentation.snapshot.filesAvailable
        set(value){presentation.update{it.copy(filesAvailable=value)}}
    var goalsAvailable:Boolean
        get()=presentation.snapshot.goalsAvailable
        set(value){presentation.update{it.copy(goalsAvailable=value)}}
    var legacyActionsAvailable:Boolean
        get()=presentation.snapshot.legacyActionsAvailable
        set(value){presentation.update{it.copy(legacyActionsAvailable=value)}}
    // Optional execution authority is explicit and one-turn only.
    fun setExecutionCapabilities(computer:Boolean,media:Boolean,durable:Boolean){
        presentation.update{it.copy(computerAvailable=computer,mediaAvailable=media,durableAvailable=durable,
            allowComputer=computer&&it.allowComputer,allowMedia=media&&it.allowMedia,allowDurable=durable&&it.allowDurable)}
    }
    fun clearExecutionConsent(){presentation.update{it.copy(allowComputer=false,allowMedia=false,allowDurable=false)}}
    fun allowsComputer()=presentation.snapshot.computerAvailable&&presentation.snapshot.allowComputer
    fun allowsMedia()=presentation.snapshot.mediaAvailable&&presentation.snapshot.allowMedia
    fun allowsDurable()=presentation.snapshot.durableAvailable&&presentation.snapshot.allowDurable
    fun openDrawer(){drawerRequest++;historyError=false}
    fun setConversationHistory(history:org.json.JSONArray,selected:String){
        conversations=(0 until history.length()).mapNotNull{history.optJSONObject(it)?.let{row->
            val id=row.optString("id")
            if(id.isBlank())null else Conversation(id,row.optString("title").ifBlank{"Untitled conversation"})
        }}.distinctBy{it.id}
        selectedConversation=selected
    }
    fun markHistoryError(){historyError=true}
    var draft:String
        get()=presentation.snapshot.draft
        set(value){presentation.update{it.copy(draft=value)}}
    var statusText:String
        get()=presentation.snapshot.statusText
        set(value){presentation.update{it.copy(statusText=value)}}
    var busy:Boolean
        get()=presentation.snapshot.busy
        set(value){presentation.update{it.copy(busy=value)}}
    var streaming:Boolean
        get()=presentation.snapshot.streaming
        set(value){presentation.update{it.copy(streaming=value)}}
    var partialReply:String
        get()=presentation.snapshot.partialReply
        set(value){presentation.update{it.copy(partialReply=value)}}
    var modeLabel:String
        get()=presentation.snapshot.modeLabel
        set(value){presentation.update{it.copy(modeLabel=value)}}
    var modelLabel:String
        get()=presentation.snapshot.modelLabel
        set(value){presentation.update{it.copy(modelLabel=value)}}
    var attachmentLabel:String
        get()=presentation.snapshot.attachmentLabel
        set(value){presentation.update{it.copy(attachmentLabel=value)}}
    var profileInitial:String
        get()=presentation.snapshot.profileInitial
        set(value){presentation.update{it.copy(profileInitial=value)}}
    var profileName by mutableStateOf("")
    var profilePhoto by mutableStateOf<android.graphics.Bitmap?>(null)
    private val tokens=DragonDesignTokens.of(dark)
    private val bg=tokens.background
    private val panel=tokens.surface
    private val ink=tokens.ink
    private val muted=tokens.muted
    private val line=tokens.divider
    private val accent=tokens.accent
    private val userBubble=tokens.bubble

    val view = ComposeView(context).apply {
        setViewCompositionStrategy(ViewCompositionStrategy.DisposeOnDetachedFromWindowOrReleasedFromPool)
        setContent { Workspace() }
    }
    fun clearMessages() = rows.clear()
    fun append(role: String, content: String) { rows.add(Message(role, content)) }

    @Composable private fun Workspace() {
        DragonTheme(dark) {
            commands?.let{NativeCommandPalette(it,dark){commands=null}}
            val drawer=rememberDrawerState(DrawerValue.Closed)
            val drawerScope=rememberCoroutineScope()
            LaunchedEffect(drawerRequest){if(drawerRequest>0)drawer.open()}
            ModalNavigationDrawer(drawerState=drawer,gesturesEnabled=!busy,drawerContent={
                ModalDrawerSheet(drawerState=drawer,modifier=Modifier.widthIn(max=320.dp).fillMaxWidth(.88f),drawerContainerColor=bg,drawerContentColor=ink){
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
                        modifier=Modifier.widthIn(max=DragonSizes.contentMax).fillMaxWidth().weight(1f),
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
        IconButton(onClick=click,enabled=!busy,modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription=label}){
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
                IconButton(onClick=close,modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription="Close menu"}){NavigationGlyph("close",muted)}
            }
            Button(onClick={select(actions::newChat)},enabled=!busy,shape=RoundedCornerShape(8.dp),modifier=Modifier.fillMaxWidth().heightIn(min=DragonSizes.touch),border=BorderStroke(1.dp,line),colors=ButtonDefaults.buttonColors(containerColor=tokens.bubble,contentColor=ink)){
                NavigationGlyph("new",ink)
                Spacer(Modifier.width(10.dp));Text("New chat",fontWeight=FontWeight.Medium)
            }
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value=query,onValueChange={query=it},singleLine=true,placeholder={Text("Search chats",fontSize=13.sp)},leadingIcon={NavigationGlyph("search",muted,22.dp)},modifier=Modifier.fillMaxWidth().semantics{contentDescription="Find conversations"},shape=RoundedCornerShape(14.dp),colors=OutlinedTextFieldDefaults.colors(unfocusedBorderColor=tokens.outline,focusedBorderColor=accent))
            Spacer(Modifier.height(8.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth(),contentPadding=PaddingValues(top=2.dp,bottom=12.dp)){
                item{DrawerRow("connections","Connections & tools",false){select(actions::connections)}}
                if(filesAvailable)item{DrawerRow("attach","Your files",false){select(actions::files)}}
                if(goalsAvailable)item{DrawerRow("tasks","Tasks",false){select(actions::tasks)}}
                if(legacyActionsAvailable)item{DrawerRow("approvals","Approvals",false){select(actions::approvals)}}
                item{DrawerSection("Chats")}
                if(historyError)item{Text("Could not refresh history",color=muted,fontSize=12.sp,modifier=Modifier.padding(10.dp))}
                if(filtered.isEmpty())item{Text(if(historyError)"History unavailable" else if(query.isBlank())"No conversations yet" else "No matching conversations",color=muted,fontSize=13.sp,modifier=Modifier.padding(10.dp))}
                items(filtered,key={it.id}){item->
                    DragonNavigationRow(item.title,null,dark,selected=item.id==selectedConversation,enabled=!busy){select{actions.openConversation(item.id)}}
                }

            }
            HorizontalDivider(color=line.copy(alpha=.55f))
            Row(Modifier.fillMaxWidth().heightIn(min=52.dp),verticalAlignment=Alignment.CenterVertically){
                val photo=profilePhoto
                Box(Modifier.size(36.dp).clip(CircleShape).background(panel),contentAlignment=Alignment.Center){
                    if(photo!=null)Image(photo.asImageBitmap(),null,Modifier.fillMaxSize(),contentScale=ContentScale.Crop)
                    else Text(profileInitial,color=ink,fontSize=12.sp,fontWeight=FontWeight.SemiBold)
                }
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)){
                    if(profileName.isNotBlank())Text(profileName,color=ink,fontSize=12.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
                    DragonNavigationRow("Settings",null,dark,enabled=!busy){select(actions::account)}
                }
                IconButton(onClick={select(actions::theme)},enabled=!busy,modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription="Switch appearance"}){NavigationGlyph(if(dark)"sun" else "moon",ink)}

            }
        }
    }
    @Composable private fun DrawerSection(title:String){
        Text(title,color=muted,fontSize=11.sp,fontWeight=FontWeight.SemiBold,modifier=Modifier.padding(start=12.dp,top=14.dp,bottom=6.dp).semantics{heading()})
    }
    @Composable private fun DrawerRow(icon:String,label:String,selected:Boolean,click:()->Unit){
        DragonNavigationRow(label,icon,dark,selected=selected,enabled=!busy,onClick=click)
    }
    @Composable private fun Welcome() {
        Column(Modifier.fillMaxWidth().padding(horizontal=10.dp,vertical=22.dp),horizontalAlignment=Alignment.CenterHorizontally) {
            Image(painterResource(R.drawable.brand_icon),"DragonZpyder",Modifier.size(56.dp));Spacer(Modifier.height(22.dp))
            Text("What shall we work on?",color=ink,fontSize=29.sp,lineHeight=35.sp,fontWeight=FontWeight.SemiBold,letterSpacing=(-1.0).sp,textAlign=TextAlign.Center)
            Spacer(Modifier.height(12.dp))
            Text(if(modeLabel=="Agent") "Ask a question or give DragonZpyder a task." else modelLabel,color=muted,fontSize=14.sp,lineHeight=22.sp,textAlign=TextAlign.Center,modifier=Modifier.widthIn(max=470.dp))
            Spacer(Modifier.height(24.dp))
            val prompts=listOf("Explore an idea" to "Help me think through a new idea.","Plan a project" to "Help me plan a project from scratch.","Write something" to "Help me turn my notes into a clear draft.")
            for((label,prompt) in prompts) {
                OutlinedButton(onClick={ draft=prompt },enabled=!busy,shape=RoundedCornerShape(10.dp),border=BorderStroke(1.dp,line),modifier=Modifier.heightIn(min=DragonSizes.touch)) { Text(label,color=ink) }
                Spacer(Modifier.height(6.dp))
            }
        }
    }
    @Composable private fun MessageRow(message:Message,ongoing:Boolean=false) {
        val user=message.role=="user"
        if(message.role=="artifact"){
            val file=remember(message.content){runCatching{org.json.JSONObject(message.content)}.getOrNull()}
            if(file!=null)OutlinedCard(Modifier.fillMaxWidth()){
                Row(Modifier.fillMaxWidth().padding(12.dp),verticalAlignment=Alignment.CenterVertically){
                    NavigationGlyph("attach",accent,26.dp);Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)){
                        Text(file.optString("filename","Generated file"),fontWeight=FontWeight.Medium,maxLines=2,overflow=TextOverflow.Ellipsis)
                        Text("${maxOf(1,(file.optInt("size")+1023)/1024)} KB · Generated file",fontSize=12.sp,color=muted)
                    }
                    TextButton(onClick={actions.saveArtifact(message.content)},enabled=!busy&&filesAvailable){Text("Save")}
                }
            }
            return
        }
        if(message.role=="receipt"){
            var expanded by remember(message.content){mutableStateOf(false)}
            OutlinedCard(Modifier.fillMaxWidth()){
                Column(Modifier.padding(12.dp)){
                    TextButton(onClick={expanded=!expanded},modifier=Modifier.heightIn(min=DragonSizes.touch)){Text(if(expanded)"Hide execution receipt" else "View execution receipt")}
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
    @Composable private fun ExecutionOptions(){
        val options=presentation.snapshot
        if(!options.computerAvailable&&!options.mediaAvailable&&!options.durableAvailable)return
        var open by remember{mutableStateOf(false)}
        val count=listOf(allowsComputer(),allowsMedia(),allowsDurable()).count{it}
        TextButton(onClick={open=true},enabled=!busy,modifier=Modifier.heightIn(min=DragonSizes.touch)){
            Text(if(count==0)"Tools" else "Tools · "+count,color=if(count>0)accent else ink)
        }
        if(open)AlertDialog(onDismissRequest={open=false},title={Text("Tools for this message")},text={
            Column{
                Text("Choose optional capabilities for the next message only. Server permissions and approvals still apply.",fontSize=13.sp)
                if(options.computerAvailable)Row(verticalAlignment=Alignment.CenterVertically){Checkbox(checked=options.allowComputer,onCheckedChange={v->presentation.update{it.copy(allowComputer=v)}});Text("Use isolated computer")}
                if(options.mediaAvailable)Row(verticalAlignment=Alignment.CenterVertically){Checkbox(checked=options.allowMedia,onCheckedChange={v->presentation.update{it.copy(allowMedia=v)}});Text("Use media tools")}
                if(options.durableAvailable)Row(verticalAlignment=Alignment.CenterVertically){Checkbox(checked=options.allowDurable,onCheckedChange={v->presentation.update{it.copy(allowDurable=v)}});Text("Allow scheduled work")}
            }
        },confirmButton={TextButton(onClick={open=false}){Text("Done")}},dismissButton={TextButton(onClick={clearExecutionConsent();open=false}){Text("Clear")}})
    }
    @Composable private fun Composer() {
        Surface(modifier=Modifier.widthIn(max=DragonSizes.contentMax).fillMaxWidth(),shape=RoundedCornerShape(22.dp),color=panel,border=BorderStroke(1.dp,line),shadowElevation=0.dp) {
            Column(Modifier.padding(horizontal=9.dp,vertical=6.dp)) {
                BasicTextField(value=draft,onValueChange={draft=it},modifier=Modifier.fillMaxWidth().padding(horizontal=8.dp,vertical=9.dp).semantics { contentDescription="Message input"; testTag="message_input" },minLines=1,maxLines=5,textStyle=TextStyle(color=ink,fontSize=16.sp,lineHeight=23.sp),cursorBrush=SolidColor(accent),decorationBox={inner->Box{if(draft.isEmpty())Text("Ask anything, or give DragonZpyder a task…",color=muted,fontSize=14.sp,lineHeight=23.sp);inner()}})
                if(draft.length>(if(modeLabel=="AI Mesh") 5000 else 12000)) Text("Message exceeds this mode’s input limit. Shorten it before sending.",color=MaterialTheme.colorScheme.error,fontSize=12.sp,modifier=Modifier.padding(horizontal=8.dp))
                if(attachmentLabel.isNotBlank()) TextButton(onClick=actions::removeAttachment,enabled=!busy){Text("×  "+attachmentLabel)}
                BoxWithConstraints(Modifier.fillMaxWidth()){
                val compact=maxWidth<300.dp||LocalDensity.current.fontScale>=1.5f
                Column {
                if(compact&&legacyActionsAvailable)TextButton(onClick=actions::mode,enabled=!busy,modifier=Modifier.heightIn(min=DragonSizes.touch)){Text(modeLabel,color=ink)}
                Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()) {
                    ToolButton("attach","Attach",actions::add)
                    if(!compact&&legacyActionsAvailable)TextButton(onClick=actions::mode,enabled=!busy){Text(modeLabel,color=ink)}
                    if(!legacyActionsAvailable)ExecutionOptions()
                    Spacer(Modifier.weight(1f))
                    ToolButton("mic","Dictate",actions::dictate)
                    if(voiceAvailable&&!busy&&draft.isBlank()&&attachmentLabel.isBlank()) ToolButton("voice","Live voice",actions::voice) else Button(onClick={if(streaming)actions.stop() else actions.send()},enabled=streaming||(!busy&&(draft.isNotBlank()||((modeLabel=="AI Mesh"||filesAvailable)&&attachmentLabel.isNotBlank()))&&draft.length<=(if(modeLabel=="AI Mesh") 5000 else 12000)),shape=RoundedCornerShape(50),contentPadding=PaddingValues(0.dp),modifier=Modifier.size(DragonSizes.touch).semantics{contentDescription=if(streaming)"Stop response" else "Send message"},colors=ButtonDefaults.buttonColors(containerColor=accent,contentColor=tokens.onAccent,disabledContainerColor=line.copy(alpha=.35f),disabledContentColor=muted)) { NavigationGlyph(if(streaming)"stop" else "send",if(streaming||draft.isNotBlank()||attachmentLabel.isNotBlank())tokens.onAccent else muted) }
                }
                }
                }
            }
        }
    }
}
