package xyz.dragonzpyder.android;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class NativeChatStateTest {
    @Test public void mountsAndPreservesControlledDraft(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(activity->{
                NativeChatView ui=new NativeChatView(activity,false,new NativeChatView.Actions(){
                    public void menu(){} public void commands(){} public void theme(){} public void account(){}
                    public void add(){} public void mode(){} public void dictate(){} public void send(){} public void stop(){}
                    public void removeAttachment(){} public void copy(String value){} public void speak(String value){}
                    public void newChat(){} public void connections(){} public void tasks(){} public void approvals(){} public void openConversation(String id){} public void voice(){} public void files(){} public void saveArtifact(String metadata){}
                });
                activity.setContentView(ui.getView());
                ui.setDraft("Example draft");
                ui.setBusy(true);ui.setStreaming(true);ui.setPartialReply("Partial");assertTrue(ui.getStreaming());assertEquals("Partial",ui.getPartialReply());
                ui.append("user","Example message");
                ui.append("assistant","# Example response");
                assertEquals("Example draft",ui.getDraft());assertTrue(ui.getBusy());
                ui.clearMessages();ui.setPartialReply("");ui.setStreaming(false);ui.setBusy(false);assertFalse(ui.getBusy());
            });
            androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        }
    }
}
