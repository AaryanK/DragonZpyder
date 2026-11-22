package xyz.dragonzpyder.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.SecureRandom;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Separate encrypted, ten-minute PKCE device proof for a single Discord login attempt. */
final class MobileOAuthStore {
    static final String CALLBACK_SCHEME="dragonzpyder";
    private static final String ALIAS="dragonzpyder.android.oauth.pkce.v1";
    private static final byte[] AAD="dragonzpyder:discord:oauth:device-v1".getBytes(StandardCharsets.UTF_8);
    private final SharedPreferences prefs;
    MobileOAuthStore(Context context){prefs=context.getApplicationContext().getSharedPreferences("oauth_device_proof",Context.MODE_PRIVATE);}
    static String randomToken(){
        byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);
        return Base64.encodeToString(bytes,Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING);
    }
    static String challenge(String verifier) throws Exception{
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(verifier.getBytes(StandardCharsets.US_ASCII));
        return Base64.encodeToString(hash,Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING);
    }
    private SecretKey key() throws Exception{
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(store.containsAlias(ALIAS))return (SecretKey)store.getKey(ALIAS,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }
    void begin(String state,String verifier) throws Exception {
        if(!state.matches("[A-Za-z0-9_-]{43,128}")||!verifier.matches("[A-Za-z0-9_-]{43,128}"))
            throw new IllegalArgumentException("Invalid device proof");
        long until=System.currentTimeMillis()+10*60*1000L;
        String data=state+"\n"+verifier+"\n"+until;
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());c.updateAAD(AAD);
        byte[] cipher=c.doFinal(data.getBytes(StandardCharsets.UTF_8));
        String encoded=Base64.encodeToString(c.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher,Base64.NO_WRAP);
        if(!prefs.edit().putString("pending",encoded).commit())throw new IllegalStateException("Unable to store device proof");
    }
    String[] take(String returnedState){
        String saved=prefs.getString("pending","");
        clear();
        if(saved.isEmpty()||!returnedState.matches("[A-Za-z0-9_-]{43,128}"))return null;
        try {
            String[] parts=saved.split(":",-1);
            if(parts.length!=2||saved.length()>2048)return null;
            byte[] iv=Base64.decode(parts[0],Base64.NO_WRAP);
            if(iv.length!=12)return null;
            Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,iv));c.updateAAD(AAD);
            String[] decoded=new String(c.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),StandardCharsets.UTF_8).split("\n",-1);
            if(decoded.length!=3||!decoded[0].equals(returnedState))return null;
            long until=Long.parseLong(decoded[2]);long now=System.currentTimeMillis();
            if(until<=now||until>now+10*60*1000L)return null;
            return new String[]{decoded[0],decoded[1]};
        }catch(Exception e){return null;}
    }
    void clear(){prefs.edit().remove("pending").commit();}
}
