package xyz.dragonzpyder.android

import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf

/** UI-only state; neither API credentials nor Activities are held here.
 * All mutations occur on the UI thread. This bridge preserves the Java host
 * during migration to feature ViewModels. */
internal data class ChatScreenState(
    val draft:String="",
    val statusText:String="Personal agent",
    val busy:Boolean=false,
    val streaming:Boolean=false,
    val partialReply:String="",
    val modeLabel:String="Agent",
    val modelLabel:String="",
    val attachmentLabel:String="",
    val profileInitial:String="D",
    val voiceAvailable:Boolean=false,
    val filesAvailable:Boolean=false
)
internal class ChatPresentationState {
    var snapshot by mutableStateOf(ChatScreenState())
        private set
    fun update(reduce:(ChatScreenState)->ChatScreenState){snapshot=reduce(snapshot)}
}
