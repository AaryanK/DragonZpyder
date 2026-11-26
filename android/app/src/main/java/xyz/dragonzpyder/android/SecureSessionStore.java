package xyz.dragonzpyder.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Properties;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Stores only an authenticated cookie pair, encrypted by a non-exportable Android Keystore key. */
final class SecureSessionStore {
    private static final String ALIAS="dragonzpyder.personal.session.v1";
    private static final byte[] AAD="https://dragonzpyder.xyz|personal|session-v1".getBytes(StandardCharsets.UTF_8);
    private final SharedPreferences prefs;
    SecureSessionStore(Context context){prefs=context.getApplicationContext().getSharedPreferences("secure_personal_session",Context.MODE_PRIVATE);}
    private SecretKey key(boolean create) throws Exception{
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(ks.containsAlias(ALIAS))return (SecretKey)ks.getKey(ALIAS,null);
        if(!create)throw new IllegalStateException("Missing key");
        KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).setRandomizedEncryptionRequired(true).build());
        return gen.generateKey();
    }
    void save(Properties state){
        if(state.isEmpty()){clear();return;}
        try{
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();state.store(bytes,null);
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key(true));cipher.updateAAD(AAD);
            byte[] encrypted=cipher.doFinal(bytes.toByteArray());
            String value=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(encrypted,Base64.NO_WRAP);
            if(!prefs.edit().putString("ciphertext",value).commit())clear();
        }catch(Exception failure){clear();}
    }
    Properties read(){
        Properties p=new Properties();String value=prefs.getString("ciphertext","");
        if(value.isEmpty())return p;
        try{
            if(value.length()>32768)throw new IOException("Invalid stored session");
            String[] parts=value.split(":",-1);if(parts.length!=2)throw new IOException("Invalid session envelope");
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(false),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));cipher.updateAAD(AAD);
            p.load(new ByteArrayInputStream(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP))));return p;
        }catch(Exception failure){clear();return new Properties();}
    }
    void clear(){prefs.edit().remove("ciphertext").commit();}
}
