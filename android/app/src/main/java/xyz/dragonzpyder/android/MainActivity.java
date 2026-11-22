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
        BG=dark?0xff0e0f11:0xfffaf9f7; PANEL=dark?0xff242124:0xffffffff;
        TEXT=dark?0xfff6f4f1:0xff24221f; MUTED=dark?0xffc2b8b0:0xff70665f;
        ACCENT=dark?0xffff8a50:0xffb94a21; LINE=dark?0xff665047:0xffe1dad2;
        SIDEBAR=dark?0xff141416:0xfff3f1ee; CHIP=dark?0xff1a191c:0xfff6f3ef;
        USER=dark?0xff222922:0xffeeebe6; COMPOSER=PANEL;
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }
    private void toggleTheme(){
        dark=!dark;
        getPreferences(MODE_PRIVATE).edit().putBoolean("dark",dark).apply();palette();
        if(signedIn){if(accountOpen)showAccount();else chatScreen();}else authScreen(authMode,"");
    }
    private NativeChatView chatUi;
    private static final DragonApi api=new DragonApi();
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private LinearLayout root;
    private TextView status;
    private JSONObject attachment;
    private String attachmentName="";
    private String conversation="", lastAnswer="", pendingPrompt="";
    // Non-sensitive Activity recreation state; never persist auth tokens or replay a request.
    private String restoredConversation="", restoredDraft="";
    private boolean restorePending=false;
    private JSONArray history=new JSONArray();
    private boolean busy, signedIn, meshMode;
    private String model="";
    private JSONArray meshMessages=new JSONArray();
    private TextToSpeech tts;
    private boolean speechReady;
    interface Work { Object run() throws Exception; }
    interface Done { void accept(Object result) throws Exception; }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        if(b!=null){
            restoredConversation=b.getString("dz.conversation","");
            restoredDraft=b.getString("dz.draft","");
            restorePending=true;
        }
        dark=getPreferences(MODE_PRIVATE).getBoolean("dark",false);palette();
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        tts=new TextToSpeech(this, code -> speechReady=code==TextToSpeech.SUCCESS);
        loginScreen("");
        submit("Checking secure session…",()->api.restore(getApplicationContext()),result->{
            if(Boolean.TRUE.equals(result)){signedIn=true;chatScreen();loadHistory(true);}
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
    private Button primary(String s,Runnable action){Button b=button(s,action);b.setTextColor(Color.WHITE);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22000000),surface(0xffb94a21,11),null));return b;}
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
    private void authSuccess(){restorePending=false;restoredDraft="";restoredConversation="";authEmail="";challengeId="";signedIn=true;accountOpen=false;chatScreen();loadHistory(true);}
    private void authScreen(String mode,String message){
        signedIn=false;accountOpen=false;chatUi=null;authMode=mode;getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);accountLayout();
        sectionLabel(accountPage,"ONE IDENTITY · YOUR INTELLIGENCE");accountPage.addView(heading("Always yours.",38));gap(accountPage,8);accountPage.addView(text("Your conversations, personal AI, and authorised connections—all in one account.",14,MUTED));gap(accountPage,22);
        LinearLayout card=accountCard();
        if(mode.equals("login")||mode.equals("signup")){
            LinearLayout tabs=row();Button sign=mode.equals("login")?primary("Sign in",()->authScreen("login","")):button("Sign in",()->authScreen("login",""));Button create=mode.equals("signup")?primary("Create account",()->authScreen("signup","")):button("Create account",()->authScreen("signup",""));
            tabs.addView(sign,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams tab=new LinearLayout.LayoutParams(0,-2,1);tab.setMargins(dp(6),0,0,0);tabs.addView(create,tab);card.addView(tabs);gap(card,22);
        }
        String title=mode.equals("signup")?"Create your account.":mode.equals("verify")?"Verify your email.":mode.equals("forgot")?"Reset your password.":mode.equals("reset")?"Set a new password.":"Welcome back.";
        card.addView(heading(title,27));gap(card,6);card.addView(text(mode.equals("signup")?"Start personal. Connect workspaces when you choose.":mode.equals("verify")?"Enter the six-digit code emailed to you.":mode.equals("forgot")?"We’ll email reset instructions if an account exists.":mode.equals("reset")?"Use the six-digit code from your password-reset email.":"Continue to your personal DragonZpyder.",14,MUTED));gap(card,20);
        status=text(message,13,message.isEmpty()?MUTED:TEXT);status.setLineSpacing(dp(2),1);card.addView(status);gap(card,8);
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
        if(mode.equals("login")){card.addView(button("Forgot password?",()->{authEmail=value(email);authScreen("forgot","");}));card.addView(button("Already have a verification code?",()->{authEmail=value(email);challengeId="";authScreen("verify","");}));}
        if(mode.equals("verify"))card.addView(button("Resend code",()->{String e=value(email);if(!emailValid(e))return;submit("Requesting code…",()->api.preauth("resend-verification",DragonApi.object("email",e)),r->setStatus("If verification is pending, another code is on its way."),true);}));
        if(mode.equals("forgot"))card.addView(button("I have a reset code",()->{authEmail=value(email);authScreen("reset","");}));
        if(!mode.equals("login")&&!mode.equals("signup"))card.addView(button("Back to sign in",()->authScreen("login","")));
        gap(accountPage,24);accountPage.addView(text("One account, clear boundaries. Personal access does not grant business permissions.",12,MUTED));
    }
    private void chatScreen(){
        String draft=chatUi==null?"":chatUi.getDraft();accountOpen=false;getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);reset();status=null;
        chatUi=new NativeChatView(this,dark,new NativeChatView.Actions(){
            public void menu(){showMenu();}
            public void commands(){showCommands();}
            public void theme(){toggleTheme();}
            public void account(){showAccount();}
            public void add(){showAdd();}
            public void mode(){showModes();}
            public void dictate(){MainActivity.this.dictate();}
            public void send(){MainActivity.this.send();}
            public void stop(){api.cancelStream();setStatus("Stopping reply…");}
            public void removeAttachment(){if(!busy){attachment=null;attachmentName="";chatUi.setAttachmentLabel("");}}
            public void copy(String value){android.content.ClipboardManager cb=(android.content.ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);cb.setPrimaryClip(android.content.ClipData.newPlainText("DragonZpyder",value));}
            public void speak(String value){if(speechReady)tts.speak(value,TextToSpeech.QUEUE_FLUSH,null,"response");else setStatus("Speech engine unavailable");}
        });
        chatUi.setDraft(draft);chatUi.setModeLabel(meshMode?"AI Mesh":"Agent");chatUi.setModelLabel(model);chatUi.setAttachmentLabel(attachmentName);chatUi.setProfileInitial(profileInitial);chatUi.setBusy(busy);
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
        if(busy)return;
        Dialog drawer=new Dialog(this);LinearLayout sidebar=column();
        sidebar.setPadding(dp(12),dp(12),dp(12),dp(8));sidebar.setBackgroundColor(SIDEBAR);
        LinearLayout brand=row();brand.addView(logo(29));TextView title=heading("DragonZpyder",18);LinearLayout.LayoutParams tp=new LinearLayout.LayoutParams(0,-2,1);tp.setMargins(dp(9),0,0,0);brand.addView(title,tp);
        Button close=button("×",drawer::dismiss);close.setContentDescription("Close sidebar");brand.addView(close,new LinearLayout.LayoutParams(dp(48),dp(48)));sidebar.addView(brand);gap(sidebar,12);
        Button newChat=primary("＋ New chat",()->{drawer.dismiss();newChat();});sidebar.addView(newChat);gap(sidebar,8);
        sidebar.addView(navRow("⌘","Connections & tools",false,()->{drawer.dismiss();showConnections();}));
        sidebar.addView(navRow("◎","Account & security",false,()->{drawer.dismiss();showAccount();}));
        gap(sidebar,10);EditText search=field("Find conversations",false);search.setSingleLine(true);search.setContentDescription("Find conversations");sidebar.addView(search);gap(sidebar,14);
        TextView label=text("YOUR CONVERSATIONS",10,MUTED);label.setLetterSpacing(.10f);label.setPadding(dp(10),0,0,dp(6));sidebar.addView(label);
        ScrollView listScroll=new ScrollView(this);LinearLayout list=column();listScroll.addView(list);sidebar.addView(listScroll,new LinearLayout.LayoutParams(-1,0,1));
        Runnable filter=()->{
            list.removeAllViews();String query=search.getText().toString().toLowerCase(Locale.ROOT);int count=0;
            for(int i=0;i<history.length();i++){JSONObject c=history.optJSONObject(i);if(c==null)continue;
                String name=c.optString("title","Conversation");if(!name.toLowerCase(Locale.ROOT).contains(query))continue;String id=c.optString("id");
                TextView entry=navRow("",name,id.equals(conversation),()->{drawer.dismiss();open(id);});entry.setText(name);entry.setMaxLines(2);list.addView(entry);count++;
            }
            if(count==0){TextView empty=text(query.isEmpty()?"No conversations to show.":"No matching conversations.",13,MUTED);empty.setPadding(dp(10),dp(10),dp(10),dp(10));list.addView(empty);}
        };
        search.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){filter.run();}public void afterTextChanged(android.text.Editable e){}});
        filter.run();
        View rule=new View(this);rule.setBackgroundColor(LINE);sidebar.addView(rule,new LinearLayout.LayoutParams(-1,dp(1)));
        LinearLayout footer=row();footer.addView(navRow("◷","Tasks",false,()->{drawer.dismiss();showTasks();}),new LinearLayout.LayoutParams(0,dp(48),1));
        footer.addView(navRow("◇","Approvals",false,()->{drawer.dismiss();approvals();}),new LinearLayout.LayoutParams(0,dp(48),1));sidebar.addView(footer);
        sidebar.addView(navRow("▦","More commands",false,()->{drawer.dismiss();showCommands();}));
        drawer.setContentView(sidebar);drawer.show();Window w=drawer.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setGravity(Gravity.START|Gravity.TOP);w.setLayout(Math.min(dp(320),(int)(getResources().getDisplayMetrics().widthPixels*.88)), -1);w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);}
        worker.execute(()->{try{JSONArray refreshed=(JSONArray)api.call("/api/personal-agent/conversations",null);runOnUiThread(()->{if(!isDestroyed()&&signedIn){history=refreshed;if(drawer.isShowing())filter.run();}});}catch(Exception e){runOnUiThread(()->{if(!isDestroyed()&&drawer.isShowing())label.setText("CONVERSATIONS · REFRESH FAILED");});}});
    }
    private void showAccount(){
        submit("Loading account…",()->{
            JSONObject p=api.profile();p.put("native_sessions",api.call("/api/auth/sessions",null));
            try{p.put("native_workspaces",api.call("/api/auth/workspaces",null));}catch(Exception ignored){p.put("workspaces_unavailable",true);}
            return p;
        },r->renderAccount((JSONObject)r),true);
    }
    private void renderAccount(JSONObject p){
        accountOpen=true;getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);accountLayout();
        accountPage.addView(button("‹ Back to Personal AI",()->{accountOpen=false;chatScreen();}));gap(accountPage,20);
        sectionLabel(accountPage,"YOUR DRAGONZPYDER");accountPage.addView(heading("Account & connections.",30));gap(accountPage,8);accountPage.addView(text("One identity, with clear boundaries around every connected service and workspace.",14,MUTED));gap(accountPage,20);
        LinearLayout profile=accountCard();sectionLabel(profile,"01 / IDENTITY");profile.addView(heading("Your profile",21));gap(profile,8);profile.addView(text(p.optString("email"),14,MUTED));gap(profile,16);
        String current=p.optString("display_name");if(!current.isEmpty())profileInitial=current.substring(0,1).toUpperCase(Locale.ROOT);EditText name=accountField(profile,"Display name",current,1,View.AUTOFILL_HINT_NAME);
        status=text("",13,MUTED);profile.addView(status);profile.addView(primary("Save changes",()->{String n=value(name);if(n.isEmpty()||n.length()>200){setStatus("Enter a display name up to 200 characters.");return;}submit("Saving…",()->{api.updateName(n);return api.profile();},result->{JSONObject saved=(JSONObject)result;p.put("display_name",saved.optString("display_name",n));renderAccount(p);setStatus("Your account has been updated.");},true);}));
        gap(accountPage,14);LinearLayout identity=accountCard();sectionLabel(identity,"02 / ACCESS");identity.addView(heading("Sign-in methods",21));gap(identity,8);
        JSONArray ids=p.optJSONArray("auth_identities");if(ids!=null)for(int i=0;i<ids.length();i++){JSONObject item=ids.optJSONObject(i);if(item!=null){identity.addView(text(item.optString("provider")+(item.optString("account").isEmpty()?"":" · "+item.optString("account")),14,TEXT));gap(identity,8);}}
        if(ids==null||ids.length()==0)identity.addView(text("No sign-in methods returned.",13,MUTED));gap(identity,10);identity.addView(text("Connected tools require their own authorization. Signing in does not grant Gmail or Calendar access.",12,MUTED));
        gap(accountPage,14);LinearLayout sessions=accountCard();sectionLabel(sessions,"03 / SECURITY");sessions.addView(heading("Active sessions",21));gap(sessions,12);
        JSONArray list=p.optJSONArray("native_sessions");if(list!=null)for(int i=0;i<list.length();i++){JSONObject item=list.optJSONObject(i);if(item==null)continue;sessions.addView(text(item.optString("device","Session")+(item.optBoolean("current")?" · This device":""),14,TEXT));sessions.addView(text(item.optString("scope",""),12,MUTED));gap(sessions,12);}
        gap(accountPage,14);LinearLayout spaces=accountCard();sectionLabel(spaces,"04 / SCOPE");spaces.addView(heading("Your workspaces",21));gap(spaces,8);
        JSONArray work=p.optJSONArray("native_workspaces");if(p.optBoolean("workspaces_unavailable"))spaces.addView(text("Workspace information is unavailable.",13,MUTED));else if(work==null||work.length()==0)spaces.addView(text("No business workspaces attached to this account.",13,MUTED));else for(int i=0;i<work.length();i++){JSONObject w=work.optJSONObject(i);if(w!=null){spaces.addView(text(w.optString("name")+" · "+w.optString("role"),14,TEXT));gap(spaces,8);}}
        gap(accountPage,14);accountPage.addView(button("Manage connections & tools",this::showConnections));gap(accountPage,14);Button out=button("Sign out",this::confirmSignOut);out.setTextColor(dark?0xffffa59a:0xffb6382b);accountPage.addView(out);gap(accountPage,10);accountPage.addView(text("Signs out this device and clears its local conversation view. Your server conversations are retained.",12,MUTED));
    }
    private void confirmSignOut(){alert().setTitle("Sign out of DragonZpyder?").setMessage("You’ll need to sign in again to access your Personal workspace on this device.").setNegativeButton("Cancel",null).setPositiveButton("Sign out",(d,i)->signOut()).show();}
    private void showCommands(){
        Dialog sheet=new Dialog(this);LinearLayout page=column();page.setPadding(dp(16),dp(8),dp(16),dp(10));page.setBackground(surface(PANEL,24));
        View handle=new View(this);handle.setBackground(surface(LINE,3));LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(dp(32),dp(4));hp.gravity=Gravity.CENTER_HORIZONTAL;hp.bottomMargin=dp(14);page.addView(handle,hp);
        LinearLayout header=row();header.addView(heading("Commands",22),new LinearLayout.LayoutParams(0,-2,1));Button close=button("×",sheet::dismiss);close.setContentDescription("Close commands");header.addView(close,new LinearLayout.LayoutParams(dp(48),dp(48)));page.addView(header);
        page.addView(text("Find an action in your Personal workspace.",13,MUTED));gap(page,10);
        EditText search=field("Search commands",false);search.setSingleLine(true);page.addView(search);gap(page,8);
        ScrollView scroller=new ScrollView(this);LinearLayout list=column();scroller.addView(list);page.addView(scroller,new LinearLayout.LayoutParams(-1,0,1));
        String[] names={"New chat","Find conversations","Switch mode","Approvals","Dictate a message","Toggle appearance","Connections & tools","Personal tasks","AI Mesh media","Account & security","Your tools"};
        String[] icons={"＋","⌕","✦","◇","◉","☾","⌘","◷","▧","◎","▦"};
        Runnable[] actions={this::newChat,this::showMenu,this::showModes,this::approvals,this::dictate,this::toggleTheme,this::showConnections,this::showTasks,this::showMedia,this::showAccount,this::showTools};
        Runnable filter=()->{list.removeAllViews();String q=value(search).toLowerCase(Locale.ROOT);int count=0;for(int k=0;k<names.length;k++){final int n=k;if(names[k].toLowerCase(Locale.ROOT).contains(q)){list.addView(navRow(icons[k],names[k],false,()->{sheet.dismiss();actions[n].run();}));count++;}}if(count==0)list.addView(text("No matching commands.",14,MUTED));};
        search.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){filter.run();}public void afterTextChanged(android.text.Editable e){}});
        filter.run();page.setFocusableInTouchMode(true);page.requestFocus();
        sheet.setContentView(page);sheet.show();Window w=sheet.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setGravity(Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);w.setLayout(Math.min(getResources().getDisplayMetrics().widthPixels-dp(16),dp(520)),Math.min(dp(570),(int)(getResources().getDisplayMetrics().heightPixels*.78)));w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE|WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);}
    }
    private void showAdd(){
        if(!meshMode){setStatus("Choose a compatible AI Mesh model before attaching media.");chooseModel();return;}
        alert().setTitle("Add to your message").setItems(new String[]{"Attach a file or photo","Take a photo"},(d,i)->{
            if(i==1){
                Intent camera=new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                try{startActivityForResult(camera,45);}catch(android.content.ActivityNotFoundException e){setStatus("Camera app unavailable.");}
                return;
            }
            Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.setType("*/*");picker.addCategory(Intent.CATEGORY_OPENABLE);picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try{startActivityForResult(picker,43);}catch(android.content.ActivityNotFoundException e){setStatus("No file picker available.");}
        }).setNegativeButton("Close",null).show();
    }
    private void attachCameraPreview(Intent data){
        Bundle extras=data.getExtras();if(extras==null){setStatus("Camera returned no image.");return;}
        Object image=extras.get("data");if(!(image instanceof android.graphics.Bitmap)){setStatus("Camera returned no preview.");return;}
        android.graphics.Bitmap bitmap=(android.graphics.Bitmap)image;
        submit("Preparing photo…",()->{
            java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
            if(!bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG,90,out)||out.size()==0||out.size()>2500000)throw new Exception("Camera image could not be encoded");
            return new JSONObject().put("type","image_url").put("image_url",new JSONObject().put("url","data:image/jpeg;base64,"+android.util.Base64.encodeToString(out.toByteArray(),android.util.Base64.NO_WRAP)));
        },r->{attachment=(JSONObject)r;attachmentName="Camera photo";if(chatUi!=null)chatUi.setAttachmentLabel(attachmentName);},true);
    }
    private void readAttachment(android.net.Uri uri){
        submit("Preparing attachment…",()->{
            String mime=getContentResolver().getType(uri),name="attachment";
            try(android.database.Cursor c=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())name=c.getString(0);}
            if(name==null||name.isEmpty()||name.length()>120)throw new Exception("Unsupported filename");
            if(mime==null)mime="application/octet-stream";
            boolean image=Arrays.asList("image/jpeg","image/png","image/webp").contains(mime);
            String extension=name.toLowerCase(Locale.ROOT);
            if(!image&&!extension.matches(".*\\.(pdf|docx|txt|md|csv|json|py|log)$"))throw new Exception("Unsupported file format");
            int limit=extension.endsWith(".docx")?1000000:extension.matches(".*\\.(txt|md|csv|json|py|log)$")?250000:3*1024*1024;
            java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new Exception("Cannot read attachment");byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>limit)throw new Exception("Attachment exceeds size limit");out.write(buffer,0,n);}}
            if(out.size()==0)throw new Exception("Empty file");
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
    private void showModes(){alert().setTitle("Choose your intelligence").setItems(new String[]{"DragonZpyder Agent — tasks and tools","AI Mesh — choose a model"},(d,i)->{if(i==0){meshMode=false;newChat();}else chooseModel();}).show();}
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
                    if(e instanceof DragonApi.ApiError && ((DragonApi.ApiError)e).status==401 && signedIn){api.clear();pendingPrompt="";attachment=null;attachmentName="";transcript.clear();conversation="";meshMessages=new JSONArray();meshMode=false;loginScreen("Session expired. Sign in again.");}
                    else if(report){boolean hadPartial=chatUi!=null&&!chatUi.getPartialReply().isEmpty();if(hadPartial){append("assistant",chatUi.getPartialReply()+"\n\n[Reply incomplete]");chatUi.setPartialReply("");}if(!pendingPrompt.isEmpty()&&chatUi!=null){if(chatUi.getDraft().isEmpty()&&!hadPartial)chatUi.setDraft(pendingPrompt);append("system","Request did not return a confirmed completion. Check server history or tasks before resending an agent action.");pendingPrompt="";}setStatus(e.getMessage()==null?"Request failed":e.getMessage());}
                }
            });
        });
    }
    private void newChat(){
        if(busy)return;restorePending=false;restoredDraft="";restoredConversation="";transcript.clear();pendingPrompt="";attachment=null;attachmentName="";conversation="";meshMessages=new JSONArray();lastAnswer="";
        if(chatUi!=null){chatUi.clearMessages();chatUi.setDraft("");chatUi.setAttachmentLabel("");chatUi.setModeLabel(meshMode?"AI Mesh":"Agent");chatUi.setModelLabel(model);}
        setStatus(meshMode?"AI Mesh · "+model:"Personal agent");
    }
    private void send(){
        if(busy||!signedIn||chatUi==null)return;
        String prompt=chatUi.getDraft().trim();if(prompt.isEmpty())return;
        if(prompt.length()>(meshMode?5000:12000)){setStatus("Message is too long for this mode.");return;}
        View focused=getCurrentFocus();if(focused!=null)hideKeyboard(focused);chatUi.setDraft("");pendingPrompt=prompt;append("user",prompt);
        if(meshMode){
            final JSONArray next=new JSONArray();
            try{for(int i=Math.max(0,meshMessages.length()-10);i<meshMessages.length();i++)next.put(meshMessages.get(i));Object content=attachment==null?prompt:new JSONArray().put(new JSONObject().put("type","text").put("text",prompt)).put(attachment);next.put(new JSONObject().put("role","user").put("content",content));}
            catch(JSONException e){chatUi.setDraft(prompt);pendingPrompt="";setStatus("Message error");return;}
            final NativeChatView target=chatUi;
            target.setPartialReply("");target.setStreaming(true);api.prepareStream();
            submit("Generating…",()->api.streamChat(new JSONObject().put("model",model).put("messages",next),delta->runOnUiThread(()->{if(!isDestroyed()&&chatUi==target)target.setPartialReply(target.getPartialReply()+delta);})),r->{
                String value=(String)r;if(value.isEmpty())throw new Exception("Model did not return text.");
                pendingPrompt="";target.setPartialReply("");attachment=null;attachmentName="";if(chatUi!=null)chatUi.setAttachmentLabel("");meshMessages=next;meshMessages.put(new JSONObject().put("role","assistant").put("content",value));lastAnswer=value;append("assistant",value);
            },true);return;
        }
        final String id=conversation;
        submit("Working…",()->{JSONObject body=DragonApi.object("message",prompt);if(!id.isEmpty())body.put("conversation_id",id);return api.call("/api/personal-agent/chat",body);},r->{
            JSONObject answer=(JSONObject)r;conversation=answer.optString("conversation_id",id);
            String value=answer.optString("message",answer.optString("output",""));
            JSONObject nested=answer.optJSONObject("result");if(value.isEmpty()&&nested!=null)value=nested.optString("message");
            if(value.isEmpty())throw new Exception("Agent did not return a message.");
            pendingPrompt="";lastAnswer=value;append("assistant",value);
            if(answer.has("error_code")&&!answer.optString("error_code").isEmpty())setStatus(answer.optString("error_code"));
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
            if(selected.isEmpty()&&history.length()>0){
                JSONObject first=history.optJSONObject(0);
                if(first!=null)selected=first.optString("id");
            }
            if(!selected.isEmpty())open(selected);
            else applyRestoredDraft();
        },true);
    }
    private void applyRestoredDraft(){
        if(restorePending&&chatUi!=null)chatUi.setDraft(restoredDraft);
        restorePending=false;restoredDraft="";restoredConversation="";
    }
    @Override protected void onSaveInstanceState(Bundle out){
        // The draft is user-authored; never store passwords, credentials, or request payloads.
        out.putString("dz.conversation",conversation);
        out.putString("dz.draft",chatUi!=null?chatUi.getDraft():restoredDraft);
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
            meshMode=false;attachment=null;attachmentName="";conversation=id;transcript.clear();if(chatUi!=null){chatUi.clearMessages();chatUi.setModeLabel("Agent");chatUi.setAttachmentLabel("");chatUi.setDraft("");}JSONArray rows=(JSONArray)r;
            for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&Arrays.asList("user","assistant").contains(item.optString("role")))append(item.optString("role"),item.optString("content"));}
            applyRestoredDraft();
        },true);
    }
    private void chooseModel(){
        submit("Loading models…",()->api.call("/mesh/models",null),r->{
            JSONArray models=((JSONObject)r).optJSONArray("chat");if(models==null||models.length()==0)throw new Exception("No chat models available.");
            String[] names=new String[models.length()];for(int i=0;i<names.length;i++)names[i]=models.getJSONObject(i).optString("name");
            alert().setTitle("AI Mesh models").setItems(names,(d,i)->{model=models.optJSONObject(i).optString("id");meshMode=true;newChat();}).setNegativeButton("Close",null).show();
        },true);
    }
    private void approvals(){
        submit("Loading approvals…",()->{
            LinkedHashMap<String,JSONObject> all=new LinkedHashMap<>();
            for(String source:new String[]{"legacy","kernel"}){
                String prefix=source.equals("kernel")?"/api/kernel/personal/approvals":"/api/personal-tools/approvals";
                JSONObject payload=(JSONObject)api.call(prefix+"?status=pending",null);
                JSONArray rows=payload.optJSONArray("approvals");
                if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&!item.optString("id").isEmpty()){item.put("native_source",source);all.put(item.optString("id"),item);}}
            }return new JSONArray(all.values());
        },r->renderApprovals((JSONArray)r),true);
    }
    private void renderApprovals(JSONArray rows){
        Dialog dialog=new Dialog(this);LinearLayout page=column();page.setPadding(dp(18),dp(20),dp(18),dp(12));page.setBackgroundColor(BG);
        page.addView(heading("Pending approvals",26));gap(page,10);page.addView(text("Review the exact action and arguments before allowing execution.",14,MUTED));gap(page,16);
        ScrollView area=new ScrollView(this);LinearLayout list=column();area.addView(list);page.addView(area,new LinearLayout.LayoutParams(-1,0,1));
        if(rows.length()==0)list.addView(text("No Personal actions are waiting for approval.",14,MUTED));
        for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item==null)continue;
            LinearLayout card=column();GradientDrawable bg=surface(PANEL,16);bg.setStroke(dp(1),LINE);card.setBackground(bg);card.setPadding(dp(14),dp(14),dp(14),dp(14));
            card.addView(heading(item.optString("capability_id","Personal action"),18));gap(card,8);card.addView(text("Approval: "+item.optString("id"),12,MUTED));
            if(item.has("arguments_hash"))card.addView(text("Review hash: "+item.optString("arguments_hash"),12,MUTED));
            if(item.has("expires_at"))card.addView(text("Expires: "+item.optString("expires_at"),12,MUTED));
            gap(card,10);TextView arguments=text(item.optString("arguments","{}"),14,TEXT);arguments.setTextIsSelectable(true);card.addView(arguments);gap(card,15);
            LinearLayout actions=row();Button reject=button("Reject",()->confirmApproval(dialog,item,false));Button approve=primary("Approve exact action",()->confirmApproval(dialog,item,true));
            actions.addView(reject,new LinearLayout.LayoutParams(0,-2,1));actions.addView(approve,new LinearLayout.LayoutParams(0,-2,2));card.addView(actions);list.addView(card);gap(list,12);
        }
        page.addView(button("Close",dialog::dismiss));dialog.setContentView(page);dialog.show();Window w=dialog.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setLayout(-1,-1);}
    }
    private void confirmApproval(Dialog dialog,JSONObject item,boolean approved){
        alert().setTitle(approved?"Approve exact action?":"Reject this action?").setMessage(item.optString("capability_id","Personal action")+"\n\n"+item.optString("arguments","{}")).setNegativeButton("Cancel",null).setPositiveButton(approved?"Approve and execute":"Reject",(d,i)->{
            dialog.dismiss();submit(approved?"Executing approved action…":"Rejecting action…",()->{
                String id=DragonApi.segment(item.getString("id"));boolean kernel="kernel".equals(item.optString("native_source"));
                String root=kernel?"/api/kernel/personal/approvals/":"/api/personal-tools/approvals/";
                Object decision=api.call(root+id+"/decision",DragonApi.object("approved",approved));
                if(!approved)return DragonApi.object("decision","rejected");
                if(kernel)return api.call(root+id+"/execute",new JSONObject());
                JSONObject contract=decision instanceof JSONObject?(JSONObject)decision:item;
                String capability=contract.optString("capability_id",item.optString("capability_id"));if(capability.isEmpty())throw new Exception("Approved action missing capability contract; check execution status.");
                JSONObject arguments=contract.optJSONObject("arguments");if(arguments==null)arguments=item.optJSONObject("arguments");if(arguments==null)arguments=new JSONObject();
                JSONObject body=new JSONObject().put("goal","").put("arguments",arguments).put("request_id",contract.optString("request_id",item.optString("request_id",UUID.randomUUID().toString()))).put("approval_id",contract.optString("id",item.getString("id")));
                String conversation=contract.optString("conversation_id",item.optString("conversation_id"));if(!conversation.isEmpty())body.put("conversation_id",conversation);
                return api.call("/api/personal-tools/"+DragonApi.segment(capability)+"/execute",body);
            },result->{
                JSONObject value=result instanceof JSONObject?(JSONObject)result:new JSONObject();
                String reported=value.optString("status",value.optString("decision","unspecified"));
                alert().setTitle(approved?"Execution result":"Decision recorded").setMessage("Server status: "+reported+"\n\n"+value.toString()).setPositiveButton("Close",null).show();
            },true);
        }).show();
    }
    private void showConnections(){
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
    private void showTools(){
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
        if(!result.optBoolean("done",true)||"failed".equals(result.optString("status")))throw new Exception("Unable to read workflow record.");
        JSONObject payload=result.optJSONObject("result");if(payload==null)return new JSONObject();JSONObject value=payload.optJSONObject("value");return value==null?payload:value;
    }
    private void showTasks(){
        submit("Loading Personal workflows…",()->{
            JSONObject catalog=(JSONObject)api.call("/api/personal-tools?query=workflow&limit=100",null);
            JSONArray rows=catalog.optJSONArray("tools");HashSet<String> ids=new HashSet<>();if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject t=rows.optJSONObject(i);if(t!=null)ids.add(t.optString("id"));}
            if(!ids.contains("workflow.list"))throw new Exception("Workflow discovery is unavailable for this Personal session.");
            JSONObject definitions=workflowRead("workflow.list");JSONObject activity=ids.contains("workflow.run.list")?workflowRead("workflow.run.list"):new JSONObject();
            return new JSONObject().put("definitions",definitions).put("activity",activity);
        },r->{JSONObject data=(JSONObject)r;JSONArray workflows=data.getJSONObject("definitions").optJSONArray("workflows");JSONArray runs=data.getJSONObject("activity").optJSONArray("runs");
            StringBuilder content=new StringBuilder("WORKFLOWS\n");if(workflows==null||workflows.length()==0)content.append("No workflows returned.\n");
            else for(int i=0;i<workflows.length();i++){JSONObject w=workflows.optJSONObject(i);if(w!=null)content.append(w.optString("name",w.optString("id"))).append(" · ").append(w.optString("status",w.optBoolean("enabled")?"Enabled":"Unknown")).append("\n");}
            content.append("\nRECENT RUNS\n");if(runs==null||runs.length()==0)content.append("No runs returned.");else for(int i=0;i<runs.length();i++){JSONObject run=runs.optJSONObject(i);if(run!=null)content.append(run.optString("workflow_name",run.optString("workflow_id","Run"))).append(" · ").append(run.optString("status","Unknown")).append("\n");}
            alert().setTitle("Personal tasks").setMessage(content.toString()).setPositiveButton("Close",null).show();
        },true);
    }
    private void dictate(){
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak to DragonZpyder");
        try{startActivityForResult(intent,42);}
        catch(android.content.ActivityNotFoundException e){setStatus("No speech recognition service available.");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==45){if(signedIn&&meshMode&&result==RESULT_OK&&data!=null)attachCameraPreview(data);return;}if(request==44){if(signedIn&&result==RESULT_OK&&data!=null&&data.getData()!=null)transcribeAudio(data.getData());else transcriptionModel="";return;}if(request==43&&signedIn&&meshMode&&result==RESULT_OK&&data!=null&&data.getData()!=null){readAttachment(data.getData());return;}if(request==42&&signedIn&&result==RESULT_OK&&data!=null&&chatUi!=null){ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty()){String draft=chatUi.getDraft();chatUi.setDraft(draft+(draft.isEmpty()?"":" ")+words.get(0));}}}
    @Override public void onBackPressed(){if(busy)return;if(accountOpen){accountOpen=false;chatScreen();}else if(!signedIn&&!"login".equals(authMode))authScreen("login","");else super.onBackPressed();}
    private void signOut(){submit("Signing out…",()->{api.logout();return null;},r->{conversation="";pendingPrompt="";attachment=null;attachmentName="";transcript.clear();meshMode=false;lastAnswer="";meshMessages=new JSONArray();history=new JSONArray();profileInitial="D";authEmail="";challengeId="";stopMedia();transcriptionModel="";if(tts!=null)tts.stop();chatUi=null;loginScreen("");},true);}
    @Override protected void onDestroy(){stopMedia();api.cancelStream();worker.shutdownNow();if(tts!=null)tts.shutdown();super.onDestroy();}
}
