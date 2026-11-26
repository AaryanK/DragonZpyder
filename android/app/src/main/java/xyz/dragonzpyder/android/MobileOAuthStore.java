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
    private final String alias;
    private final byte[] aad;
    private final SharedPreferences prefs;
    MobileOAuthStore(Context context){this(context,false);}
    MobileOAuthStore(Context context,boolean mcp){
        alias=mcp?"dragonzpyder.android.mcp.oauth.pkce.v1":"dragonzpyder.android.oauth.pkce.v1";
        aad=(mcp?"dragonzpyder:mcp:oauth:device-v1":"dragonzpyder:discord:oauth:device-v1").getBytes(StandardCharsets.UTF_8);
        prefs=context.getApplicationContext().getSharedPreferences(mcp?"mcp_oauth_device_proof":"oauth_device_proof",Context.MODE_PRIVATE);
    }
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
        if(store.containsAlias(alias))return (SecretKey)store.getKey(alias,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setRandomizedEncryptionRequired(true).build());
        return generator.generateKey();
    }
    void begin(String state,String verifier) throws Exception {
        if(!state.matches("[A-Za-z0-9_-]{43,128}")||!verifier.matches("[A-Za-z0-9_-]{43,128}"))
            throw new IllegalArgumentException("Invalid device proof");
        long until=System.currentTimeMillis()+10*60*1000L;
        String data=state+"\n"+verifier+"\n"+until;
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());c.updateAAD(aad);
        byte[] cipher=c.doFinal(data.getBytes(StandardCharsets.UTF_8));
        String encoded=Base64.encodeToString(c.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher,Base64.NO_WRAP);
        if(!prefs.edit().putString("pending",encoded).commit())throw new IllegalStateException("Unable to store device proof");
    }
    synchronized String[] take(String returnedState){
        if(returnedState==null||!returnedState.matches("[A-Za-z0-9_-]{43,128}"))return null;
        String[] proof=peek();
        if(proof==null||!MessageDigest.isEqual(proof[0].getBytes(StandardCharsets.US_ASCII),returnedState.getBytes(StandardCharsets.US_ASCII)))return null;
        if(!prefs.edit().remove("pending").commit())return null;
        return proof;
    }
    synchronized String[] peek(){
        String saved=prefs.getString("pending","");
        if(saved.isEmpty())return null;
        try {
            String[] parts=saved.split(":",-1);
            if(parts.length!=2||saved.length()>2048)return null;
            byte[] iv=Base64.decode(parts[0],Base64.NO_WRAP);
            if(iv.length!=12)return null;
            Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,iv));c.updateAAD(aad);
            String[] decoded=new String(c.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),StandardCharsets.UTF_8).split("\n",-1);
            if(decoded.length!=3){clear();return null;}
            if(!decoded[0].matches("[A-Za-z0-9_-]{43,128}")||!decoded[1].matches("[A-Za-z0-9_-]{43,128}")){clear();return null;}
            long until=Long.parseLong(decoded[2]);long now=System.currentTimeMillis();
            if(until<=now||until>now+10*60*1000L){clear();return null;}
            return new String[]{decoded[0],decoded[1]};
        }catch(Exception e){clear();return null;}
    }
    void clear(){prefs.edit().remove("pending").commit();}
}
