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

public final class MainActivity extends Activity {
    private static final int BG=0xff101310, PANEL=0xff1d221d, TEXT=0xfff4f2ed, MUTED=0xffa5aca1, ACCENT=0xffd6a573, LINE=0xff39433a;
    private boolean welcomeVisible;
    private static final DragonApi api=new DragonApi();
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private LinearLayout root, messages;
    private ScrollView scroll;
    private EditText input;
    private TextView status;
    private String conversation="", lastAnswer="";
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
        getWindow().setStatusBarColor(BG); getWindow().setNavigationBarColor(BG);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        tts=new TextToSpeech(this, code -> speechReady=code==TextToSpeech.SUCCESS);
        loginScreen("");
        submit("Checking session…", () -> api.call("/api/auth/sessions",null), result -> {
            JSONArray rows=(JSONArray)result;
            for(int i=0;i<rows.length();i++){
                JSONObject row=rows.optJSONObject(i);
                if(row!=null && row.optBoolean("current") && "personal".equals(row.optString("scope"))){
                    signedIn=true; chatScreen(); loadHistory(true); break;
                }
            }
        }, false);
    }
    private int dp(float n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private GradientDrawable surface(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private TextView text(String s,int size,int color){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);return v;}
    private TextView heading(String s,int size){TextView t=text(s,size,TEXT);t.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));t.setLetterSpacing(-.035f);return t;}
    private TextView serif(String s,int size){TextView t=text(s,size,TEXT);t.setTypeface(Typeface.create("serif",Typeface.NORMAL));t.setLetterSpacing(-.035f);return t;}
    private ImageView logo(int size){ImageView image=new ImageView(this);image.setImageResource(R.drawable.brand_icon);image.setScaleType(ImageView.ScaleType.FIT_CENTER);image.setLayoutParams(new LinearLayout.LayoutParams(dp(size),dp(size)));image.setContentDescription("DragonZpyder");return image;}
    private Button button(String s,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(s);b.setTextColor(TEXT);b.setTextSize(14);b.setTypeface(Typeface.create("sans-serif-medium",0));b.setMinHeight(dp(48));b.setMinimumHeight(dp(48));b.setMinWidth(dp(48));b.setMinimumWidth(dp(48));b.setPadding(dp(12),0,dp(12),0);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22ffffff),surface(PANEL,14),null));b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private Button primary(String s,Runnable action){Button b=button(s,action);b.setTextColor(BG);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22000000),surface(ACCENT,20),null));return b;}
    private EditText field(String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setHintTextColor(MUTED);e.setTextColor(TEXT);e.setTextSize(16);e.setPadding(dp(14),dp(12),dp(14),dp(12));GradientDrawable d=surface(PANEL,16);d.setStroke(dp(1),LINE);e.setBackground(d);e.setInputType(secret?129:1);return e;}
    private void gap(LinearLayout l,int height){l.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height)));}
    private void reset(){root=column();root.setBackgroundColor(BG);root.setPadding(dp(20),dp(16),dp(20),dp(12));setContentView(root);root.setOnApplyWindowInsetsListener((v,insets)->{int left,top,right,bottom;if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());left=bars.left;top=bars.top;right=bars.right;bottom=bars.bottom;}else{left=insets.getSystemWindowInsetLeft();top=insets.getSystemWindowInsetTop();right=insets.getSystemWindowInsetRight();bottom=insets.getSystemWindowInsetBottom();}v.setPadding(dp(20)+left,dp(12)+top,dp(20)+right,dp(12)+bottom);return insets;});root.requestApplyInsets();}
    private void loginScreen(String message){
        signedIn=false;reset();root.setGravity(Gravity.CENTER_VERTICAL);
        root.addView(logo(64));gap(root,24);
        TextView eyebrow=text("DRAGONZPYDER  /  PERSONAL",11,ACCENT);eyebrow.setLetterSpacing(.16f);root.addView(eyebrow);gap(root,12);
        root.addView(serif("Welcome back.",38));gap(root,8);
        root.addView(text("One intelligence. Many possibilities.",16,MUTED));gap(root,30);
        EditText email=field("Email",false);email.setInputType(33);email.setSingleLine(true);root.addView(text("EMAIL ADDRESS",11,MUTED));gap(root,6);root.addView(email);gap(root,16);
        EditText password=field("Password",true);password.setSingleLine(true);root.addView(text("PASSWORD",11,MUTED));gap(root,6);root.addView(password);gap(root,22);
        Button login=primary("Sign in",()->{
            String e=email.getText().toString().trim(),p=password.getText().toString();
            if(e.isEmpty()||p.isEmpty()){status.setText("Enter your email and password.");return;}
            hideKeyboard(password);password.setText("");
            submit("Signing in…",()->{api.login(e,p);return null;},result->{signedIn=true;chatScreen();loadHistory(true);},true);
        });root.addView(login);
        status=text(message,14,MUTED);status.setPadding(0,dp(12),0,0);root.addView(status);
        gap(root,24);root.addView(text("Secure Personal session · DragonZpyder",12,MUTED));
    }
    private void chatScreen(){
        reset();LinearLayout toolbar=row();
        toolbar.addView(button("☰",this::showMenu));gap(root,4);
        LinearLayout title=column();TextView brand=heading("DragonZpyder",20);title.addView(brand);title.addView(text("Personal workspace",11,MUTED));
        LinearLayout.LayoutParams titleParams=new LinearLayout.LayoutParams(0,-2,1);titleParams.setMargins(dp(12),0,0,0);toolbar.addView(title,titleParams);
        Button newButton=button("+",this::newChat);newButton.setContentDescription("New conversation");toolbar.addView(newButton);root.addView(toolbar);
        gap(root,12);View divider=new View(this);divider.setBackgroundColor(LINE);root.addView(divider,new LinearLayout.LayoutParams(-1,dp(1)));gap(root,12);
        status=text("Personal agent",12,MUTED);status.setPadding(dp(4),0,0,0);root.addView(status);
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=column();scroll.addView(messages);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=column();GradientDrawable skin=surface(PANEL,24);skin.setStroke(dp(1),LINE);composer.setBackground(skin);composer.setPadding(dp(10),dp(8),dp(10),dp(8));
        input=field("Message DragonZpyder",false);input.setBackgroundColor(Color.TRANSPARENT);input.setInputType(1|131072);input.setMaxLines(5);composer.addView(input,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout actions=row();actions.addView(button("Mode",this::showModes));actions.addView(new View(this),new LinearLayout.LayoutParams(0,1,1));
        Button microphone=button("Mic",this::dictate);microphone.setContentDescription("Voice dictation");actions.addView(microphone);Button send=primary("↑",this::send);send.setContentDescription("Send message");actions.addView(send);composer.addView(actions);root.addView(composer);
        if(conversation.isEmpty()) welcome();
    }
    private void showMenu(){new AlertDialog.Builder(this).setTitle("Personal workspace").setItems(new String[]{"New conversation","Chat history","Switch mode","Pending approvals","Sign out"},(d,i)->{switch(i){case 0:newChat();break;case 1:showHistory();break;case 2:showModes();break;case 3:approvals();break;case 4:signOut();break;}}).show();}
    private void showModes(){new AlertDialog.Builder(this).setTitle("Choose your intelligence").setItems(new String[]{"DragonZpyder Agent — tasks and tools","AI Mesh — choose a model"},(d,i)->{if(i==0){meshMode=false;newChat();}else chooseModel();}).show();}
    private void welcome(){messages.removeAllViews();welcomeVisible=true;messages.setGravity(Gravity.CENTER);LinearLayout panel=column();panel.setGravity(Gravity.CENTER_HORIZONTAL);panel.addView(logo(68));gap(panel,24);
        TextView label=text(meshMode?"AI MESH":"YOUR PERSONAL INTELLIGENCE",10,ACCENT);label.setLetterSpacing(.16f);panel.addView(label);gap(panel,12);
        TextView title=serif("What can we\\nwork on today?",34);title.setGravity(Gravity.CENTER);panel.addView(title);gap(panel,14);
        TextView desc=text(meshMode?model:"Ask, create, explore, or delegate a task.",15,MUTED);desc.setGravity(Gravity.CENTER);panel.addView(desc);gap(panel,25);
        for(String prompt:new String[]{"Help me plan something","Research an idea","Help me write something"}){Button suggestion=button(prompt,()->{input.setText(prompt);input.setSelection(input.length());});LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(52));lp.setMargins(0,0,0,dp(8));panel.addView(suggestion,lp);}
        messages.addView(panel,new LinearLayout.LayoutParams(-1,-2));}
    private void append(String role,String content){
        if(welcomeVisible){messages.removeAllViews();welcomeVisible=false;}messages.setGravity(Gravity.TOP);
        boolean user="user".equals(role);LinearLayout bubble=column();bubble.setPadding(dp(14),dp(12),dp(14),dp(12));bubble.setBackground(surface(user?0xff293329:BG,20));
        bubble.addView(text(user?"You":"DragonZpyder",12,ACCENT));gap(bubble,5);TextView body=text(content,16,TEXT);body.setLineSpacing(dp(4),1.08f);body.setTextIsSelectable(true);bubble.addView(body);
        if(!user){Button speak=button("Read aloud",()->{if(speechReady)tts.speak(content,TextToSpeech.QUEUE_FLUSH,null,"response");else status.setText("Speech engine unavailable");});bubble.addView(speak);}
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(user?dp(25):0,dp(8),user?0:dp(10),dp(4));messages.addView(bubble,lp);
        scroll.post(()->scroll.fullScroll(View.FOCUS_DOWN));
    }
    private void hideKeyboard(View v){((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(v.getWindowToken(),0);}
    private void submit(String label,Work work,Done done,boolean report){
        if(busy)return;busy=true;if(status!=null)status.setText(label);
        worker.execute(()->{
            Object result=null;Exception error=null;
            try{result=work.run();}catch(Exception e){error=e;}
            final Object value=result;final Exception failure=error;
            runOnUiThread(()->{
                if(isDestroyed())return;busy=false;
                try{
                    if(failure!=null)throw failure;
                    if(status!=null)status.setText(signedIn?(meshMode?"AI Mesh · "+model:"Personal agent"):"");
                    done.accept(value);
                }catch(Exception e){
                    if(e instanceof DragonApi.ApiError && ((DragonApi.ApiError)e).status==401 && signedIn){api.clear();loginScreen("Session expired. Sign in again.");}
                    else if(report && status!=null)status.setText(e.getMessage()==null?"Request failed":e.getMessage());
                }
            });
        });
    }
    private void newChat(){conversation="";meshMessages=new JSONArray();lastAnswer="";welcome();status.setText(meshMode?"AI Mesh · "+model:"Personal agent");}
    private void send(){
        String prompt=input.getText().toString().trim();if(prompt.isEmpty())return;
        hideKeyboard(input);input.setText("");if(welcomeVisible){messages.removeAllViews();welcomeVisible=false;}messages.setGravity(Gravity.TOP);append("user",prompt);
        if(meshMode){
            final JSONArray next=new JSONArray();
            try{for(int i=Math.max(0,meshMessages.length()-10);i<meshMessages.length();i++)next.put(meshMessages.get(i));next.put(new JSONObject().put("role","user").put("content",prompt));}
            catch(JSONException e){status.setText("Message error");return;}
            submit("Generating…",()->api.call("/mesh/chat",new JSONObject().put("model",model).put("messages",next)),r->{
                JSONObject answer=(JSONObject)r;String value=answer.optString("message",answer.optString("text",answer.optString("content","")));
                if(value.isEmpty())throw new Exception("Model did not return text.");
                meshMessages=next;meshMessages.put(new JSONObject().put("role","assistant").put("content",value));lastAnswer=value;append("assistant",value);
            },true);return;
        }
        final String id=conversation;
        submit("Working…",()->{JSONObject body=DragonApi.object("message",prompt);if(!id.isEmpty())body.put("conversation_id",id);return api.call("/api/personal-agent/chat",body);},r->{
            JSONObject answer=(JSONObject)r;conversation=answer.optString("conversation_id",id);
            String value=answer.optString("message",answer.optString("output",""));
            JSONObject nested=answer.optJSONObject("result");if(value.isEmpty()&&nested!=null)value=nested.optString("message");
            if(value.isEmpty())throw new Exception("Agent did not return a message.");
            lastAnswer=value;append("assistant",value);
            if(answer.has("error_code")&&!answer.optString("error_code").isEmpty())status.setText(answer.optString("error_code"));
        },true);
    }
    private void loadHistory(boolean restore){
        submit("Loading conversations…",()->api.call("/api/personal-agent/conversations",null),r->{history=(JSONArray)r;if(restore&&history.length()>0){JSONObject first=history.optJSONObject(0);if(first!=null)open(first.optString("id"));}},true);
    }
    private void showHistory(){
        submit("Loading conversations…",()->api.call("/api/personal-agent/conversations",null),r->{
            history=(JSONArray)r;String[] labels=new String[history.length()];
            for(int i=0;i<labels.length;i++)labels[i]=history.getJSONObject(i).optString("title","Conversation");
            new AlertDialog.Builder(this).setTitle("Conversations").setItems(labels,(d,i)->{JSONObject c=history.optJSONObject(i);if(c!=null)open(c.optString("id"));}).setNegativeButton("Close",null).show();
        },true);
    }
    private void open(String id){
        if(id.isEmpty())return;
        submit("Loading chat…",()->api.call("/api/personal-agent/conversations/"+DragonApi.segment(id)+"/messages",null),r->{
            meshMode=false;conversation=id;welcomeVisible=false;messages.removeAllViews();messages.setGravity(Gravity.TOP);JSONArray rows=(JSONArray)r;
            for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&Arrays.asList("user","assistant").contains(item.optString("role")))append(item.optString("role"),item.optString("content"));}
        },true);
    }
    private void chooseModel(){
        submit("Loading models…",()->api.call("/mesh/models",null),r->{
            JSONArray models=((JSONObject)r).optJSONArray("chat");if(models==null||models.length()==0)throw new Exception("No chat models available.");
            String[] names=new String[models.length()];for(int i=0;i<names.length;i++)names[i]=models.getJSONObject(i).optString("name");
            new AlertDialog.Builder(this).setTitle("AI Mesh models").setItems(names,(d,i)->{model=models.optJSONObject(i).optString("id");meshMode=true;newChat();}).setNegativeButton("Close",null).show();
        },true);
    }
    private void approvals(){
        submit("Loading approval requests…",()->{
            LinkedHashMap<String,JSONObject> all=new LinkedHashMap<>();
            for(String prefix:new String[]{"/api/personal-tools/approvals","/api/kernel/personal/approvals"}){
                JSONObject payload=(JSONObject)api.call(prefix+"?status=pending",null);
                JSONArray rows=payload.optJSONArray("approvals");
                if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&!item.optString("id").isEmpty())all.put(item.optString("id"),item);}
            }return new JSONArray(all.values());
        },r->{JSONArray rows=(JSONArray)r;StringBuilder s=new StringBuilder();
            for(int i=0;i<rows.length();i++){JSONObject item=rows.getJSONObject(i);s.append(item.optString("title",item.optString("capability_id","Pending action"))).append("\n").append(item.optString("arguments")).append("\n\n");}
            new AlertDialog.Builder(this).setTitle("Pending approvals").setMessage(rows.length()==0?"No pending approvals.":s+"Approval execution is not enabled in this native preview.").setPositiveButton("Close",null).show();
        },true);
    }
    private void dictate(){
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT,"Speak to DragonZpyder");
        try{startActivityForResult(intent,42);}
        catch(android.content.ActivityNotFoundException e){status.setText("No speech recognition service available.");}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==42&&result==RESULT_OK&&data!=null&&input!=null){ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())input.setText(words.get(0));}}
    private void signOut(){submit("Signing out…",()->{api.logout();return null;},r->{conversation="";meshMode=false;lastAnswer="";meshMessages=new JSONArray();history=new JSONArray();loginScreen("");},true);}
    @Override protected void onDestroy(){worker.shutdown();if(tts!=null)tts.shutdown();super.onDestroy();}
}
