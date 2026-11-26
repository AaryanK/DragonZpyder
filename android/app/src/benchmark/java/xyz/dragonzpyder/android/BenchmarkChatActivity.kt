package xyz.dragonzpyder.android

import android.os.Bundle
import androidx.activity.ComponentActivity

/** Benchmark-only synthetic messages, no accounts, no tools, no network. */
class BenchmarkChatActivity:ComponentActivity(){
    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        val ui=NativeChatView(this,false,object:NativeChatView.Actions{
            override fun menu(){}
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
            override fun openConversation(id:String){}
            override fun voice(){}
            override fun files(){}
            override fun saveArtifact(metadata:String){}
        })
        repeat(100){i->
            ui.append("user","Synthetic question "+i)
            ui.append("assistant","## Synthetic response "+i+"\n\nA deterministic paragraph for native rendering. **Bold text**, inline `code`, and a list:\n\n- First entry\n- Second entry")
        }
        setContentView(ui.view)
    }
}
