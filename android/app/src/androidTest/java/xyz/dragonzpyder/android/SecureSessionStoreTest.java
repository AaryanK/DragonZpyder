package xyz.dragonzpyder.android;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.Properties;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class SecureSessionStoreTest {
    @Test public void storesCiphertextAndClears() {
        Context context=ApplicationProvider.getApplicationContext();
        SecureSessionStore store=new SecureSessionStore(context);
        store.clear();
        try{
            Properties input=new Properties();
            input.setProperty("__Host-operly_session","dummy-session-12345");
            input.setProperty("__Host-operly_csrf","dummy-csrf-67890");
            long until=System.currentTimeMillis()+60000;
            input.setProperty("__Host-operly_session.expiry",Long.toString(until));
            input.setProperty("__Host-operly_csrf.expiry",Long.toString(until));
            store.save(input);
            String stored=context.getSharedPreferences("secure_personal_session",Context.MODE_PRIVATE).getString("ciphertext","");
            assertFalse(stored.isEmpty());
            assertFalse(stored.contains("dummy-session-12345"));
            assertFalse(stored.contains("dummy-csrf-67890"));
            assertEquals(input,new SecureSessionStore(context).read());
            store.clear();
            assertTrue(new SecureSessionStore(context).read().isEmpty());
        }finally{store.clear();}
    }
}
