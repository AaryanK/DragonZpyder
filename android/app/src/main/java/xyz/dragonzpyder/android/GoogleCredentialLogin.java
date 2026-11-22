package xyz.dragonzpyder.android;

import android.app.Activity;
import android.os.CancellationSignal;
import androidx.annotation.NonNull;
import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.GetCredentialException;
import com.google.android.libraries.identity.googleid.GetGoogleIdOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;
import java.util.concurrent.Executor;
import java.util.function.Consumer;

/** Native Credential Manager Google sign-in. Google token is transient, never persisted. */
final class GoogleCredentialLogin {
    private GoogleCredentialLogin(){}
    static void start(Activity activity,String webClientId,String nonce,
                      Executor callbackExecutor,Consumer<String> success,Consumer<String> error){
        if(webClientId==null||webClientId.isEmpty()||nonce==null||nonce.isEmpty()){
            error.accept("Google login is not configured.");return;
        }
        try{
            GetGoogleIdOption option=new GetGoogleIdOption.Builder()
                .setFilterByAuthorizedAccounts(false)
                .setServerClientId(webClientId)
                .setNonce(nonce)
                .build();
            GetCredentialRequest request=new GetCredentialRequest.Builder()
                .addCredentialOption(option).build();
            CredentialManager.create(activity).getCredentialAsync(
                activity,request,new CancellationSignal(),callbackExecutor,
                new CredentialManagerCallback<GetCredentialResponse,GetCredentialException>(){
                    @Override public void onResult(@NonNull GetCredentialResponse result){
                        Credential credential=result.getCredential();
                        if(!(credential instanceof CustomCredential)||
                            !GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType())){
                            error.accept("Google returned an unsupported sign-in method.");return;
                        }
                        try{
                            GoogleIdTokenCredential token=GoogleIdTokenCredential.createFrom(((CustomCredential)credential).getData());
                            String value=token.getIdToken();
                            if(value==null||value.isEmpty())throw new IllegalArgumentException("No ID token");
                            success.accept(value);
                        }catch(RuntimeException e){
                            error.accept("Google sign-in could not be verified.");
                        }
                    }
                    @Override public void onError(@NonNull GetCredentialException exception){
                        error.accept("Google sign-in was cancelled or is unavailable on this device.");
                    }
                }
            );
        }catch(RuntimeException e){error.accept("Google sign-in is unavailable on this device.");}
    }
}
