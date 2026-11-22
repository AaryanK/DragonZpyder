package xyz.dragonzpyder.android;

import android.content.Context;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Exercises the real Android Keystore and single-use browser callback protection. */
@RunWith(AndroidJUnit4.class)
public final class MobileOAuthStoreTest {
    @Test public void validProofRedeemedOnceAndStoredEncrypted() throws Exception{
        Context app=ApplicationProvider.getApplicationContext();
        MobileOAuthStore store=new MobileOAuthStore(app);
        store.clear();
        String state=MobileOAuthStore.randomToken(),verifier=MobileOAuthStore.randomToken();
        store.begin(state,verifier);
        String ciphertext=app.getSharedPreferences("oauth_device_proof",Context.MODE_PRIVATE).getString("pending","");
        assertFalse(ciphertext.isEmpty());
        assertFalse(ciphertext.contains(verifier));
        assertFalse(ciphertext.contains(state));
        assertEquals(43,MobileOAuthStore.challenge(verifier).length());
        assertNull("Wrong state must be rejected",store.take(MobileOAuthStore.randomToken()));
        assertNull("Attempt must be erased after rejection",store.take(state));
        store.begin(state,verifier);
        String[] accepted=store.take(state);
        assertNotNull(accepted);
        assertEquals(state,accepted[0]);
        assertEquals(verifier,accepted[1]);
        assertNull("One-time verifier must not be reusable",store.take(state));
    }
}
