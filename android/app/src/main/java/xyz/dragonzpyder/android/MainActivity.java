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
    private static final int BG=0xff101219, PANEL=0xff1b202a, TEXT=0xffeef1f8, MUTED=0xffa8b2c2, ACCENT=0xffb5d6ff;
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
    private TextView heading(String s,int size){TextView t=text(s,size,TEXT);t.setTypeface(null,Typeface.BOLD);return t;}
    private Button button(String s,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(s);b.setTextColor(ACCENT);b.setTextSize(14);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(PANEL));b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private EditText field(String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setHintTextColor(MUTED);e.setTextColor(TEXT);e.setTextSize(16);e.setPadding(dp(14),dp(12),dp(14),dp(12));e.setBackground(surface(PANEL,16));e.setInputType(secret?129:1);return e;}
    private void gap(LinearLayout l,int height){l.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height)));}
    private void reset(){root=column();root.setBackgroundColor(BG);root.setPadding(dp(16),dp(16),dp(16),dp(10));setContentView(root);}
    private void loginScreen(String message){
        signedIn=false;reset();root.setGravity(Gravity.CENTER_VERTICAL);
        TextView title=heading("DragonZpyder",32);root.addView(title);gap(root,6);
        root.addView(text("Your intelligence, connected.",16,MUTED));gap(root,30);
        EditText email=field("Email",false);email.setInputType(33);email.setSingleLine(true);root.addView(email);gap(root,10);
        EditText password=field("Password",true);password.setSingleLine(true);root.addView(password);gap(root,14);
        Button login=button("Sign in",()->{
            String e=email.getText().toString().trim(),p=password.getText().toString();
            if(e.isEmpty()||p.isEmpty()){status.setText("Enter your email and password.");return;}
            hideKeyboard(password);password.setText("");
            submit("Signing in…",()->{api.login(e,p);return null;},result->{signedIn=true;chatScreen();loadHistory(true);},true);
        });root.addView(login);
        status=text(message,14,MUTED);status.setPadding(0,dp(12),0,0);root.addView(status);
        gap(root,16);root.addView(text("Native preview · Existing Personal account",12,MUTED));
    }
    private void chatScreen(){
        reset();LinearLayout toolbar=row();
        TextView brand=heading("DragonZpyder",21);
        toolbar.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
        toolbar.addView(button("History",this::showHistory));toolbar.addView(button("New",this::newChat));
        root.addView(toolbar);
        LinearLayout controls=row();
        controls.addView(button("Agent",()->{meshMode=false;newChat();}));
        controls.addView(button("Models",this::chooseModel));
        controls.addView(button("Approvals",this::approvals));
        controls.addView(button("Sign out",this::signOut));
        HorizontalScrollView strip=new HorizontalScrollView(this);strip.setHorizontalScrollBarEnabled(false);strip.addView(controls);root.addView(strip);
        status=text("Personal agent",12,MUTED);root.addView(status);gap(root,8);
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=column();scroll.addView(messages);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=row();input=field("Message DragonZpyder",false);input.setInputType(1|131072);input.setMaxLines(5);
        composer.addView(input,new LinearLayout.LayoutParams(0,-2,1));
        composer.addView(button("Mic",this::dictate));composer.addView(button("Send",this::send));root.addView(composer);
        if(conversation.isEmpty()) welcome();
    }
    private void welcome(){messages.removeAllViews();gap(messages,45);messages.addView(heading("What can I help you with?",25));gap(messages,8);messages.addView(text(meshMode?"AI Mesh · "+model:"Ask a question or delegate a task.",15,MUTED));}
    private void append(String role,String content){
        if(messages.getChildCount()>0 && messages.getChildAt(0) instanceof View && conversation.isEmpty() && !meshMode && lastAnswer.isEmpty() && messages.getChildCount()==4) messages.removeAllViews();
        boolean user="user".equals(role);LinearLayout bubble=column();bubble.setPadding(dp(14),dp(12),dp(14),dp(12));bubble.setBackground(surface(user?0xff27364b:PANEL,18));
        bubble.addView(text(user?"You":"DragonZpyder",12,ACCENT));gap(bubble,5);TextView body=text(content,16,TEXT);body.setTextIsSelectable(true);bubble.addView(body);
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
        hideKeyboard(input);input.setText("");if(conversation.isEmpty() && meshMessages.length()==0)messages.removeAllViews();append("user",prompt);
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
            meshMode=false;conversation=id;messages.removeAllViews();JSONArray rows=(JSONArray)r;
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
