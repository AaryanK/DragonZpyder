package xyz.dragonzpyder.android;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.UUID;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class PendingAgentRequestStoreTest {
    @Test public void markerSurvivesNewStoreAndIsBoundToOriginalSession(){
        Context context=ApplicationProvider.getApplicationContext();
        String first="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",second="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",id=UUID.randomUUID().toString();
        PendingAgentRequestStore original=new PendingAgentRequestStore(context);
        assertTrue(original.save(first,id));
        try{
            PendingAgentRequestStore restored=new PendingAgentRequestStore(context);
            assertEquals(id,restored.read(first));
            assertEquals("",restored.read(second));
            assertFalse(restored.clear(second,id));
            assertFalse(restored.clear(first,UUID.randomUUID().toString()));
            assertFalse(restored.save(first,"not-a-uuid"));
            assertFalse(restored.save("invalid-binding",id));
            assertEquals(id,restored.read(first));
        }finally{assertTrue(original.clear(first,id));}
        assertEquals("",new PendingAgentRequestStore(context).read(first));
    }
}
