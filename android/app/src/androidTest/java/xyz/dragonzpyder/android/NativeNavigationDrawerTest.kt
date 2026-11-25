package xyz.dragonzpyder.android

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.viewinterop.AndroidView
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NativeNavigationDrawerTest {
    @get:Rule val compose=createComposeRule()

    @Test fun drawerSearchOpensOnlyTheSelectedConversation(){
        var opened=""
        lateinit var ui:NativeChatView
        compose.setContent {
            AndroidView(factory={context->
                ui=NativeChatView(context,false,object:NativeChatView.Actions{
                    override fun menu(){ui.openDrawer()}
                    override fun commands(){}
                    override fun theme(){}
                    override fun account(){}
                    override fun add(){}
                    override fun mode(){}
                    override fun dictate(){}
                    override fun send(){}
                    override fun stop(){}
                    override fun removeAttachment(){}
                    override fun copy(value:String){}
                    override fun speak(value:String){}
                    override fun newChat(){}
                    override fun connections(){}
                    override fun tasks(){}
                    override fun approvals(){}
                    override fun openConversation(id:String){opened=id}
                    override fun voice(){}
                })
                ui.setConversationHistory(JSONArray().put(JSONObject().put("id","one").put("title","Physics research")).put(JSONObject().put("id","two").put("title","Travel planning")),"one")
                ui.view
            })
        }
        compose.onNodeWithContentDescription("Conversations").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Connections & tools").assertExists()
        compose.onNodeWithContentDescription("Find conversations").performTextInput("Travel")
        compose.onNodeWithText("Physics research").assertDoesNotExist()
        compose.onNodeWithText("Travel planning").performClick()
        compose.waitForIdle()
        compose.runOnIdle{assertEquals("two",opened)}
    }
}
