package xyz.dragonzpyder.android;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import static org.junit.Assert.*;

/** Account transitions must not retain data from a previously signed-in user. */
@RunWith(AndroidJUnit4.class)
public final class AccountIsolationTest {
    private static Field field(String name) throws Exception {
        Field f=MainActivity.class.getDeclaredField(name);
        f.setAccessible(true);
        return f;
    }
    @Test public void resetClearsPriorAccountDataAndPendingActions(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(activity->{
                try {
                    for(String key:new String[]{"conversation","pendingPrompt","lastAnswer","model","authEmail","challengeId","restoredDraft","restoredConversation","attachmentName","transcriptionModel"})
                        field(key).set(activity,"previous-user");
                    field("profileInitial").set(activity,"X");
                    field("history").set(activity,new JSONArray().put("private-history"));
                    field("meshMessages").set(activity,new JSONArray().put("private-chat"));
                    field("restorePending").setBoolean(activity,true);
                    field("interruptedRequest").setBoolean(activity,true);
                    field("meshMode").setBoolean(activity,true);
                    Method reset=MainActivity.class.getDeclaredMethod("clearAccountView");
                    reset.setAccessible(true);reset.invoke(activity);
                    for(String key:new String[]{"conversation","pendingPrompt","lastAnswer","model","authEmail","challengeId","restoredDraft","restoredConversation","attachmentName","transcriptionModel"})
                        assertEquals(key,"",field(key).get(activity));
                    assertEquals("D",field("profileInitial").get(activity));
                    assertEquals(0,((JSONArray)field("history").get(activity)).length());
                    assertEquals(0,((JSONArray)field("meshMessages").get(activity)).length());
                    assertFalse(field("restorePending").getBoolean(activity));
                    assertFalse(field("interruptedRequest").getBoolean(activity));
                    assertFalse(field("meshMode").getBoolean(activity));
                    assertNull(field("chatUi").get(activity));
                } catch(Exception e){throw new AssertionError(e);}
            });
        }
    }
}
