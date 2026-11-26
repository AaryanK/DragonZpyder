package xyz.dragonzpyder.android;

import android.app.*;
import android.os.Bundle;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

public final class MainActivity extends androidx.activity.ComponentActivity {
    private int BG, PANEL, TEXT, MUTED, ACCENT, LINE, SIDEBAR, CHIP, USER, COMPOSER;
    private boolean dark;
    private final ArrayList<String[]> transcript=new ArrayList<>();
    private void palette(){
        int[] colors=DragonDesignTokens.of(dark).legacyColors();
        BG=colors[0];PANEL=colors[1];TEXT=colors[2];MUTED=colors[3];ACCENT=colors[4];
        LINE=colors[5];SIDEBAR=colors[6];CHIP=colors[7];USER=colors[8];COMPOSER=colors[9];
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }
    private void toggleTheme(){
        dark=!dark;
        getPreferences(MODE_PRIVATE).edit().putBoolean("dark",dark).apply();palette();
        if(signedIn){if(accountOpen)showAccount();else chatScreen();}else authScreen(authMode,"");
    }
    private NativeChatView chatUi;
    private AgentRequestViewModel agentRequests;
    private String activeRequestId="";
    private PendingAgentRequestStore pendingAgentStore;
    private static final DragonApi api=new DragonApi();
    private AgentFileRepository fileRepository;
    private NativeVoiceSession nativeVoice;
    private android.app.Dialog voiceDialog;
    private boolean voiceStartOnResume;
    private boolean voicePermissionPending;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private LinearLayout root;
    private TextView status;
    private JSONObject attachment;
    private JSONObject pendingFileDownload;
    private String attachmentName="";
    private java.io.File cameraCapture;
    private String conversation="", lastAnswer="", pendingPrompt="";
    // Non-sensitive Activity recreation state; never persist auth tokens or replay a request.
    private String restoredConversation="", restoredDraft="";
    private boolean restorePending=false;
    private boolean interruptedRequest=false;
    private JSONArray history=new JSONArray();
    private boolean busy, signedIn, meshMode;
    private String model="";
    private boolean modelAcceptsImages;
    private boolean restoredMesh;
    private String restoredModel="";
    private boolean restoredModelAcceptsImages;
    private JSONArray meshMessages=new JSONArray();
    private final LinkedHashSet<String> selectedMcpConnections=new LinkedHashSet<>();
    private TextToSpeech tts;
    private boolean speechReady;
    interface Work { Object run() throws Exception; }
    interface Done { void accept(Object result) throws Exception; }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        agentRequests=new androidx.lifecycle.ViewModelProvider(this).get(AgentRequestViewModel.class);
        pendingAgentStore=new PendingAgentRequestStore(getApplicationContext());
        fileRepository=new AgentFileRepository(getApplicationContext().getContentResolver(),api);
        mobileOAuth=new MobileOAuthStore(getApplicationContext());mcpOAuth=new MobileOAuthStore(getApplicationContext(),true);
        if(b!=null){
            restoredConversation=b.getString("dz.conversation","");
            restoredDraft=b.getString("dz.draft","");
            restorePending=true;
            interruptedRequest=b.getBoolean("dz.request_in_flight",false);
            activeRequestId=b.getString("dz.request_id","");
            restoredMesh=b.getBoolean("dz.mesh",false);restoredModel=b.getString("dz.model","");restoredModelAcceptsImages=b.getBoolean("dz.model_images",false);
        }
        dark=getPreferences(MODE_PRIVATE).getBoolean("dark",false);palette();
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        tts=new TextToSpeech(this, code -> speechReady=code==TextToSpeech.SUCCESS);
        loginScreen("");
        agentRequests.outcomes().observe(this,outcome->{if(signedIn)handleAgentOutcome(outcome);});
        submit("Checking secure session…",()->api.restore(getApplicationContext()),result->{
            if(Boolean.TRUE.equals(result)){signedIn=true;String savedRequest=pendingAgentStore.read(api.pendingRequestBinding());if(!savedRequest.isEmpty()){activeRequestId=savedRequest;interruptedRequest=true;restorePending=true;}else{activeRequestId="";}if(!api.isFirstParty()&&restorePending&&restoredMesh&&!restoredModel.isEmpty()){meshMode=true;model=restoredModel;modelAcceptsImages=restoredModelAcceptsImages;chatScreen();applyRestoredDraft();append("system","Android recreated this screen. Previous AI Mesh context and attachments were not saved; this is a new model conversation.");loadHistory(false);}else{chatScreen();if(restorePending&&chatUi!=null)chatUi.setDraft(restoredDraft);if(!activeRequestId.isEmpty()){AgentRequestViewModel.Outcome retained=agentRequests.current();if(retained!=null&&activeRequestId.equals(retained.id))handleAgentOutcome(retained);else checkAgentRequest();}else loadHistory(true);}}
            else {activeRequestId="";agentRequests.reset();mcpOAuth.clear();loginScreen("");processOAuthIntent(getIntent());}
        },true);
    }
    private int dp(float n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private GradientDrawable surface(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);return v;}
    private TextView heading(String s,int size){TextView t=text(s,size,TEXT);t.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));t.setLetterSpacing(-.035f);return t;}
    private TextView serif(String s,int size){TextView t=text(s,size,TEXT);t.setTypeface(Typeface.create("serif",Typeface.NORMAL));t.setLetterSpacing(-.035f);return t;}
    private ImageView logo(int size){ImageView image=new ImageView(this);image.setImageResource(R.drawable.brand_icon);image.setScaleType(ImageView.ScaleType.FIT_CENTER);image.setLayoutParams(new LinearLayout.LayoutParams(dp(size),dp(size)));image.setContentDescription("DragonZpyder");return image;}
    private Button button(String s,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(s);b.setTextColor(TEXT);b.setTextSize(14);b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));b.setMinHeight(dp(48));b.setMinimumHeight(dp(48));b.setMinWidth(dp(48));b.setMinimumWidth(dp(48));b.setPadding(dp(12),0,dp(12),0);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22ffffff),surface(CHIP,10),null));b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private Button primary(String s,Runnable action){Button b=button(s,action);b.setTextColor(dark?0xff17110d:Color.WHITE);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22000000),surface(ACCENT,11),null));return b;}
    private EditText field(String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setHintTextColor(MUTED);e.setTextColor(TEXT);e.setTextSize(16);e.setPadding(dp(14),dp(12),dp(14),dp(12));GradientDrawable d=surface(PANEL,16);d.setStroke(dp(1),LINE);e.setBackground(d);if(secret)SecurePasswordField.configure(e);else e.setInputType(android.text.InputType.TYPE_CLASS_TEXT);return e;}
    private void gap(LinearLayout l,int height){l.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height)));}
    private void reset(){root=column();root.setBackgroundColor(BG);root.setPadding(dp(12),dp(8),dp(12),dp(8));setContentView(root);root.setOnApplyWindowInsetsListener((v,insets)->{int left,top,right,bottom;if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());left=bars.left;top=bars.top;right=bars.right;bottom=bars.bottom;}else{left=insets.getSystemWindowInsetLeft();top=insets.getSystemWindowInsetTop();right=insets.getSystemWindowInsetRight();bottom=insets.getSystemWindowInsetBottom();}v.setPadding(dp(12)+left,dp(8)+top,dp(12)+right,dp(8)+bottom);return insets;});root.requestApplyInsets();}
    private String authMode="login", authEmail="", challengeId="", profileInitial="D";
    private boolean accountOpen;
    private LinearLayout accountPage;
    private void loginScreen(String message){authMode="login";authScreen("login",message);}
    private void accountLayout(){
        reset();ScrollView scroller=new ScrollView(this);scroller.setFillViewport(true);accountPage=column();accountPage.setPadding(dp(12),dp(14),dp(12),dp(30));scroller.addView(accountPage);root.addView(scroller,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout bar=row();bar.addView(logo(32));bar.addView(heading("  DragonZpyder",19));bar.addView(new View(this),new LinearLayout.LayoutParams(0,1,1));bar.addView(button(dark?"☀":"☾",()->{dark=!dark;getPreferences(MODE_PRIVATE).edit().putBoolean("dark",dark).apply();palette();if(signedIn)showAccount();else authScreen(authMode,"");}));accountPage.addView(bar);gap(accountPage,24);
    }
    private void sectionLabel(LinearLayout parent,String label){TextView t=text(label,11,ACCENT);t.setLetterSpacing(.12f);parent.addView(t);gap(parent,8);}
    private EditText accountField(LinearLayout parent,String label,String value,int kind,String hint){
        TextView caption=text(label,13,TEXT);parent.addView(caption);gap(parent,6);
        EditText e=field("",false);e.setId(View.generateViewId());caption.setLabelFor(e.getId());e.setSingleLine(true);e.setInputType(kind);e.setText(value);e.setMinHeight(dp(48));if(!hint.isEmpty())e.setAutofillHints(hint);
        if(kind==SecurePasswordField.TYPE)SecurePasswordField.configure(e);
        if(kind==android.text.InputType.TYPE_CLASS_NUMBER){e.setSaveEnabled(false);e.setFreezesText(false);e.setImeOptions(android.view.inputmethod.EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);}
        parent.addView(e);gap(parent,16);return e;
    }
    private LinearLayout accountCard(){
        LinearLayout card=column();card.setPadding(dp(18),dp(18),dp(18),dp(18));GradientDrawable bg=surface(PANEL,18);bg.setStroke(dp(1),LINE);card.setBackground(bg);accountPage.addView(card,new LinearLayout.LayoutParams(-1,-2));return card;
    }
    private String value(EditText field){return field.getText().toString().trim();}
    private boolean emailValid(String email){if(!android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()){setStatus("Enter a valid email address.");return false;}return true;}
    private boolean strong(String p){if(p.length()<12){setStatus("Use at least 12 characters for your password.");return false;}return true;}
    private boolean six(String code){if(!code.matches("[0-9]{6}")){setStatus("Enter the six-digit code.");return false;}return true;}
    private void clearAccountView(){
        closeVoice();
        activeRequestId="";if(agentRequests!=null)agentRequests.reset();
        conversation="";pendingPrompt="";attachment=null;pendingFileDownload=null;attachmentName="";transcript.clear();
        meshMode=false;model="";modelAcceptsImages=false;restoredMesh=false;restoredModel="";restoredModelAcceptsImages=false;lastAnswer="";meshMessages=new JSONArray();history=new JSONArray();
        profileInitial="D";authEmail="";challengeId="";restoredDraft="";restoredConversation="";selectedMcpConnections.clear();
        restorePending=false;interruptedRequest=false;transcriptionModel="";queuedOAuthIntent=null;googleSignInPending=false;googleAttempt++;
        if(mobileOAuth!=null)mobileOAuth.clear();if(mcpOAuth!=null)mcpOAuth.clear();discardCamera();stopMedia();if(tts!=null)tts.stop();chatUi=null;
    }
    private void authSuccess(){clearAccountView();signedIn=true;accountOpen=false;chatScreen();loadHistory(true);}
    private MobileOAuthStore mobileOAuth,mcpOAuth;
    private Intent queuedOAuthIntent;
    private boolean googleSignInPending;
    private long googleAttempt;
    private LinearLayout providerButton(String symbol,String title,int identityColor,Runnable action){
        LinearLayout row=row();row.setMinimumHeight(dp(56));row.setPadding(dp(14),dp(6),dp(12),dp(6));
        TextView mark=text(symbol,22,identityColor);mark.setTypeface(Typeface.create("sans-serif-black",Typeface.BOLD));
        mark.setGravity(Gravity.CENTER);row.addView(mark,new LinearLayout.LayoutParams(dp(32),dp(44)));
        TextView label=text(title,15,TEXT);label.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);lp.setMargins(dp(9),0,0,0);
        row.addView(label,lp);TextView arrow=text("›",23,MUTED);
        row.addView(arrow,new LinearLayout.LayoutParams(dp(18),-2));
        GradientDrawable bg=surface(dark?0xff292427:0xffffffff,16);bg.setStroke(dp(1),LINE);
        row.setBackground(new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(dark?0x33ffffff:0x18000000),bg,null));
        row.setContentDescription(title);row.setClickable(true);row.setFocusable(true);
        row.setOnClickListener(v->{if(!busy)action.run();});
        return row;
    }
    private void startGoogleSignIn(){
        if(mobileOAuth!=null&&!busy)mobileOAuth.clear();
        if(busy||googleSignInPending)return;
        final boolean signup="signup".equals(authMode);
        submit("Preparing Google sign-in…",()->api.googleBootstrap(),data->{
            JSONObject info=(JSONObject)data;
            final long attempt=++googleAttempt;googleSignInPending=true;busy=true;setStatus("Choose your Google account…");
            GoogleCredentialLogin.start(this,
                info.optString("client_id"),info.optString("nonce"),
                runnable->runOnUiThread(runnable),
                token->{if(isDestroyed()||attempt!=googleAttempt||!googleSignInPending)return;googleSignInPending=false;busy=false;submit("Verifying Google account…",()->{
                    api.loginWithGoogle(token,signup);return Boolean.TRUE;
                },result->authSuccess(),true);},
                reason->{if(isDestroyed()||attempt!=googleAttempt||!googleSignInPending)return;googleSignInPending=false;busy=false;setStatus(reason);
                    if(api.isFirstParty())alert().setTitle("Google sign-in did not complete").setMessage("Try signing in through your browser instead. Your Google credentials stay with Google.").setNegativeButton("Close",null).setPositiveButton("Use browser",(d,i)->startBrowserProvider("google",signup)).show();
                });
        },true);
    }
    private void startBrowserProvider(String provider,boolean signup){
        if(busy||googleSignInPending||!api.isFirstParty())return;
        submit("Checking secure "+provider+" sign-in…",()->api.browserProviderAvailable(provider),enabled->{
            if(!Boolean.TRUE.equals(enabled)){setStatus("Browser sign-in for "+provider+" is not configured on DragonZpyder yet.");return;}
            try{
                String state=MobileOAuthStore.randomToken(),verifier=MobileOAuthStore.randomToken();
                mobileOAuth.begin(state,verifier);
                String url="https://dragonzpyder.xyz/dz/identity/v1/mobile/"+provider+"/start?state="+android.net.Uri.encode(state)+"&code_challenge="+android.net.Uri.encode(MobileOAuthStore.challenge(verifier))+(signup?"&register=true":"");
                new androidx.browser.customtabs.CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(this,android.net.Uri.parse(url));
                setStatus("Complete sign-in in your browser.");
            }catch(Exception failure){mobileOAuth.clear();setStatus("Could not open secure browser sign-in.");}
        },true);
    }
    private void startDiscordSignIn(){
        if(busy||googleSignInPending)return;
        if(api.isFirstParty()){startBrowserProvider("discord",false);return;}
        submit("Checking Discord sign-in…",()->api.discordMobileAvailable(),enabled->{
            if(!Boolean.TRUE.equals(enabled)){
                setStatus(api.isFirstParty()?"Discord sign-in: first-party mobile OAuth is not available yet.":"Discord sign-in: the server does not advertise the required mobile OAuth endpoint.");
                return;
            }
            try{
                String state=MobileOAuthStore.randomToken();
                String verifier=MobileOAuthStore.randomToken();
                mobileOAuth.begin(state,verifier);
                String challenge=MobileOAuthStore.challenge(verifier);
                String url="https://dragonzpyder.xyz/api/identities/discord/mobile/start"+
                    "?state="+android.net.Uri.encode(state)+"&code_challenge="+android.net.Uri.encode(challenge);
                androidx.browser.customtabs.CustomTabsIntent intent=
                    new androidx.browser.customtabs.CustomTabsIntent.Builder().setShowTitle(true).build();
                intent.launchUrl(this,android.net.Uri.parse(url));
                setStatus("Complete Discord sign-in in your browser to return securely.");
            }catch(Exception error){
                mobileOAuth.clear();
                setStatus("Could not open secure Discord sign-in on this device.");
            }
        },true);
    }
    private void processOAuthIntent(Intent intent){
        if(intent==null||intent.getData()==null||signedIn||isDestroyed()||googleSignInPending||!api.isModeKnown())return;
        android.net.Uri uri=intent.getData();
        if(!"dragonzpyder".equals(uri.getScheme())||!"auth".equals(uri.getHost())||
            !Arrays.asList("/google","/discord").contains(uri.getPath()))return;
        final String provider=uri.getPath().substring(1);
        if(!api.isFirstParty()&&!"discord".equals(provider))return;
        if(busy){queuedOAuthIntent=intent;return;}
        queuedOAuthIntent=null;
        setIntent(new Intent(this,MainActivity.class));
        String ticket=uri.getQueryParameter("ticket");
        String state=uri.getQueryParameter("state");
        if(uri.getQueryParameter("error")!=null){
            if(mobileOAuth.take(state)!=null)setStatus("Sign-in did not complete. Verify the provider account is linked to your DragonZpyder identity.");
            return;
        }
        if(ticket==null||state==null||!ticket.matches("[A-Za-z0-9_-]{40,120}")){
            setStatus("Discord sign-in returned an invalid response.");return;
        }
        String[] proof=mobileOAuth.take(state);
        if(proof==null){setStatus("Discord device verification expired. Please start again.");return;}
        final String verifier=proof[1];
        submit("Completing secure sign-in…",()->{
            if(api.isFirstParty())api.redeemBrowserProvider(provider,ticket,verifier);
            else api.redeemDiscordMobile(ticket,verifier);
            return Boolean.TRUE;
        },result->authSuccess(),true);
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);
        processOAuthIntent(intent);
    }
    private void authScreen(String mode,String message){
        signedIn=false;accountOpen=false;chatUi=null;authMode=mode;getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);accountLayout();
        LinearLayout hero=column();hero.setPadding(dp(20),dp(20),dp(20),dp(22));
        GradientDrawable shine=new GradientDrawable(GradientDrawable.Orientation.TL_BR,
            dark?new int[]{0xff37231f,0xff1e1919,0xff141416}:new int[]{0xffffe5d3,0xfffff2e8,0xfffffaf5});
        shine.setCornerRadius(dp(24));shine.setStroke(dp(1),dark?0xff715043:0xffefcdb8);hero.setBackground(shine);
        TextView eyebrow=text("✦   ONE IDENTITY · YOUR INTELLIGENCE",11,dark?0xffffb88f:0xffa64b24);eyebrow.setLetterSpacing(.10f);hero.addView(eyebrow);gap(hero,14);
        TextView headline=serif("Always yours.",37);headline.setTextColor(TEXT);hero.addView(headline);gap(hero,9);
        hero.addView(text("Your conversations, personal AI and authorized connections—one account, wherever you work.",14,MUTED));
        accountPage.addView(hero);gap(accountPage,18);
        LinearLayout card=accountCard();
        if(mode.equals("login")||mode.equals("signup")){
            LinearLayout tabs=row();Button sign=mode.equals("login")?primary("Sign in",()->authScreen("login","")):button("Sign in",()->authScreen("login",""));Button create=mode.equals("signup")?primary("Create account",()->authScreen("signup","")):button("Create account",()->authScreen("signup",""));
            tabs.addView(sign,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams tab=new LinearLayout.LayoutParams(0,-2,1);tab.setMargins(dp(6),0,0,0);tabs.addView(create,tab);card.addView(tabs);gap(card,22);
        }
        String title=mode.equals("signup")?"Create your account.":mode.equals("verify")?"Verify your email.":mode.equals("forgot")?"Reset your password.":mode.equals("reset")?"Set a new password.":"Welcome back.";
        card.addView(heading(title,27));gap(card,6);card.addView(text(mode.equals("signup")?"Start personal. Connect workspaces when you choose.":mode.equals("verify")?"Enter the six-digit code emailed to you.":mode.equals("forgot")?"We’ll email reset instructions if an account exists.":mode.equals("reset")?"Use the six-digit code from your password-reset email.":"Continue to your personal DragonZpyder.",14,MUTED));gap(card,20);
        status=text(message,13,message.isEmpty()?MUTED:TEXT);status.setLineSpacing(dp(2),1);card.addView(status);gap(card,8);
        if(mode.equals("login")||mode.equals("signup")){
            card.addView(providerButton("G","Continue with Google",0xff4285f4,this::startGoogleSignIn));
            gap(card,10);
            card.addView(providerButton("◈","Continue with Discord",0xff5865f2,this::startDiscordSignIn));
            if(api.isFirstParty()&&mode.equals("signup")){gap(card,12);card.addView(text("Create a DragonZpyder account with Google verification.",14,TEXT));return;}
            gap(card,18);
            LinearLayout separator=row();View left=new View(this);left.setBackgroundColor(LINE);
            separator.addView(left,new LinearLayout.LayoutParams(0,dp(1),1));
            TextView orLabel=text("  OR CONTINUE WITH EMAIL  ",11,MUTED);orLabel.setLetterSpacing(.08f);
            separator.addView(orLabel);View right=new View(this);right.setBackgroundColor(LINE);
            separator.addView(right,new LinearLayout.LayoutParams(0,dp(1),1));
            card.addView(separator);gap(card,20);
        }
        EditText name=mode.equals("signup")?accountField(card,"Your name","",1,View.AUTOFILL_HINT_NAME):null;
        EditText email=accountField(card,"Email address",authEmail,33,View.AUTOFILL_HINT_EMAIL_ADDRESS);
        EditText code=mode.equals("verify")||mode.equals("reset")?accountField(card,mode.equals("verify")?"Verification code":"Reset code","",2,"smsOTPCode"):null;
        if(code!=null)code.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(6)});
        EditText password=mode.equals("login")||mode.equals("signup")||mode.equals("reset")?accountField(card,mode.equals("login")?"Password":mode.equals("reset")?"New password (at least 12 characters)":"Password (at least 12 characters)","",SecurePasswordField.TYPE,mode.equals("login")?View.AUTOFILL_HINT_PASSWORD:"newPassword"):null;
        EditText confirm=mode.equals("signup")?accountField(card,"Confirm password","",SecurePasswordField.TYPE,"newPassword"):null;
        String action=mode.equals("signup")?"Create account":mode.equals("verify")?"Verify and continue":mode.equals("forgot")?"Send reset instructions":mode.equals("reset")?"Update password":"Sign in";
        card.addView(primary(action,()->{
            String e=value(email),p=password==null?"":password.getText().toString(),c=code==null?"":value(code),n=name==null?"":value(name);
            if(!emailValid(e))return;authEmail=e;
            if(mode.equals("signup")&&(n.isEmpty()||n.length()>200)){setStatus("Enter your name (up to 200 characters).");return;}
            if((mode.equals("signup")||mode.equals("reset"))&&!strong(p))return;
            if(confirm!=null&&!p.equals(confirm.getText().toString())){setStatus("Passwords do not match.");return;}
            if(code!=null&&!six(c))return;
            if(mode.equals("login")&&p.isEmpty()){setStatus("Enter your password.");return;}
            hideKeyboard(email);
            if(mode.equals("login")){
                submit("Signing in…",()->{try{api.login(e,p);return Boolean.TRUE;}catch(DragonApi.ApiError failure){if("EMAIL_NOT_VERIFIED".equals(failure.code))return Boolean.FALSE;throw failure;}},r->{if(Boolean.TRUE.equals(r))authSuccess();else{challengeId="";authScreen("verify","Please verify your email to continue.");}},true);
            }else if(mode.equals("signup")){
                submit("Creating your account…",()->api.preauth("signup",new JSONObject().put("display_name",n).put("email",e).put("password",p)),r->{JSONObject result=(JSONObject)r;challengeId=result.optString("challenge_id","");authEmail=result.optString("email",e);authScreen("verify","Account created. Enter the code sent to your email.");},true);
            }else if(mode.equals("verify")){
                submit("Verifying email…",()->{api.verify(e,c,challengeId);return null;},r->authSuccess(),true);
            }else if(mode.equals("forgot")){
                submit("Requesting reset…",()->api.preauth("forgot-password",DragonApi.object("email",e)),r->authScreen("reset","If the account exists, reset instructions were sent."),true);
            }else if(mode.equals("reset")){
                submit("Updating password…",()->api.preauth("reset-password",new JSONObject().put("email",e).put("code",c).put("password",p)),r->authScreen("login","Password updated. Sign in with your new password."),true);
            }
            if(password!=null)password.setText("");if(confirm!=null)confirm.setText("");
        }));
        if(mode.equals("login")&&!api.isFirstParty()){card.addView(button("Forgot password?",()->{authEmail=value(email);authScreen("forgot","");}));card.addView(button("Already have a verification code?",()->{authEmail=value(email);challengeId="";authScreen("verify","");}));}
        if(mode.equals("verify"))card.addView(button("Resend code",()->{String e=value(email);if(!emailValid(e))return;submit("Requesting code…",()->api.preauth("resend-verification",DragonApi.object("email",e)),r->setStatus("If verification is pending, another code is on its way."),true);}));
        if(mode.equals("forgot"))card.addView(button("I have a reset code",()->{authEmail=value(email);authScreen("reset","");}));
        if(!mode.equals("login")&&!mode.equals("signup"))card.addView(button("Back to sign in",()->authScreen("login","")));
        gap(accountPage,24);accountPage.addView(text("One account, clear boundaries. Personal access does not grant business permissions.",12,MUTED));
    }
    private void chatScreen(){
        String draft=chatUi==null?"":chatUi.getDraft();accountOpen=false;getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);reset();status=null;
        chatUi=new NativeChatView(this,dark,new NativeChatView.Actions(){
            public void menu(){showMenu();}
            public void newChat(){MainActivity.this.newChat();}
            public void connections(){showConnections();}
            public void tasks(){showTasks();}
            public void approvals(){MainActivity.this.approvals();}
            public void openConversation(String id){open(id);}
            public void voice(){showVoice();}
            public void files(){showFiles();}
            public void saveArtifact(String metadata){try{chooseFileDestination(new JSONObject(metadata));}catch(Exception invalid){setStatus("Invalid file receipt.");}}
            public void commands(){showCommands();}
            public void theme(){toggleTheme();}
            public void account(){showAccount();}
            public void add(){showAdd();}
            public void mode(){showModes();}
            public void dictate(){MainActivity.this.dictate();}
            public void send(){MainActivity.this.send();}
            public void stop(){if(!activeRequestId.isEmpty())cancelActiveAgent();else{api.cancelStream();setStatus("Stopping reply…");}}
            public void removeAttachment(){if(!busy){attachment=null;attachmentName="";chatUi.setAttachmentLabel("");}}
            public void copy(String value){android.content.ClipboardManager cb=(android.content.ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);cb.setPrimaryClip(android.content.ClipData.newPlainText("DragonZpyder",value));}
            public void speak(String value){if(speechReady)tts.speak(value,TextToSpeech.QUEUE_FLUSH,null,"response");else setStatus("Speech engine unavailable");}
        });
        chatUi.setDraft(draft);chatUi.setModeLabel(meshMode?"AI Mesh":"Agent");chatUi.setModelLabel(model);chatUi.setAttachmentLabel(attachmentName);chatUi.setProfileInitial(profileInitial);chatUi.setBusy(busy);chatUi.setVoiceAvailable(api.supportsVoice());chatUi.setFilesAvailable(api.supportsFiles());chatUi.setGoalsAvailable(!api.isFirstParty()||api.supportsGoals());chatUi.setLegacyActionsAvailable(!api.isFirstParty());
        for(String[] item:transcript)chatUi.append(item[0],item[1]);
        root.addView(chatUi.getView(),new LinearLayout.LayoutParams(-1,0,1));
    }
    private void setStatus(String value){if(status!=null)status.setText(value);if(chatUi!=null&&signedIn&&!accountOpen)chatUi.setStatusText(value);}
    private AlertDialog.Builder alert(){return new AlertDialog.Builder(this,dark?R.style.DragonDialogDark:R.style.DragonDialogLight);}
    private TextView navRow(String symbol,String label,boolean selected,Runnable action){
        TextView v=text(symbol+"   "+label,14,TEXT);v.setGravity(Gravity.CENTER_VERTICAL);v.setMinHeight(dp(48));
        v.setPadding(dp(12),dp(8),dp(12),dp(8));v.setMaxLines(2);v.setEllipsize(android.text.TextUtils.TruncateAt.END);
        v.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(dark?0x25ffffff:0x18000000),surface(selected?CHIP:Color.TRANSPARENT,10),surface(Color.WHITE,10)));
        v.setOnClickListener(w->{if(!busy)action.run();});v.setFocusable(true);v.setContentDescription(label);return v;
    }
    private void showMenu(){
        if(busy||chatUi==null||!signedIn)return;
        final NativeChatView target=chatUi;
        target.setConversationHistory(history,conversation);target.openDrawer();
        worker.execute(()->{
            try{
                JSONArray refreshed=(JSONArray)api.call("/api/personal-agent/conversations",null);
                runOnUiThread(()->{if(!isDestroyed()&&signedIn&&chatUi==target){history=refreshed;target.setConversationHistory(history,conversation);}});
            }catch(Exception e){
                runOnUiThread(()->{if(!isDestroyed()&&signedIn&&chatUi==target){
                    if(e instanceof DragonApi.ApiError&&((DragonApi.ApiError)e).status==401&&!busy){api.clear();clearAccountView();loginScreen("Session expired. Sign in again.");}
                    else target.markHistoryError();
                }});
            }
        });
    }
    private void showAccount(){
        submit("Loading account…",()->{
            JSONObject p=api.profile();if(api.isFirstParty()){p.put("workspaces_unavailable",true);return p;}p.put("native_sessions",api.call("/api/auth/sessions",null));
            try{p.put("native_workspaces",api.call("/api/auth/workspaces",null));}catch(Exception failure){if(failure instanceof DragonApi.ApiError&&((DragonApi.ApiError)failure).status==401)throw failure;p.put("workspaces_unavailable",true);}
            return p;
        },r->renderAccount((JSONObject)r),true);
    }
    private void renderAccount(JSONObject p){
        accountOpen=true;getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);accountLayout();
        accountPage.addView(button("‹ Back to Personal AI",()->{accountOpen=false;chatScreen();}));gap(accountPage,20);
        sectionLabel(accountPage,"YOUR DRAGONZPYDER");accountPage.addView(heading("Account & connections.",30));gap(accountPage,8);accountPage.addView(text("One identity, with clear boundaries around every connected service and workspace.",14,MUTED));gap(accountPage,20);
        LinearLayout profile=accountCard();sectionLabel(profile,"01 / IDENTITY");profile.addView(heading("Your profile",21));gap(profile,8);profile.addView(text(p.optString("email"),14,MUTED));gap(profile,16);
        String current=p.optString("display_name");if(!current.isEmpty())profileInitial=current.substring(0,1).toUpperCase(Locale.ROOT);EditText name=accountField(profile,"Display name",current,1,View.AUTOFILL_HINT_NAME);
        status=text("",13,MUTED);profile.addView(status);profile.addView(primary("Save changes",()->{String n=value(name);if(n.isEmpty()||n.length()>200){setStatus("Enter a display name up to 200 characters.");return;}submit("Saving…",()->{api.updateName(n);return api.profile();},result->{JSONObject saved=(JSONObject)result;p.put("display_name",saved.optString("display_name",n));renderAccount(p);setStatus("Your account has been updated.");},true);}));
        gap(accountPage,14);LinearLayout identity=accountCard();sectionLabel(identity,"02 / ACCESS");identity.addView(heading("Sign-in methods",21));gap(identity,8);
        JSONArray ids=p.optJSONArray("auth_identities");if(ids!=null)for(int i=0;i<ids.length();i++){JSONObject item=ids.optJSONObject(i);if(item!=null){identity.addView(text(item.optString("provider")+(item.optString("account").isEmpty()?"":" · "+item.optString("account")),14,TEXT));gap(identity,8);}}
        if(ids==null||ids.length()==0)identity.addView(text(api.isFirstParty()?p.optString("identity_origin","DragonZpyder"):"No sign-in methods returned.",13,MUTED));gap(identity,10);identity.addView(text("Connected tools require their own authorization. Signing in does not grant Gmail or Calendar access.",12,MUTED));
        gap(accountPage,14);LinearLayout sessions=accountCard();sectionLabel(sessions,"03 / SECURITY");sessions.addView(heading("Active sessions",21));gap(sessions,12);
        if(api.isFirstParty())sessions.addView(text("This device has a verified Personal session. Full session inventory is not yet exposed.",13,MUTED));JSONArray list=p.optJSONArray("native_sessions");if(list!=null)for(int i=0;i<list.length();i++){JSONObject item=list.optJSONObject(i);if(item==null)continue;sessions.addView(text(item.optString("device","Session")+(item.optBoolean("current")?" · This device":""),14,TEXT));sessions.addView(text(item.optString("scope",""),12,MUTED));gap(sessions,12);}
        gap(accountPage,14);LinearLayout spaces=accountCard();sectionLabel(spaces,"04 / SCOPE");spaces.addView(heading("Your workspaces",21));gap(spaces,8);
        JSONArray work=p.optJSONArray("native_workspaces");if(p.optBoolean("workspaces_unavailable"))spaces.addView(text("Workspace information is unavailable.",13,MUTED));else if(work==null||work.length()==0)spaces.addView(text("No business workspaces attached to this account.",13,MUTED));else for(int i=0;i<work.length();i++){JSONObject w=work.optJSONObject(i);if(w!=null){spaces.addView(text(w.optString("name")+" · "+w.optString("role"),14,TEXT));gap(spaces,8);}}
        gap(accountPage,14);accountPage.addView(button("Manage connections & tools",this::showConnections));gap(accountPage,14);Button out=button("Sign out",this::confirmSignOut);out.setTextColor(dark?0xffffa59a:0xffb6382b);accountPage.addView(out);gap(accountPage,10);accountPage.addView(text("Signs out this device and clears its local conversation view. Your server conversations are retained.",12,MUTED));
    }
    private void confirmSignOut(){alert().setTitle("Sign out of DragonZpyder?").setMessage("You’ll need to sign in again to access your Personal workspace on this device.").setNegativeButton("Cancel",null).setPositiveButton("Sign out",(d,i)->signOut()).show();}
    private void showCommands(){
        if(chatUi==null||busy)return;
        ArrayList<String> availableNames=new ArrayList<>(),availableIcons=new ArrayList<>();ArrayList<Runnable> availableActions=new ArrayList<>();
        // Primary navigation lives in the drawer, not in a duplicate command list.
        if(!api.isFirstParty()){availableNames.add("Switch mode");availableIcons.add("more");availableActions.add(this::showModes);}
        availableNames.add("Dictate a message");availableIcons.add("mic");availableActions.add(this::dictate);
        if(api.supportsVoice()){availableNames.add("Live voice");availableIcons.add("voice");availableActions.add(this::showVoice);}
        if(!api.isFirstParty()){availableNames.add("AI Mesh media");availableIcons.add("attach");availableActions.add(this::showMedia);}
        if(!api.isFirstParty()){availableNames.add("Your tools");availableIcons.add("connections");availableActions.add(this::showTools);}
        chatUi.showCommands(availableNames.toArray(new String[0]),availableIcons.toArray(new String[0]),availableActions.toArray(new Runnable[0]));
    }
    private void showAdd(){
        if(api.isFirstParty()){
            if(!api.supportsFiles()){setStatus("First-party Agent file uploads are not enabled for this session.");return;}
            alert().setTitle("Attach a file").setMessage("The selected file will be uploaded to your private encrypted file storage. The Agent receives it only when you send a message. Maximum 10 MiB.")
                .setNegativeButton("Cancel",null).setPositiveButton("Choose file",(d,i)->{
                    Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.setType("*/*");picker.addCategory(Intent.CATEGORY_OPENABLE);picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    try{startActivityForResult(picker,47);}catch(android.content.ActivityNotFoundException e){setStatus("No file picker available.");}
                }).show();return;
        }
        if(!meshMode){setStatus("Agent attachments are not available on this server yet. Your conversation has not changed.");return;}
        alert().setTitle("Add to your message").setItems(new String[]{"Attach a file or photo","Take a photo"},(d,i)->{
            if(i==1){
                if(!modelAcceptsImages){setStatus("The selected model does not advertise image support. Choose a vision model.");return;}
                launchCamera();return;
            }
            Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.setType("*/*");picker.addCategory(Intent.CATEGORY_OPENABLE);picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try{startActivityForResult(picker,43);}catch(android.content.ActivityNotFoundException e){setStatus("No file picker available.");}
        }).setNegativeButton("Close",null).show();
    }
    private void uploadAgentAttachment(android.net.Uri uri){
        if(busy||!signedIn||!api.supportsFiles())return;
        submit("Uploading private attachment…",()->fileRepository.upload(uri),r->{JSONObject receipt=(JSONObject)r;attachment=receipt;attachmentName=receipt.getString("filename");if(chatUi!=null)chatUi.setAttachmentLabel(attachmentName);setStatus("File attached · send to include it in your request");},true);
    }
    private void showFiles(){
        if(!signedIn||!api.supportsFiles()){setStatus("Shared file storage is not enabled for this session.");return;}
        submit("Loading files…",()->fileRepository.inventory(),r->{
            @SuppressWarnings("unchecked") List<JSONObject> valid=(List<JSONObject>)r;
            if(valid.isEmpty()){alert().setTitle("Your files").setMessage("No files uploaded or generated yet.").setPositiveButton("Close",null).show();return;}
            ArrayList<String> labels=new ArrayList<>();
            for(JSONObject file:valid)labels.add(file.optString("filename")+" · "+Math.max(1,(file.optInt("size")+1023)/1024)+" KB");
            alert().setTitle("Your files").setItems(labels.toArray(new String[0]),(d,i)->chooseFileDestination(valid.get(i))).setNegativeButton("Close",null).show();
        },true);
    }
    private void chooseFileDestination(JSONObject file){
        if(busy||!signedIn||!api.supportsFiles())return;
        if(!AgentFileRepository.validReceipt(file)){setStatus("Invalid file receipt.");return;}
        String name=file.optString("filename","download");
        pendingFileDownload=file;
        Intent picker=new Intent(Intent.ACTION_CREATE_DOCUMENT);picker.addCategory(Intent.CATEGORY_OPENABLE);picker.setType("application/octet-stream");picker.putExtra(Intent.EXTRA_TITLE,name);
        try{startActivityForResult(picker,48);}catch(Exception unavailable){pendingFileDownload=null;setStatus("File destination picker unavailable.");}
    }
    private void saveAgentFile(android.net.Uri uri,JSONObject file){
        if(busy||!signedIn||!api.supportsFiles()||file==null)return;
        submit("Downloading verified file…",()->{
            fileRepository.save(uri,file);
            return Boolean.TRUE;
        },r->setStatus("File saved"),true);
    }
    private void appendGeneratedFiles(JSONObject answer){
        JSONArray files=answer.optJSONArray("artifacts");
        if(files==null)return;
        for(int i=0;i<Math.min(files.length(),20);i++){JSONObject file=files.optJSONObject(i);if(file!=null&&AgentFileRepository.validReceipt(file))append("artifact",file.toString());}
    }
    private void discardCamera(){
        if(cameraCapture!=null){
            try{android.net.Uri uri=androidx.core.content.FileProvider.getUriForFile(this,getPackageName()+".camera",cameraCapture);revokeUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);}catch(Exception ignored){}
            cameraCapture.delete();cameraCapture=null;
        }
    }
    private void launchCamera(){
        discardCamera();
        try{
            java.io.File directory=new java.io.File(getCacheDir(),"camera");
            if(!directory.exists()&&!directory.mkdirs())throw new java.io.IOException("Camera cache unavailable");
            cameraCapture=java.io.File.createTempFile("capture-",".jpg",directory);
            android.net.Uri uri=androidx.core.content.FileProvider.getUriForFile(this,getPackageName()+".camera",cameraCapture);
            Intent camera=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
            camera.putExtra(android.provider.MediaStore.EXTRA_OUTPUT,uri);
            camera.setClipData(android.content.ClipData.newRawUri("Photo",uri));
            camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivityForResult(camera,45);
        }catch(Exception failure){discardCamera();setStatus("Camera app or capture storage unavailable.");}
    }
    private void attachCameraCapture(){
        final java.io.File capture=cameraCapture;
        if(capture==null||!capture.isFile()||capture.length()==0){discardCamera();setStatus("Camera returned no photo.");return;}
        if(busy){discardCamera();setStatus("Camera result could not be processed while another request was active.");return;}
        submit("Preparing full-resolution photo…",()->{
            try{
                if(capture.length()>32L*1024*1024)throw new Exception("Camera file exceeds 32 MB");
                android.graphics.BitmapFactory.Options options=new android.graphics.BitmapFactory.Options();options.inJustDecodeBounds=true;
                android.graphics.BitmapFactory.decodeFile(capture.getAbsolutePath(),options);
                if(options.outWidth<1||options.outHeight<1||options.outWidth>16000||options.outHeight>16000)throw new Exception("Unsupported photo dimensions");
                options.inJustDecodeBounds=false;options.inSampleSize=1;while(Math.max(options.outWidth,options.outHeight)/options.inSampleSize>2048)options.inSampleSize*=2;
                android.graphics.Bitmap bitmap=android.graphics.BitmapFactory.decodeFile(capture.getAbsolutePath(),options);
                if(bitmap==null)throw new Exception("Camera photo could not be decoded");
                try{
                    java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
                    for(int quality:new int[]{92,82,72,60}){out.reset();if(bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG,quality,out)&&out.size()>0&&out.size()<=2500000)break;}
                    if(out.size()==0||out.size()>2500000)throw new Exception("Camera photo exceeds upload limit");
                    return new JSONObject().put("type","image_url").put("image_url",new JSONObject().put("url","data:image/jpeg;base64,"+android.util.Base64.encodeToString(out.toByteArray(),android.util.Base64.NO_WRAP)));
                }finally{bitmap.recycle();}
            }finally{capture.delete();}
        },r->{discardCamera();attachment=(JSONObject)r;attachmentName="Camera photo";if(chatUi!=null)chatUi.setAttachmentLabel(attachmentName);},true);
    }
    private void readAttachment(android.net.Uri uri){
        submit("Preparing attachment…",()->{
            String mime=getContentResolver().getType(uri),name="attachment";
            try(android.database.Cursor c=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())name=c.getString(0);}
            if(name==null||name.isEmpty()||name.length()>120)throw new Exception("Unsupported filename");
            if(mime==null)mime="application/octet-stream";
            boolean image=Arrays.asList("image/jpeg","image/png","image/webp").contains(mime);
            if(image&&!modelAcceptsImages)throw new Exception("Choose a model that supports image inputs.");
            String extension=name.toLowerCase(Locale.ROOT);
            if(!image&&!extension.matches(".*\\.(pdf|docx|txt|md|csv|json|py|log)$"))throw new Exception("Unsupported file format");
            if(!image&&extension.endsWith(".pdf"))mime="application/pdf";
            else if(!image&&extension.endsWith(".docx"))mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            else if(!image)mime="text/plain";
            int limit=extension.endsWith(".docx")?1000000:extension.matches(".*\\.(txt|md|csv|json|py|log)$")?250000:3*1024*1024;
            java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new Exception("Cannot read attachment");byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>limit)throw new Exception("Attachment exceeds size limit");out.write(buffer,0,n);}}
            if(out.size()==0)throw new Exception("Empty file");
            byte[] bytes=out.toByteArray();
            if(image){android.graphics.BitmapFactory.Options bounds=new android.graphics.BitmapFactory.Options();bounds.inJustDecodeBounds=true;android.graphics.BitmapFactory.decodeByteArray(bytes,0,bytes.length,bounds);if(bounds.outWidth<1||bounds.outHeight<1||bounds.outWidth>8192||bounds.outHeight>8192||!mime.equals(bounds.outMimeType))throw new Exception("Invalid image or unsupported dimensions");}
            else if(extension.endsWith(".pdf")&&(bytes.length<5||!new String(bytes,0,5,java.nio.charset.StandardCharsets.US_ASCII).equals("%PDF-")))throw new Exception("Invalid PDF");
            else if(extension.endsWith(".docx")&&(bytes.length<4||bytes[0]!=80||bytes[1]!=75))throw new Exception("Invalid DOCX");
            else if(!extension.endsWith(".pdf")&&!extension.endsWith(".docx"))java.nio.charset.StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(bytes));
            String encoded="data:"+mime+";base64,"+android.util.Base64.encodeToString(out.toByteArray(),android.util.Base64.NO_WRAP);
            JSONObject part=image?new JSONObject().put("type","image_url").put("image_url",new JSONObject().put("url",encoded)):new JSONObject().put("type","file").put("file",new JSONObject().put("filename",name).put("file_data",encoded));
            return new JSONObject().put("name",name).put("part",part);
        },r->{JSONObject file=(JSONObject)r;attachment=file.getJSONObject("part");attachmentName=file.getString("name");if(chatUi!=null)chatUi.setAttachmentLabel(attachmentName);},true);
    }
    private String transcriptionModel="";
    private android.media.MediaPlayer mediaPlayer;
    private java.io.File mediaFile;
    private void stopMedia(){
        if(mediaPlayer!=null){mediaPlayer.release();mediaPlayer=null;}
        if(mediaFile!=null){mediaFile.delete();mediaFile=null;}
    }
    private void showMedia(){
        if(api.isFirstParty()){setStatus("AI Mesh media is not yet authorized for first-party identity.");return;}
        submit("Loading media models…",()->api.call("/mesh/models",null),result->{
            JSONObject catalog=(JSONObject)result;
            ArrayList<String> labels=new ArrayList<>(),kinds=new ArrayList<>();
            labels.add("Generate speech");kinds.add("tts");labels.add("Transcribe an audio file");kinds.add("stt");
            if(catalog.optBoolean("imageEnabled")){labels.add("Generate an image");kinds.add("image");}
            alert().setTitle("AI Mesh media").setItems(labels.toArray(new String[0]),(d,i)->pickMediaModel(catalog,kinds.get(i))).setNegativeButton("Close",null).show();
        },true);
    }
    private void pickMediaModel(JSONObject catalog,String kind){
        JSONArray items=catalog.optJSONArray(kind);
        if(items==null||items.length()==0){setStatus("No compatible models returned.");return;}
        String[] labels=new String[items.length()];
        for(int i=0;i<labels.length;i++){JSONObject item=items.optJSONObject(i);labels[i]=item==null?"Unavailable":item.optString("name",item.optString("id"));}
        alert().setTitle("Choose a "+kind+" model").setItems(labels,(d,i)->{
            JSONObject item=items.optJSONObject(i);if(item==null)return;String id=item.optString("id");if(id.isEmpty())return;
            if(kind.equals("stt")){
                transcriptionModel=id;
                Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.setType("audio/*");picker.addCategory(Intent.CATEGORY_OPENABLE);
                try{startActivityForResult(picker,44);}catch(android.content.ActivityNotFoundException e){setStatus("Audio picker unavailable.");}
            }else{
                EditText prompt=field(kind.equals("image")?"Describe your image":"Enter text to speak",false);
                prompt.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);
                prompt.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(kind.equals("image")?1600:1200)});
                prompt.setMinLines(3);
                LinearLayout container=column();container.setPadding(dp(18),dp(8),dp(18),dp(8));container.addView(text("Provider charges may apply. Uses your authorized DragonZpyder account.",13,MUTED));gap(container,8);container.addView(prompt);
                AlertDialog box=alert().setTitle(kind.equals("image")?"Generate image":"Generate speech").setView(container).setNegativeButton("Cancel",null).setPositiveButton("Generate",null).create();
                box.setOnShowListener(v->box.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(w->{String content=value(prompt);if(content.isEmpty()){prompt.setError("Enter a prompt");return;}box.dismiss();
                    alert().setTitle("Confirm generation").setMessage("Send this request to "+labels[i]+"? Provider usage may be billed.").setNegativeButton("Cancel",null).setPositiveButton("Generate",(confirm,j)->generateMedia(kind,id,content)).show();
                }));box.show();
            }
        }).setNegativeButton("Close",null).show();
    }
    private void generateMedia(String kind,String id,String content){
        final boolean image=kind.equals("image");
        submit(image?"Generating image…":"Generating speech…",()->{
            JSONObject body=new JSONObject().put("model",id).put(image?"prompt":"text",content);
            if(image)body.put("confirmed",true);
            JSONObject result=(JSONObject)api.call(image?"/mesh/image":"/mesh/speech",body);
            byte[] bytes=MediaPayload.decode(result.optString(image?"image":"audio"),image?"image":"audio",image?6*1024*1024:4*1024*1024);
            if(image){
                android.graphics.BitmapFactory.Options options=new android.graphics.BitmapFactory.Options();options.inJustDecodeBounds=true;android.graphics.BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);
                if(options.outWidth<1||options.outHeight<1||options.outWidth>8192||options.outHeight>8192)throw new Exception("Unsupported image dimensions");
                options.inJustDecodeBounds=false;options.inSampleSize=1;while(options.outWidth/options.inSampleSize>2048||options.outHeight/options.inSampleSize>2048)options.inSampleSize*=2;
                android.graphics.Bitmap bitmap=android.graphics.BitmapFactory.decodeByteArray(bytes,0,bytes.length,options);if(bitmap==null)throw new Exception("Image could not be decoded");return bitmap;
            }
            return bytes;
        },result->{
            if(image){
                ImageView preview=new ImageView(this);preview.setImageBitmap((android.graphics.Bitmap)result);preview.setAdjustViewBounds(true);preview.setScaleType(ImageView.ScaleType.FIT_CENTER);preview.setContentDescription("Generated image");
                alert().setTitle("Generated image").setView(preview).setPositiveButton("Close",null).show();
            }else{
                stopMedia();mediaFile=java.io.File.createTempFile("dz-speech-",".mp3",getCacheDir());
                try(java.io.FileOutputStream out=new java.io.FileOutputStream(mediaFile)){out.write((byte[])result);}
                mediaPlayer=new android.media.MediaPlayer();mediaPlayer.setDataSource(mediaFile.getAbsolutePath());
                AlertDialog player=alert().setTitle("Generated speech").setMessage("Preparing audio…").setPositiveButton("Close",null).create();
                player.setOnDismissListener(d->stopMedia());mediaPlayer.setOnPreparedListener(p->{if(mediaPlayer==p){player.setMessage("Playing generated speech");p.start();}});
                mediaPlayer.setOnCompletionListener(p->{if(mediaPlayer==p)player.setMessage("Playback completed.");});
                mediaPlayer.setOnErrorListener((p,w,e)->{player.setMessage("Audio playback failed.");stopMedia();return true;});
                player.show();mediaPlayer.prepareAsync();
            }
        },true);
    }
    private void transcribeAudio(android.net.Uri uri){
        final String id=transcriptionModel;transcriptionModel="";if(id.isEmpty())return;
        submit("Reading audio…",()->{
            String mime=getContentResolver().getType(uri);
            if("audio/x-wav".equals(mime))mime="audio/wav";
            if("audio/m4a".equals(mime)||"audio/x-m4a".equals(mime))mime="audio/mp4";
            if(!Arrays.asList("audio/webm","audio/mpeg","audio/mp4","audio/ogg","audio/wav","audio/flac").contains(mime))throw new Exception("Unsupported audio format");
            java.io.ByteArrayOutputStream output=new java.io.ByteArrayOutputStream();
            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new Exception("Cannot open audio");byte[] buffer=new byte[8192];int count;while((count=in.read(buffer))!=-1){if(output.size()+count>2500000)throw new Exception("Audio exceeds native 2.5 MB upload limit");output.write(buffer,0,count);}}
            if(output.size()==0)throw new Exception("Empty audio file");
            return "data:"+mime+";base64,"+android.util.Base64.encodeToString(output.toByteArray(),android.util.Base64.NO_WRAP);
        },data->alert().setTitle("Transcribe selected audio?").setMessage("The selected audio will be sent to the chosen model. Provider usage may be billed.").setNegativeButton("Cancel",null).setPositiveButton("Transcribe",(d,i)->submit("Transcribing…",()->api.call("/mesh/transcribe",new JSONObject().put("model",id).put("audio",data)),r->{
            String text=((JSONObject)r).optString("text");if(text.isEmpty())throw new Exception("No transcription returned.");
            alert().setTitle("Transcription").setMessage(text).setPositiveButton("Add to draft",(dialog,j)->{if(chatUi!=null){String draft=chatUi.getDraft();chatUi.setDraft(draft+(draft.isEmpty()?"":" ")+text);}}).setNegativeButton("Close",null).show();
        },true)).show(),true);
    }
    private void showModes(){if(api.isFirstParty()){setStatus("DragonZpyder Agent · AI Mesh is not yet authorized for this identity.");return;}alert().setTitle("Choose your intelligence").setItems(new String[]{"DragonZpyder Agent — tasks and tools","AI Mesh — choose a model"},(d,i)->{if(i==0){if(meshMode)switchMode(false,"",false);}else chooseModel();}).show();}
    private void append(String role,String content){transcript.add(new String[]{role,content});if(chatUi!=null)chatUi.append(role,content);}
    private void hideKeyboard(View v){((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(v.getWindowToken(),0);}
    private void submit(String label,Work work,Done done,boolean report){
        if(busy)return;busy=true;if(chatUi!=null)chatUi.setBusy(true);setStatus(label);
        worker.execute(()->{
            Object result=null;Exception error=null;
            try{result=work.run();}catch(Exception e){error=e;}
            final Object value=result;final Exception failure=error;
            runOnUiThread(()->{
                if(isDestroyed())return;busy=false;if(chatUi!=null){chatUi.setBusy(false);chatUi.setStreaming(false);}
                try{
                    if(failure!=null)throw failure;
                    setStatus(signedIn&&!accountOpen?(meshMode?"AI Mesh · "+model:"Personal agent"):"");
                    done.accept(value);
                }catch(Exception e){
                    if(e instanceof DragonApi.ApiError && ((DragonApi.ApiError)e).status==401 && signedIn){api.clear();clearAccountView();loginScreen("Session expired. Sign in again.");}
                    else if(report){boolean hadPartial=chatUi!=null&&!chatUi.getPartialReply().isEmpty();if(hadPartial){append("assistant",chatUi.getPartialReply()+"\n\n[Reply incomplete]");chatUi.setPartialReply("");}if(!pendingPrompt.isEmpty()&&chatUi!=null){if(meshMode&&!hadPartial&&chatUi.getDraft().isEmpty()){if(!"[Attachment]".equals(pendingPrompt))chatUi.setDraft(pendingPrompt);if(!transcript.isEmpty()&&"user".equals(transcript.get(transcript.size()-1)[0])){transcript.remove(transcript.size()-1);chatUi.clearMessages();for(String[] item:transcript)chatUi.append(item[0],item[1]);}}append("system","Request did not return a confirmed completion. Check server history or tasks before resending an agent action.");pendingPrompt="";}if(restorePending)applyRestoredDraft();setStatus(e.getMessage()==null?"Request failed":e.getMessage());}
                }
                if(!busy&&queuedOAuthIntent!=null){Intent oauth=queuedOAuthIntent;queuedOAuthIntent=null;processOAuthIntent(oauth);}
            });
        });
    }
    private void switchMode(boolean mesh,String nextModel,boolean acceptsImages){
        String draft=chatUi==null?"":chatUi.getDraft();
        Runnable change=()->{meshMode=mesh;model=nextModel;modelAcceptsImages=acceptsImages;newChat();if(chatUi!=null)chatUi.setDraft(draft);};
        if(!transcript.isEmpty()||attachment!=null)alert().setTitle("Start a new conversation?").setMessage("Switching modes starts a new conversation. Your draft text is retained, but any attachment and the current local context are cleared.").setNegativeButton("Cancel",null).setPositiveButton("Switch",(d,i)->change.run()).show();else change.run();
    }
    private void newChat(){
        if(busy)return;restorePending=false;restoredDraft="";restoredConversation="";transcript.clear();pendingPrompt="";attachment=null;attachmentName="";conversation="";meshMessages=new JSONArray();lastAnswer="";
        if(chatUi!=null){chatUi.clearMessages();chatUi.setDraft("");chatUi.setAttachmentLabel("");chatUi.setModeLabel(meshMode?"AI Mesh":"Agent");chatUi.setModelLabel(model);}
        setStatus(meshMode?"AI Mesh · "+model:"Personal agent");
    }
    private void send(){
        if(busy||!signedIn||chatUi==null)return;
        if(!activeRequestId.isEmpty()){showUnresolvedAgentRequest();return;}
        String prompt=chatUi.getDraft().trim();if(prompt.isEmpty()&&attachment==null)return;
        if(prompt.length()>(meshMode?5000:12000)){setStatus("Message is too long for this mode.");return;}
        View focused=getCurrentFocus();if(focused!=null)hideKeyboard(focused);chatUi.setDraft("");pendingPrompt=prompt.isEmpty()?"[Attachment]":prompt;
        if(meshMode){
            final JSONArray next=new JSONArray();
            try{int budget=14000-prompt.length()-(attachment!=null&&"file".equals(attachment.optString("type"))?8000:0);int start=meshMessages.length();for(int i=meshMessages.length()-2;i>=0&&meshMessages.length()-i<=10;i-=2){JSONObject user=meshMessages.getJSONObject(i),assistant=meshMessages.getJSONObject(i+1);int chars=user.optString("content").length()+assistant.optString("content").length();if(chars>budget)break;budget-=chars;start=i;}for(int i=start;i<meshMessages.length();i++)next.put(meshMessages.get(i));if(start>0)append("system","Older AI Mesh messages were omitted to fit the server context limit.");Object content=attachment==null?prompt:new JSONArray().put(new JSONObject().put("type","text").put("text",prompt)).put(attachment);next.put(new JSONObject().put("role","user").put("content",content));}
            catch(JSONException e){chatUi.setDraft(prompt);pendingPrompt="";setStatus("Message error");return;}
            append("user",prompt+(attachmentName.isEmpty()?"":"\n[Attachment: "+attachmentName+"]"));
            final NativeChatView target=chatUi;
            target.setPartialReply("");target.setStreaming(true);api.prepareStream();
            submit("Generating…",()->api.streamChat(new JSONObject().put("model",model).put("messages",next),delta->runOnUiThread(()->{if(!isDestroyed()&&chatUi==target)target.setPartialReply(target.getPartialReply()+delta);})),r->{
                String value=(String)r;if(value.isEmpty())throw new Exception("Model did not return text.");
                pendingPrompt="";target.setPartialReply("");String previousAttachment=attachmentName;attachment=null;attachmentName="";if(chatUi!=null)chatUi.setAttachmentLabel("");meshMessages=next;meshMessages.put(meshMessages.length()-1,new JSONObject().put("role","user").put("content",prompt+(previousAttachment.isEmpty()?"":" [Prior attachment omitted; reattach to inspect it again.]")));if(!previousAttachment.isEmpty())append("system","Attachment was sent for this turn only. Reattach it if a later question needs its original contents.");meshMessages.put(new JSONObject().put("role","assistant").put("content",value.length()>5000?value.substring(0,5000):value));lastAnswer=value;append("assistant",value);
            },true);return;
        }
        final JSONObject selectedAttachment=attachment;
        if(selectedAttachment!=null&&!api.supportsFiles()){chatUi.setDraft(prompt);pendingPrompt="";setStatus("Agent attachments unavailable.");return;}
        append("user",prompt+(attachmentName.isEmpty()?"":"\n[Attachment: "+attachmentName+"]"));
        final String id=conversation;
        if(api.supportsRequestLedger()){
            try{
                final JSONObject body=DragonApi.object("message",prompt);if(!id.isEmpty())body.put("conversation_id",id);
                if(!selectedMcpConnections.isEmpty())body.put("mcp_connection_ids",new JSONArray(selectedMcpConnections));
                if(selectedAttachment!=null)body.put("attachment_ids",new JSONArray().put(selectedAttachment.getString("id")));
                activeRequestId=UUID.randomUUID().toString();body.put("request_id",activeRequestId);
                if(!pendingAgentStore.save(api.pendingRequestBinding(),activeRequestId)){
                    activeRequestId="";pendingPrompt="";chatUi.setDraft(prompt);
                    if(!transcript.isEmpty()&&"user".equals(transcript.get(transcript.size()-1)[0])){transcript.remove(transcript.size()-1);chatUi.clearMessages();for(String[] item:transcript)chatUi.append(item[0],item[1]);}
                    setStatus("Unable to save request tracking. No agent request was sent.");return;
                }
                if(api.supportsAgentStream())agentRequests.startStreaming(activeRequestId,progress->api.streamAgent(body,progress));
                else agentRequests.start(activeRequestId,()->(JSONObject)api.call("/api/personal-agent/chat",body));
            }catch(Exception failure){pendingPrompt="";setStatus("Request could not start or its outcome is unconfirmed. Check request status before resending.");}
            return;
        }
        submit("Working…",()->{JSONObject body=DragonApi.object("message",prompt);if(!id.isEmpty())body.put("conversation_id",id);if(api.isFirstParty()&&!selectedMcpConnections.isEmpty())body.put("mcp_connection_ids",new JSONArray(selectedMcpConnections));return api.call("/api/personal-agent/chat",body);},r->{
            JSONObject answer=(JSONObject)r;conversation=answer.optString("conversation_id",id);
            String value=answer.optString("message",answer.optString("output",""));
            JSONObject nested=answer.optJSONObject("result");if(value.isEmpty()&&nested!=null)value=nested.optString("message");
            if(value.isEmpty())throw new Exception("Agent did not return a message.");
            pendingPrompt="";lastAnswer=value;append("assistant",value);appendGeneratedFiles(answer);
            if(answer.has("error_code")&&!answer.optString("error_code").isEmpty())setStatus(answer.optString("error_code"));
        },true);
    }
    private void handleAgentOutcome(AgentRequestViewModel.Outcome outcome){
        if(outcome==null||activeRequestId.isEmpty()||!activeRequestId.equals(outcome.id)||isDestroyed())return;
        busy=outcome.running;if(chatUi!=null){chatUi.setBusy(busy);chatUi.setStreaming(outcome.running&&outcome.streaming&&!outcome.phase.isEmpty());chatUi.setPartialReply(outcome.running?outcome.partial:"");}
        if(outcome.running){setStatus(outcome.phase.isEmpty()?"Working…":outcome.phase+(outcome.partial.isEmpty()?"":" · provisional draft"));return;}
        agentRequests.reset();
        if(outcome.failure!=null){
            if(outcome.failure instanceof DragonApi.ApiError&&((DragonApi.ApiError)outcome.failure).status==401){api.clear();clearAccountView();loginScreen("Session expired. Sign in again.");return;}
            pendingPrompt="";if(restorePending)applyRestoredDraft();
            append("system","Request outcome is unconfirmed. Use Check request status before sending another agent action.");
            setStatus("Request status unconfirmed");return;
        }
        JSONObject answer=outcome.response;
        if(answer==null||!activeRequestId.equals(answer.optString("request_id"))||answer.optString("conversation_id").isEmpty()||answer.optString("message").isEmpty()){
            pendingPrompt="";if(restorePending)applyRestoredDraft();setStatus("Response incomplete. Check request status.");return;
        }
        clearTrackedRequest();pendingPrompt="";attachment=null;attachmentName="";if(chatUi!=null)chatUi.setAttachmentLabel("");
        String completedConversation=answer.optString("conversation_id");
        if(restorePending){interruptedRequest=false;open(completedConversation);return;}
        conversation=completedConversation;lastAnswer=answer.optString("message");append("assistant",lastAnswer);appendGeneratedFiles(answer);appendExecutionReceipt(answer);setStatus("Personal agent");
    }
    private void appendExecutionReceipt(JSONObject answer){
        JSONObject receipt=answer.optJSONObject("execution_receipts");
        if(receipt==null)return;
        JSONArray names=receipt.optJSONArray("tool_names");
        StringBuilder summary=new StringBuilder("Server-reported execution");
        if(names!=null&&names.length()>0){
            summary.append("\nTools: ");
            for(int i=0;i<Math.min(names.length(),40);i++){if(i>0)summary.append(", ");summary.append(names.optString(i));}
        }
        if(receipt.has("failed_tool_count"))summary.append("\nFailed tools: ").append(receipt.optInt("failed_tool_count"));
        if(receipt.has("artifact_readback_count"))summary.append("\nArtifact readbacks: ").append(receipt.optInt("artifact_readback_count"));
        summary.append("\nObjective verified: ").append(receipt.optBoolean("objective_verified")?"Yes":"No");
        append("receipt",summary.toString());
    }
    private void clearTrackedRequest(){
        if(pendingAgentStore!=null&&!activeRequestId.isEmpty())pendingAgentStore.clear(api.pendingRequestBinding(),activeRequestId);
        activeRequestId="";
    }
    private boolean cancelAgentInFlight;
    private void cancelActiveAgent(){
        if(cancelAgentInFlight||activeRequestId.isEmpty())return;
        final String id=activeRequestId;
        cancelAgentInFlight=true;setStatus("Requesting server cancellation…");
        worker.execute(()->{
            JSONObject result=null;Exception failure=null;
            try{result=api.cancelAgent(id);}catch(Exception error){failure=error;}
            final JSONObject value=result;final Exception error=failure;
            runOnUiThread(()->{
                cancelAgentInFlight=false;
                if(isDestroyed()||!id.equals(activeRequestId))return;
                if(error!=null){setStatus("Cancellation not confirmed. Check request status.");return;}
                setStatus(value.optBoolean("cancel_requested")?"Cancellation requested; earlier effects may remain.":"Server status: "+value.optString("status","unknown"));
            });
        });
    }
    private void showUnresolvedAgentRequest(){
        alert().setTitle("Previous request is unresolved").setMessage("The previous agent action may have run. Check its server status before sending again. Dismissing this warning does not cancel server work.")
            .setPositiveButton("Check status",(d,i)->checkAgentRequest())
            .setNegativeButton("Keep waiting",null)
            .setNeutralButton("Dismiss warning",(d,i)->alert().setTitle("Dismiss request tracking?").setMessage("This does not undo actions or stop execution. Do not resend an action unless you verify its outcome independently.").setNegativeButton("Cancel",null).setPositiveButton("Dismiss",(dd,j)->{clearTrackedRequest();agentRequests.reset();setStatus("Request tracking dismissed");}).show()).show();
    }
    private void checkAgentRequest(){
        if(activeRequestId.isEmpty()){setStatus("No unresolved agent request.");return;}
        final String id=activeRequestId;
        submit("Checking request status…",()->api.requestStatus(id),r->{
            JSONObject record=(JSONObject)r;
            if(!id.equals(record.optString("request_id")))throw new Exception("Request status mismatch.");
            if("completed".equals(record.optString("status"))){
                JSONObject answer=record.optJSONObject("response");
                if(answer==null||!id.equals(answer.optString("request_id"))||answer.optString("conversation_id").isEmpty())throw new Exception("Completed response unavailable.");
                clearTrackedRequest();pendingPrompt="";interruptedRequest=false;agentRequests.reset();open(answer.optString("conversation_id"));
            }else{if(restorePending)applyRestoredDraft();setStatus("Server request: "+record.optString("status","unknown")+" — do not replay.");}
        },true);
    }
    private void loadHistory(boolean restore){
        submit("Loading conversations…",()->api.call("/api/personal-agent/conversations",null),r->{
            history=(JSONArray)r;
            if(!restore)return;
            String selected="";
            if(restorePending&&!restoredConversation.isEmpty()){
                for(int i=0;i<history.length();i++){
                    JSONObject item=history.optJSONObject(i);
                    if(item!=null&&restoredConversation.equals(item.optString("id"))){selected=restoredConversation;break;}
                }
            }
            if(!restorePending&&selected.isEmpty()&&history.length()>0){
                JSONObject first=history.optJSONObject(0);
                if(first!=null)selected=first.optString("id");
            }
            if(!selected.isEmpty())open(selected);
            else {boolean missing=restorePending&&!restoredConversation.isEmpty();applyRestoredDraft();if(missing)setStatus("Previous conversation unavailable. Draft retained in a new chat.");}
        },true);
    }
    private void applyRestoredDraft(){
        if(restorePending&&chatUi!=null)chatUi.setDraft(restoredDraft);
        // History loading clears the transcript. Surface the warning only after restoration,
        // including when history loading fails, so it cannot silently disappear.
        if(interruptedRequest&&chatUi!=null){
            append("system","A request was interrupted when Android recreated this screen. Its server-side outcome is unknown. Review conversation history and tasks before sending another action.");
            interruptedRequest=false;
        }
        restorePending=false;restoredDraft="";restoredConversation="";
    }
    @Override protected void onSaveInstanceState(Bundle out){
        // The draft is user-authored; never store passwords, credentials, or request payloads.
        out.putString("dz.conversation",conversation);
        out.putString("dz.request_id",activeRequestId);
        out.putBoolean("dz.mesh",meshMode);out.putString("dz.model",model);out.putBoolean("dz.model_images",modelAcceptsImages);
        out.putString("dz.draft",chatUi!=null?chatUi.getDraft():restoredDraft);
        // Marker only, never the prompt or credentials. Prevent implied completion or automatic replay.
        out.putBoolean("dz.request_in_flight",(busy&&!pendingPrompt.isEmpty())||!activeRequestId.isEmpty());
        super.onSaveInstanceState(out);
    }
    private void showHistory(){
        submit("Loading conversations…",()->api.call("/api/personal-agent/conversations",null),r->{
            history=(JSONArray)r;String[] labels=new String[history.length()];
            for(int i=0;i<labels.length;i++)labels[i]=history.getJSONObject(i).optString("title","Conversation");
            alert().setTitle("Conversations").setItems(labels,(d,i)->{JSONObject c=history.optJSONObject(i);if(c!=null)open(c.optString("id"));}).setNegativeButton("Close",null).show();
        },true);
    }
    private void open(String id){
        if(busy||id.isEmpty())return;
        submit("Loading chat…",()->api.call("/api/personal-agent/conversations/"+DragonApi.segment(id)+"/messages",null),r->{
            meshMode=false;model="";modelAcceptsImages=false;attachment=null;attachmentName="";conversation=id;transcript.clear();if(chatUi!=null){chatUi.clearMessages();chatUi.setModeLabel("Agent");chatUi.setAttachmentLabel("");chatUi.setDraft("");}JSONArray rows=(JSONArray)r;
            for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&Arrays.asList("user","assistant").contains(item.optString("role")))append(item.optString("role"),item.optString("content"));}
            applyRestoredDraft();
        },true);
    }
    private void chooseModel(){
        submit("Loading models…",()->api.call("/mesh/models",null),r->{
            JSONArray models=((JSONObject)r).optJSONArray("chat");if(models==null||models.length()==0)throw new Exception("No chat models available.");
            String[] names=new String[models.length()];for(int i=0;i<names.length;i++)names[i]=models.getJSONObject(i).optString("name");
            alert().setTitle("AI Mesh models").setItems(names,(d,i)->{JSONObject selected=models.optJSONObject(i);if(selected==null||selected.optString("id").isEmpty()){setStatus("Invalid model selection.");return;}String nextModel=selected.optString("id");boolean acceptsImages=false;JSONArray inputs=selected.optJSONArray("inputs");if(inputs!=null)for(int j=0;j<inputs.length();j++)if("image".equals(inputs.optString(j)))acceptsImages=true;if(!meshMode||!nextModel.equals(model))switchMode(true,nextModel,acceptsImages);}).setNegativeButton("Close",null).show();
        },true);
    }
    private void approvals(){
        if(api.isFirstParty()){setStatus("Approval center is not yet exposed by the first-party API.");return;}
        submit("Loading approvals…",()->{
            LinkedHashMap<String,JSONObject> all=new LinkedHashMap<>();JSONArray unavailable=new JSONArray();
            for(String source:new String[]{"legacy","kernel"}){
                String prefix=source.equals("kernel")?"/api/kernel/personal/approvals":"/api/personal-tools/approvals";
                try{
                    JSONObject payload=(JSONObject)api.call(prefix+"?status=pending",null);
                    JSONArray rows=payload.optJSONArray("approvals");if(rows==null)throw new Exception("Invalid approvals response");
                    for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&!item.optString("id").isEmpty()){item.put("native_source",source);all.put(item.optString("id"),item);}}
                }catch(Exception failure){if(failure instanceof DragonApi.ApiError&&((DragonApi.ApiError)failure).status==401)throw failure;unavailable.put(source);}
            }return new JSONObject().put("rows",new JSONArray(all.values())).put("unavailable",unavailable);
        },r->{JSONObject data=(JSONObject)r;renderApprovals(data.getJSONArray("rows"),data.getJSONArray("unavailable"));},true);
    }
    private void renderApprovals(JSONArray rows,JSONArray unavailable){
        Dialog dialog=new Dialog(this);LinearLayout page=column();page.setPadding(dp(18),dp(20),dp(18),dp(12));page.setBackgroundColor(BG);
        page.addView(heading("Pending approvals",26));gap(page,10);page.addView(text("Review the exact action and arguments before allowing execution.",14,MUTED));gap(page,16);
        ScrollView area=new ScrollView(this);LinearLayout list=column();area.addView(list);page.addView(area,new LinearLayout.LayoutParams(-1,0,1));
        if(unavailable.length()>0)list.addView(text("Some approval sources are unavailable. Refresh before reviewing or executing actions. "+unavailable,14,MUTED));
        if(rows.length()==0&&unavailable.length()==0)list.addView(text("No Personal actions are waiting for approval.",14,MUTED));
        for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item==null)continue;
            LinearLayout card=column();GradientDrawable bg=surface(PANEL,16);bg.setStroke(dp(1),LINE);card.setBackground(bg);card.setPadding(dp(14),dp(14),dp(14),dp(14));
            card.addView(heading(item.optString("capability_id","Personal action"),18));gap(card,8);card.addView(text("Approval: "+item.optString("id"),12,MUTED));
            if(item.has("arguments_hash"))card.addView(text("Review hash: "+item.optString("arguments_hash"),12,MUTED));
            if(item.has("expires_at"))card.addView(text("Expires: "+item.optString("expires_at"),12,MUTED));
            gap(card,10);TextView arguments=text(item.optString("arguments","{}"),14,TEXT);arguments.setTextIsSelectable(true);card.addView(arguments);gap(card,15);
            LinearLayout actions=row();Button reject=button("Reject",()->confirmApproval(dialog,item,false));Button approve=primary("Approve exact action",()->confirmApproval(dialog,item,true));
            if(unavailable.length()>0){reject.setEnabled(false);approve.setEnabled(false);}actions.addView(reject,new LinearLayout.LayoutParams(0,-2,1));actions.addView(approve,new LinearLayout.LayoutParams(0,-2,2));card.addView(actions);list.addView(card);gap(list,12);
        }
        page.addView(button("Close",dialog::dismiss));dialog.setContentView(page);dialog.show();Window w=dialog.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setLayout(-1,-1);}
    }
    private void confirmApproval(Dialog dialog,JSONObject item,boolean approved){
        alert().setTitle(approved?"Approve exact action?":"Reject this action?").setMessage(item.optString("capability_id","Personal action")+"\n\n"+item.optString("arguments","{}")).setNegativeButton("Cancel",null).setPositiveButton(approved?"Approve and execute":"Reject",(d,i)->{
            dialog.dismiss();submit(approved?"Executing approved action…":"Rejecting action…",()->{
                String id=DragonApi.segment(item.getString("id"));boolean kernel="kernel".equals(item.optString("native_source"));
                if(approved&&!kernel&&(item.optString("capability_id").isEmpty()||item.optString("request_id").isEmpty()||item.optJSONObject("arguments")==null))throw new Exception("Approval is missing its original execution contract. Refresh and review again.");
                String root=kernel?"/api/kernel/personal/approvals/":"/api/personal-tools/approvals/";
                Object decision=api.call(root+id+"/decision",DragonApi.object("approved",approved));
                if(!approved)return DragonApi.object("decision","rejected");
                if(kernel)return api.call(root+id+"/execute",new JSONObject());
                JSONObject contract=decision instanceof JSONObject?(JSONObject)decision:item;
                String capability=item.getString("capability_id");
                if(!capability.equals(contract.optString("capability_id",capability))||!item.getString("request_id").equals(contract.optString("request_id",item.getString("request_id")))||!item.getString("id").equals(contract.optString("id",item.getString("id"))))throw new Exception("Approval contract changed; review server status before continuing.");
                JSONObject arguments=item.getJSONObject("arguments");
                JSONObject body=new JSONObject().put("goal","").put("arguments",arguments).put("request_id",item.getString("request_id")).put("approval_id",item.getString("id"));
                String conversation=item.optString("conversation_id");if(!conversation.isEmpty())body.put("conversation_id",conversation);
                return api.call("/api/personal-tools/"+DragonApi.segment(capability)+"/execute",body);
            },result->{
                JSONObject value=result instanceof JSONObject?(JSONObject)result:new JSONObject();
                String reported=value.optString("status",value.optString("decision","unspecified"));
                alert().setTitle(approved?"Execution result":"Decision recorded").setMessage("Server status: "+reported+"\n\n"+value.toString()).setPositiveButton("Close",null).show();
            },true);
        }).show();
    }
    private void showConnections(){
        if(api.isFirstParty()){showFirstPartyConnections();return;}
        submit("Checking connections…",()->api.call("/api/personal-connectors",null),result->{
            JSONArray rows=result instanceof JSONArray?(JSONArray)result:result instanceof JSONObject?((JSONObject)result).optJSONArray("connectors"):null;
            if(rows==null)throw new Exception("Connection catalog unavailable.");
            Dialog dialog=new Dialog(this);LinearLayout page=column();page.setPadding(dp(18),dp(20),dp(18),dp(12));page.setBackgroundColor(BG);
            page.addView(heading("Connections & tools",25));gap(page,8);
            page.addView(text("Manage services already authorized for your Personal account. Sign-in does not automatically grant access to connected services.",14,MUTED));gap(page,14);
            ScrollView area=new ScrollView(this);LinearLayout list=column();area.addView(list);page.addView(area,new LinearLayout.LayoutParams(-1,0,1));
            if(rows.length()==0)list.addView(text("No authorized connections returned. New provider authorization is not yet available in this Android preview.",14,MUTED));
            for(int i=0;i<rows.length();i++){
                JSONObject c=rows.optJSONObject(i);if(c==null)continue;String id=c.optString("id");if(id.isEmpty())continue;
                LinearLayout card=column();GradientDrawable skin=surface(PANEL,16);skin.setStroke(dp(1),LINE);card.setBackground(skin);card.setPadding(dp(14),dp(14),dp(14),dp(14));
                String name=c.optString("displayName",c.optString("provider","Connection"));
                card.addView(heading(name,18));gap(card,6);card.addView(text(c.optString("account","Account details unavailable"),14,MUTED));gap(card,8);card.addView(text(c.optString("healthStatus",c.optString("status","Status unavailable"))+" · "+(c.optBoolean("enabled")?"Enabled":"Not enabled"),13,TEXT));
                if(!c.optString("lastError").isEmpty())card.addView(text(c.optString("lastError"),13,MUTED));
                if(c.optJSONArray("capabilities")!=null)card.addView(text(c.optJSONArray("capabilities").toString(),13,MUTED));
                gap(card,12);LinearLayout buttons=row();
                buttons.addView(button("Test",()->{dialog.dismiss();submit("Testing connection…",()->api.call("/api/personal-connectors/"+DragonApi.segment(id)+"/test",new JSONObject()),r->alert().setTitle("Connection test result").setMessage(String.valueOf(r)).setPositiveButton("Refresh",(d,x)->showConnections()).setNegativeButton("Close",null).show(),true);}),new LinearLayout.LayoutParams(0,-2,1));
                buttons.addView(button("Disconnect",()->alert().setTitle("Disconnect "+name+"?").setMessage("Your agents will lose this connection's authorization.").setNegativeButton("Cancel",null).setPositiveButton("Disconnect",(d,x)->{dialog.dismiss();submit("Disconnecting…",()->api.call("/api/personal-connectors/"+DragonApi.segment(id),"DELETE",new JSONObject()),r->showConnections(),true);}).show()),new LinearLayout.LayoutParams(0,-2,1));
                card.addView(buttons);list.addView(card);gap(list,12);
            }
            page.addView(button("Browse available tools",()->{dialog.dismiss();showTools();}));page.addView(button("Close",dialog::dismiss));dialog.setContentView(page);dialog.show();Window w=dialog.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setLayout(-1,-1);}
        },true);
    }
    private void showFirstPartyConnections(){
        submit("Loading authorized MCP accounts…",()->api.call("/dz/internal/mcp/connections",null),result->{
            if(!(result instanceof JSONObject))throw new Exception("Invalid connection catalog");
            JSONArray rows=((JSONObject)result).optJSONArray("connections");
            if(rows==null)throw new Exception("Connection catalog unavailable");
            LinkedHashSet<String> active=new LinkedHashSet<>();
            ArrayList<String> aliases=new ArrayList<>(),labels=new ArrayList<>();
            for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item==null||!"active".equals(item.optString("status")))continue;String alias=item.optString("connection_id");if(alias.isEmpty()||!active.add(alias))continue;aliases.add(alias);labels.add(item.optString("label",item.optString("provider_id","Connection")));}
            selectedMcpConnections.retainAll(active);
            boolean[] checked=new boolean[aliases.size()];for(int i=0;i<checked.length;i++)checked[i]=selectedMcpConnections.contains(aliases.get(i));
            AlertDialog.Builder picker=alert().setTitle("MCP accounts for this session");
            if(aliases.isEmpty())picker.setMessage("No active accounts returned. Connect a provider in the website using the same DragonZpyder account, then refresh here.");
            else picker.setMultiChoiceItems(labels.toArray(new String[0]),checked,(dialog,i,on)->checked[i]=on);
            picker.setPositiveButton("Apply",(dialog,i)->{
                int count=0;for(boolean on:checked)if(on)count++;
                if(count>10){setStatus("Select at most ten accounts.");return;}
                selectedMcpConnections.clear();for(int j=0;j<checked.length;j++)if(checked[j])selectedMcpConnections.add(aliases.get(j));setStatus(selectedMcpConnections.size()+" MCP accounts selected");
            }).setNeutralButton("Manage accounts",(dialog,i)->manageFirstPartyMcp(rows)).setNegativeButton("Cancel",null).show();
        },true);
    }
    private void manageFirstPartyMcp(JSONArray rows){
        ArrayList<String> labels=new ArrayList<>(),aliases=new ArrayList<>();
        for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item==null||!"active".equals(item.optString("status")))continue;String alias=item.optString("connection_id");if(!alias.matches("c[a-f0-9]{30}"))continue;aliases.add(alias);labels.add(item.optString("label",item.optString("provider_id","Connection")));}
        labels.add("Connect a provider");labels.add("Complete pending connection");labels.add("Manage on website");
        alert().setTitle("Manage MCP accounts").setItems(labels.toArray(new String[0]),(d,i)->{
            if(i==aliases.size()){chooseMcpProvider();return;}
            if(i==aliases.size()+1){completeMcpConnection();return;}
            if(i==aliases.size()+2){try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://dragonzpyder.xyz/app")));}catch(Exception unavailable){setStatus("Browser unavailable.");}return;}
            String alias=aliases.get(i);alert().setTitle("Disconnect "+labels.get(i)+"?").setMessage("This revokes the selected account's local agent authority.").setNegativeButton("Cancel",null).setPositiveButton("Disconnect",(dd,j)->submit("Disconnecting MCP account…",()->api.call("/dz/internal/mcp/connections/"+alias,"DELETE",null),r->{if(!((JSONObject)r).optBoolean("disconnected"))throw new Exception("Disconnection not confirmed");selectedMcpConnections.remove(alias);showFirstPartyConnections();},true)).show();
        }).setNegativeButton("Close",null).show();
    }
    private void chooseMcpProvider(){
        if(mcpOAuth.peek()!=null){
            alert().setTitle("A connection is pending").setMessage("Complete the current authorization or explicitly discard the local proof to start again.").setNegativeButton("Close",null).setPositiveButton("Complete",(d,i)->completeMcpConnection()).setNeutralButton("Discard",(d,i)->{mcpOAuth.clear();chooseMcpProvider();}).show();return;
        }
        submit("Loading reviewed providers…",()->api.call("/dz/internal/mcp/providers",null),r->{
            JSONArray providers=((JSONObject)r).optJSONArray("providers");if(providers==null)throw new Exception("Invalid provider catalog");
            ArrayList<JSONObject> items=new ArrayList<>();ArrayList<String> names=new ArrayList<>();
            for(int i=0;i<providers.length();i++){JSONObject p=providers.optJSONObject(i);if(p==null||!p.optString("provider_id").matches("[a-z][a-z0-9_-]{1,30}"))continue;items.add(p);names.add(p.optString("provider_id"));}
            if(items.isEmpty()){setStatus("No reviewed MCP providers are available.");return;}
            alert().setTitle("Connect a provider").setItems(names.toArray(new String[0]),(d,i)->{
                JSONObject p=items.get(i);JSONArray scopes=p.optJSONArray("requested_scopes");String name=p.optString("provider_id");
                alert().setTitle("Authorize "+name+"?").setMessage(p.optString("description")+"\n\nRequested scopes: "+(scopes==null?"Unavailable":scopes.toString())+"\n\nReview the provider consent screen in your browser.").setNegativeButton("Cancel",null).setPositiveButton("Continue",(dd,j)->beginMcpConnection(name)).show();
            }).setNegativeButton("Close",null).show();
        },true);
    }
    private void beginMcpConnection(String provider){
        final String verifier=MobileOAuthStore.randomToken();
        submit("Preparing secure provider authorization…",()->{
            JSONObject response=(JSONObject)api.call("/dz/internal/mcp/connections/"+DragonApi.segment(provider)+"/native/start",new JSONObject().put("code_challenge",MobileOAuthStore.challenge(verifier)).put("label",""));
            String state=response.getString("state");String url=response.getString("authorization_url");
            java.net.URI target=new java.net.URI(url);
            if(!"https".equalsIgnoreCase(target.getScheme())||target.getHost()==null||target.getRawUserInfo()!=null||url.length()>8192)throw new Exception("Invalid provider authorization URL");
            if(!state.equals(android.net.Uri.parse(url).getQueryParameter("state")))throw new Exception("Provider authorization state mismatch");
            mcpOAuth.begin(state,verifier);return url;
        },r->{
            try{new androidx.browser.customtabs.CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(this,android.net.Uri.parse((String)r));setStatus("Authorize in the browser, then return and choose Complete pending connection.");}
            catch(Exception unavailable){mcpOAuth.clear();throw new Exception("Secure browser unavailable.");}
        },true);
    }
    private void completeMcpConnection(){
        final String[] proof=mcpOAuth.peek();
        if(proof==null){setStatus("No valid pending connection. Start a new authorization.");return;}
        submit("Completing provider connection…",()->api.call("/dz/internal/mcp/connections/native/complete",new JSONObject().put("state",proof[0]).put("verifier",proof[1])),r->{
            JSONObject account=(JSONObject)r;
            if(!"active".equals(account.optString("status"))||!account.optString("connection_id").matches("c[a-f0-9]{30}"))throw new Exception("Connection was not confirmed.");
            mcpOAuth.clear();showFirstPartyConnections();
        },true);
    }
    private void showTools(){
        if(api.isFirstParty()){showConnections();return;}
        submit("Discovering tools…",()->api.call("/api/personal-tools",null),r->{
            JSONArray tools=((JSONObject)r).optJSONArray("tools");if(tools==null)throw new Exception("Capability catalog unavailable.");
            String[] labels=new String[tools.length()];for(int i=0;i<labels.length;i++){JSONObject item=tools.getJSONObject(i);labels[i]=item.optString("name",item.optString("id","Capability"));}
            alert().setTitle("Your tools").setItems(labels,(d,i)->{
                JSONObject t=tools.optJSONObject(i);if(t==null)return;
                alert().setTitle(labels[i]).setMessage(t.optString("description")+"\n\nRisk: "+t.optString("risk","Policy-controlled")+"\nApproval: "+(t.optBoolean("approval_required")?"Required":"Determined by policy")).setPositiveButton("Close",null).show();
            }).setNegativeButton("Close",null).show();
        },true);
    }
    private JSONObject workflowRead(String id) throws Exception {
        JSONObject result=(JSONObject)api.call("/api/personal-tools/"+DragonApi.segment(id)+"/execute",new JSONObject().put("arguments",DragonApi.object("limit",100)).put("goal","View my Personal workflow activity"));
        if(!result.optBoolean("done",false)||"failed".equals(result.optString("status")))throw new Exception("Unable to read workflow record.");
        JSONObject payload=result.optJSONObject("result");if(payload==null)throw new Exception("Workflow response was incomplete.");JSONObject value=payload.optJSONObject("value");return value==null?payload:value;
    }
    private void showFirstPartyGoals(){
        submit("Loading persistent goals…",()->api.call("/dz/v2/personal/goals",null),r->{
            JSONArray goals=((JSONObject)r).optJSONArray("goals");if(goals==null)throw new Exception("Invalid goal catalog");
            ArrayList<String> labels=new ArrayList<>(),ids=new ArrayList<>();
            for(int i=0;i<goals.length();i++){JSONObject g=goals.optJSONObject(i);if(g==null||g.optString("goal_id").isEmpty())continue;
                ids.add(g.getString("goal_id"));labels.add(g.optString("state","Unknown")+" · "+g.optInt("completed_wakes")+"/"+g.optInt("total_wakes")+" wakes\n"+g.optString("updated_at",""));
            }
            if(ids.isEmpty()){alert().setTitle("Persistent goals").setMessage("No goals returned for this account.").setPositiveButton("Close",null).show();return;}
            alert().setTitle("Persistent goals").setItems(labels.toArray(new String[0]),(d,i)->showFirstPartyGoal(ids.get(i))).setNegativeButton("Close",null).show();
        },true);
    }
    private void showFirstPartyGoal(String goalId){
        final String path="/dz/v2/personal/goals/"+DragonApi.segment(goalId);
        submit("Loading goal receipts…",()->api.call(path,null),r->{
            JSONObject g=(JSONObject)r;String state=g.optString("state","Unknown");
            StringBuilder details=new StringBuilder("State: ").append(state).append("\nWakes: ").append(g.optInt("completed_wakes")).append("/").append(g.optInt("total_wakes"));
            if("blocked".equals(state))details.append("\nReason: ").append(g.optString("blocked_reason","Unavailable"));
            JSONArray receipts=g.optJSONArray("receipts");if(receipts==null)throw new Exception("Goal receipts unavailable");
            for(int i=0;i<receipts.length();i++){JSONObject item=receipts.optJSONObject(i);if(item!=null)details.append("\n\nWake ").append(item.optInt("sequence")+1).append(": ").append(item.optString("status")).append("\n").append(item.optString("tool_names","")).append("\n").append(item.optString("at",""));}
            AlertDialog.Builder dialog=alert().setTitle("Goal details").setMessage(details.toString()).setPositiveButton("Refresh",(d,i)->showFirstPartyGoal(goalId)).setNegativeButton("Close",null);
            if("active".equals(state)||"preparing".equals(state))dialog.setNeutralButton("Cancel goal",(d,i)->alert().setTitle("Cancel persistent goal?").setMessage("Future queued wakes will stop. Already executed actions are not undone.").setNegativeButton("Keep goal",null).setPositiveButton("Cancel goal",(dd,j)->submit("Cancelling goal…",()->api.call(path+"/cancel",new JSONObject()),result->{JSONObject cancelled=(JSONObject)result;if(!"cancelled".equals(cancelled.optString("state")))throw new Exception("Cancellation not confirmed");showFirstPartyGoal(goalId);},true)).show());
            dialog.show();
        },true);
    }
    private void showTasks(){
        if(api.isFirstParty()){if(api.supportsGoals())showFirstPartyGoals();else setStatus("Persistent goals are not enabled for this session.");return;}
        submit("Loading Personal workflows…",()->{
            JSONObject catalog=(JSONObject)api.call("/api/personal-tools?query=workflow&limit=100",null);
            JSONArray rows=catalog.optJSONArray("tools");HashSet<String> ids=new HashSet<>();if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject t=rows.optJSONObject(i);if(t!=null)ids.add(t.optString("id"));}
            if(!ids.contains("workflow.list"))throw new Exception("Workflow discovery is unavailable for this Personal session.");
            JSONObject definitions=workflowRead("workflow.list");JSONObject activity=ids.contains("workflow.run.list")?workflowRead("workflow.run.list"):new JSONObject();
            return new JSONObject().put("definitions",definitions).put("activity",activity);
        },r->{JSONObject data=(JSONObject)r;JSONArray workflows=data.getJSONObject("definitions").optJSONArray("workflows");JSONArray runs=data.getJSONObject("activity").optJSONArray("runs");
            StringBuilder content=new StringBuilder("WORKFLOWS\n");if(workflows==null)content.append("Workflow records unavailable.\n");else if(workflows.length()==0)content.append("No workflows returned.\n");
            else for(int i=0;i<workflows.length();i++){JSONObject w=workflows.optJSONObject(i);if(w!=null)content.append(w.optString("name",w.optString("id"))).append(" · ").append(w.optString("status",w.optBoolean("enabled")?"Enabled":"Unknown")).append("\n");}
            content.append("\nRECENT RUNS\n");if(runs==null)content.append("Run records unavailable.");else if(runs.length()==0)content.append("No runs returned.");else for(int i=0;i<runs.length();i++){JSONObject run=runs.optJSONObject(i);if(run!=null)content.append(run.optString("workflow_name",run.optString("workflow_id","Run"))).append(" · ").append(run.optString("status","Unknown")).append("\n");}
            alert().setTitle("Personal tasks").setMessage(content.toString()).setPositiveButton("Close",null).show();
        },true);
    }
    private void showVoice(){
        if(!signedIn||busy||!api.supportsVoice()){setStatus("Live voice is unavailable for this session.");return;}
        new android.app.AlertDialog.Builder(this).setTitle("Live voice")
            .setMessage("Microphone audio is sent to the realtime voice provider. This session is audio-only, has no external tool access, and closes when you leave the app.")
            .setNegativeButton("Cancel",null).setPositiveButton("Start",(d,w)->{
                if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED){
                    voicePermissionPending=true;requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO},79);
                }else startVoice();
            }).show();
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants){
        super.onRequestPermissionsResult(code,permissions,grants);
        if(code==79&&voicePermissionPending){
            voicePermissionPending=false;
            if(grants.length>0&&grants[0]==android.content.pm.PackageManager.PERMISSION_GRANTED){
                if(getLifecycle().getCurrentState().isAtLeast(androidx.lifecycle.Lifecycle.State.RESUMED))startVoice();
                else voiceStartOnResume=true;
            }else setStatus("Microphone permission not granted.");
        }
    }
    @Override protected void onPostResume(){
        super.onPostResume();
        if(voiceStartOnResume){voiceStartOnResume=false;startVoice();}
    }
    private void startVoice(){
        if(!signedIn||busy||!api.supportsVoice()||nativeVoice!=null||isFinishing())return;
        final android.app.Dialog dialog=new android.app.Dialog(this,android.R.style.Theme_Material_NoActionBar);
        final NativeVoiceView screen=new NativeVoiceView(this,new NativeVoiceView.Actions(){
            public void mute(boolean muted){if(nativeVoice!=null)nativeVoice.mute(muted);}
            public void end(){closeVoice();}
        });
        voiceDialog=dialog;
        androidx.lifecycle.ViewTreeLifecycleOwner.set(screen.getView(),this);
        androidx.lifecycle.ViewTreeViewModelStoreOwner.set(screen.getView(),this);
        androidx.savedstate.ViewTreeSavedStateRegistryOwner.set(screen.getView(),this);
        dialog.setContentView(screen.getView());
        dialog.setOnDismissListener(d->{if(voiceDialog==dialog)closeVoice();});
        dialog.show();
        if(dialog.getWindow()!=null)dialog.getWindow().setLayout(-1,-1);
        nativeVoice=new NativeVoiceSession(this,api,value->{if(!isDestroyed()&&voiceDialog==dialog)screen.setStatus(value);});
        nativeVoice.start();
    }
    private void closeVoice(){
        voiceStartOnResume=false;
        NativeVoiceSession session=nativeVoice;nativeVoice=null;
        if(session!=null)session.close();
        android.app.Dialog dialog=voiceDialog;voiceDialog=null;
        if(dialog!=null&&dialog.isShowing())dialog.dismiss();
    }
    @Override protected void onStop(){closeVoice();super.onStop();}
    private void dictate(){
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak to DragonZpyder");
        try{startActivityForResult(intent,42);}
        catch(android.content.ActivityNotFoundException e){setStatus("No speech recognition service available.");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==47){if(signedIn&&result==RESULT_OK&&data!=null&&data.getData()!=null)uploadAgentAttachment(data.getData());return;}if(request==48){JSONObject file=pendingFileDownload;pendingFileDownload=null;if(signedIn&&result==RESULT_OK&&data!=null&&data.getData()!=null)saveAgentFile(data.getData(),file);return;}if(request==45){if(signedIn&&meshMode&&result==RESULT_OK)attachCameraCapture();else discardCamera();return;}if(request==44){if(signedIn&&result==RESULT_OK&&data!=null&&data.getData()!=null)transcribeAudio(data.getData());else transcriptionModel="";return;}if(request==43&&signedIn&&meshMode&&result==RESULT_OK&&data!=null&&data.getData()!=null){readAttachment(data.getData());return;}if(request==42&&signedIn&&result==RESULT_OK&&data!=null&&chatUi!=null){ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty()){String draft=chatUi.getDraft();chatUi.setDraft(draft+(draft.isEmpty()?"":" ")+words.get(0));}}}
    @Override public void onBackPressed(){if(busy)return;if(accountOpen){accountOpen=false;chatScreen();}else if(!signedIn&&!"login".equals(authMode))authScreen("login","");else super.onBackPressed();}
    private void signOut(){submit("Signing out…",()->{try{api.logout();return Boolean.TRUE;}catch(Exception failure){api.clear();return Boolean.FALSE;}},r->{clearAccountView();loginScreen(Boolean.TRUE.equals(r)?"":"Signed out locally. Server sign-out could not be confirmed; revoke this session from another device if needed.");},true);}
    @Override protected void onDestroy(){closeVoice();discardCamera();stopMedia();api.cancelStream();worker.shutdownNow();if(tts!=null)tts.shutdown();super.onDestroy();}
}
