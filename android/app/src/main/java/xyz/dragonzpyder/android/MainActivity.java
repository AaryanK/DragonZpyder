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
    private int BG, PANEL, TEXT, MUTED, ACCENT, LINE, SIDEBAR, CHIP, USER, COMPOSER;
    private boolean dark;
    private final ArrayList<String[]> transcript=new ArrayList<>();
    private void palette(){
        BG=dark?0xff0e0f11:0xfffaf9f7; PANEL=dark?0xff242124:0xffffffff;
        TEXT=dark?0xfff6f4f1:0xff24221f; MUTED=dark?0xffa9a19c:0xff817a74;
        ACCENT=dark?0xffff631f:0xffe65a26; LINE=dark?0xff665047:0xffe1dad2;
        SIDEBAR=dark?0xff141416:0xfff3f1ee; CHIP=dark?0xff1a191c:0xfff6f3ef;
        USER=dark?0xff222922:0xffeeebe6; COMPOSER=PANEL;
        getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }
    private void toggleTheme(){
        String draft=input==null?"":input.getText().toString();dark=!dark;
        getPreferences(MODE_PRIVATE).edit().putBoolean("dark",dark).apply();palette();
        if(signedIn){chatScreen();if(input!=null)input.setText(draft);}else loginScreen("");
    }
    private boolean welcomeVisible;
    private static final DragonApi api=new DragonApi();
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private LinearLayout root, messages;
    private ScrollView scroll;
    private EditText input;
    private TextView status, attachmentLabel;
    private Button modeButton;
    private JSONObject attachment;
    private String attachmentName="";
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
        dark=getPreferences(MODE_PRIVATE).getBoolean("dark",false);palette();
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
    private Button button(String s,Runnable action){Button b=new Button(this);b.setAllCaps(false);b.setText(s);b.setTextColor(TEXT);b.setTextSize(14);b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));b.setMinHeight(dp(48));b.setMinimumHeight(dp(48));b.setMinWidth(dp(48));b.setMinimumWidth(dp(48));b.setPadding(dp(12),0,dp(12),0);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22ffffff),surface(CHIP,10),null));b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    private Button primary(String s,Runnable action){Button b=button(s,action);b.setTextColor(Color.WHITE);b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x22000000),surface(ACCENT,11),null));return b;}
    private EditText field(String hint,boolean secret){EditText e=new EditText(this);e.setHint(hint);e.setHintTextColor(MUTED);e.setTextColor(TEXT);e.setTextSize(16);e.setPadding(dp(14),dp(12),dp(14),dp(12));GradientDrawable d=surface(PANEL,16);d.setStroke(dp(1),LINE);e.setBackground(d);e.setInputType(secret?129:1);return e;}
    private void gap(LinearLayout l,int height){l.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height)));}
    private void reset(){root=column();root.setBackgroundColor(BG);root.setPadding(dp(12),dp(8),dp(12),dp(8));setContentView(root);root.setOnApplyWindowInsetsListener((v,insets)->{int left,top,right,bottom;if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());left=bars.left;top=bars.top;right=bars.right;bottom=bars.bottom;}else{left=insets.getSystemWindowInsetLeft();top=insets.getSystemWindowInsetTop();right=insets.getSystemWindowInsetRight();bottom=insets.getSystemWindowInsetBottom();}v.setPadding(dp(12)+left,dp(8)+top,dp(12)+right,dp(8)+bottom);return insets;});root.requestApplyInsets();}
    private void loginScreen(String message){
        signedIn=false;reset();root.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout brandRow=row();brandRow.addView(logo(36));TextView brandName=heading("DragonZpyder",20);brandRow.addView(brandName);brandRow.addView(new View(this),new LinearLayout.LayoutParams(0,1,1));brandRow.addView(button(dark?"☀":"☾",this::toggleTheme));root.addView(brandRow);gap(root,24);
        TextView eyebrow=text("PRIVATE PERSONAL RUNTIME",11,ACCENT);eyebrow.setLetterSpacing(.16f);root.addView(eyebrow);gap(root,12);
        root.addView(heading("Sign in to your Personal AI",30));gap(root,8);
        root.addView(text("Sign in with your existing Operly account to access your private Personal workspace.",16,MUTED));gap(root,30);
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
        Button menu=button("☰",this::showMenu);menu.setContentDescription("Open sidebar");toolbar.addView(menu);
        LinearLayout title=column();title.addView(heading("Personal",15));status=text("Personal runtime connected",11,0xff56a47e);title.addView(status);
        LinearLayout.LayoutParams titleParams=new LinearLayout.LayoutParams(0,-2,1);titleParams.setMargins(dp(10),0,0,0);toolbar.addView(title,titleParams);
        Button command=button("⌘",this::showCommands);command.setContentDescription("Search commands");toolbar.addView(command);
        Button theme=button(dark?"☀":"☾",this::toggleTheme);theme.setContentDescription("Toggle appearance");toolbar.addView(theme);
        Button profile=button("D",this::showAccount);profile.setContentDescription("Account menu");toolbar.addView(profile);root.addView(toolbar);
        gap(root,8);View divider=new View(this);divider.setBackgroundColor(dark?0xff302c2c:0xffeae5de);root.addView(divider,new LinearLayout.LayoutParams(-1,dp(1)));
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=column();scroll.addView(messages);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=column();GradientDrawable skin=surface(COMPOSER,18);skin.setStroke(dp(1),LINE);composer.setBackground(skin);composer.setElevation(dp(3));composer.setPadding(dp(10),dp(8),dp(10),dp(8));
        input=field("Ask anything, or give DragonZpyder a task…",false);input.setBackgroundColor(Color.TRANSPARENT);input.setInputType(1|131072);input.setMinLines(2);input.setMaxLines(5);composer.addView(input,new LinearLayout.LayoutParams(-1,-2));attachmentLabel=text(attachmentName,12,ACCENT);attachmentLabel.setVisibility(attachment==null?View.GONE:View.VISIBLE);attachmentLabel.setOnClickListener(v->{if(!busy){attachment=null;attachmentName="";attachmentLabel.setVisibility(View.GONE);}});composer.addView(attachmentLabel);
        LinearLayout actions=row();Button add=button("＋",this::showAdd);add.setContentDescription("Open attachment menu");actions.addView(add);
        modeButton=button(meshMode?"✦ AI Mesh":"✦ Agent",this::showModes);actions.addView(modeButton);actions.addView(new View(this),new LinearLayout.LayoutParams(0,1,1));
        Button microphone=button("Mic",this::dictate);microphone.setContentDescription("Voice dictation");actions.addView(microphone);Button send=primary("↑",this::send);send.setContentDescription("Send message");actions.addView(send);composer.addView(actions);root.addView(composer);
        if(transcript.isEmpty())welcome();else{welcomeVisible=false;messages.setGravity(Gravity.TOP);for(String[] item:transcript)renderMessage(item[0],item[1]);}
    
    }
    private void showMenu(){
        submit("Loading conversations…",()->api.call("/api/personal-agent/conversations",null),result->{
            history=(JSONArray)result;
            Dialog drawer=new Dialog(this);LinearLayout sidebar=column();sidebar.setPadding(dp(15),dp(22),dp(15),dp(15));sidebar.setBackgroundColor(SIDEBAR);
            LinearLayout brand=row();brand.addView(logo(32));brand.addView(heading("  DragonZpyder",18));sidebar.addView(brand);gap(sidebar,24);
            sidebar.addView(primary("＋ New chat",()->{drawer.dismiss();newChat();}));gap(sidebar,8);
            EditText search=field("Find conversations",false);search.setSingleLine(true);sidebar.addView(search);gap(sidebar,14);
            TextView label=text("YOUR CONVERSATIONS",11,MUTED);label.setLetterSpacing(.14f);sidebar.addView(label);
            ScrollView listScroll=new ScrollView(this);LinearLayout list=column();listScroll.addView(list);sidebar.addView(listScroll,new LinearLayout.LayoutParams(-1,0,1));
            Runnable filter=()->{list.removeAllViews();String query=search.getText().toString().toLowerCase(Locale.ROOT);for(int i=0;i<history.length();i++){JSONObject c=history.optJSONObject(i);if(c==null)continue;String name=c.optString("title","Conversation");if(!name.toLowerCase(Locale.ROOT).contains(query))continue;Button b=button(name,()->{drawer.dismiss();open(c.optString("id"));});b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);list.addView(b);gap(list,3);}};
            search.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){filter.run();}public void afterTextChanged(android.text.Editable e){}});filter.run();
            sidebar.addView(button("Approvals",()->{drawer.dismiss();approvals();}));sidebar.addView(button("Account & security",()->{drawer.dismiss();showAccount();}));
            drawer.setContentView(sidebar);drawer.show();Window w=drawer.getWindow();if(w!=null){w.setBackgroundDrawableResource(android.R.color.transparent);w.setGravity(Gravity.START|Gravity.TOP);w.setLayout(Math.min(dp(285),(int)(getResources().getDisplayMetrics().widthPixels*.88)), -1);}
        },true);
    }
    private void showAccount(){new AlertDialog.Builder(this).setTitle("Personal session").setItems(new String[]{"Sign out"},(d,i)->signOut()).setNegativeButton("Close",null).show();}
    private void showCommands(){new AlertDialog.Builder(this).setTitle("What would you like to do?").setItems(new String[]{"New chat","Find conversations","Switch mode","Approvals","Dictate a message","Toggle appearance"},(d,i)->{switch(i){case 0:newChat();break;case 1:showMenu();break;case 2:showModes();break;case 3:approvals();break;case 4:dictate();break;case 5:toggleTheme();break;}}).setNegativeButton("Close",null).show();}
    private void showAdd(){
        new AlertDialog.Builder(this).setTitle("Add to your message")
          .setItems(new String[]{"Attach a file or photo","Camera and screen capture (not yet available)"},(d,i)->{
            if(i!=0){status.setText("Camera and screen capture are not yet available.");return;}
            if(!meshMode){status.setText("Choose an AI Mesh model first, then attach a file.");chooseModel();return;}
            Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT);picker.setType("*/*");picker.addCategory(Intent.CATEGORY_OPENABLE);picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try{startActivityForResult(picker,43);}catch(android.content.ActivityNotFoundException e){status.setText("No file picker available.");}
          }).setNegativeButton("Close",null).show();
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
        },r->{JSONObject file=(JSONObject)r;attachment=file.getJSONObject("part");attachmentName=file.getString("name");attachmentLabel.setText("×  "+attachmentName);attachmentLabel.setVisibility(View.VISIBLE);},true);
    }
    private void showModes(){new AlertDialog.Builder(this).setTitle("Choose your intelligence").setItems(new String[]{"DragonZpyder Agent — tasks and tools","AI Mesh — choose a model"},(d,i)->{if(i==0){meshMode=false;newChat();}else chooseModel();}).show();}
    private void welcome(){messages.removeAllViews();welcomeVisible=true;messages.setGravity(Gravity.TOP|Gravity.CENTER_HORIZONTAL);LinearLayout panel=column();panel.setGravity(Gravity.CENTER_HORIZONTAL);panel.setPadding(dp(8),dp(38),dp(8),dp(24));
        if(dark){LinearLayout emblem=column();emblem.setGravity(Gravity.CENTER);GradientDrawable shape=surface(0xff261c1a,19);shape.setStroke(dp(1),0xff683c2b);emblem.setBackground(shape);emblem.addView(logo(40));panel.addView(emblem,new LinearLayout.LayoutParams(dp(65),dp(65)));gap(panel,20);}
        TextView title=heading("What shall we work on?",dark?38:34);title.setTypeface(Typeface.create("sans-serif",Typeface.BOLD));title.setGravity(Gravity.CENTER);panel.addView(title);gap(panel,12);
        TextView desc=text(meshMode?model:"From a quick question to a big idea. Start anywhere. We’ll find the way forward.",14,MUTED);desc.setGravity(Gravity.CENTER);desc.setLineSpacing(dp(3),1.1f);panel.addView(desc);gap(panel,26);
        String[] labels={"Explore an idea","Plan a project","Write something"};String[] prompts={"Help me think through a new idea.","Help me plan a project from scratch.","Help me turn my notes into a clear draft."};
        for(int i=0;i<labels.length;i++){final String prompt=prompts[i];Button suggestion=button(labels[i],()->{input.setText(prompt);input.setSelection(input.length());});GradientDrawable chip=surface(dark?CHIP:Color.WHITE,dark?14:25);chip.setStroke(dp(1),dark?0xff393338:0xffe6e0da);suggestion.setBackground(chip);suggestion.setTextSize(12);suggestion.setTextColor(MUTED);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(dark?-1:-2,dp(48));lp.setMargins(0,0,0,dp(8));panel.addView(suggestion,lp);}
        messages.addView(panel,new LinearLayout.LayoutParams(-1,-2));}
    private void append(String role,String content){transcript.add(new String[]{role,content});renderMessage(role,content);}
    private void renderMessage(String role,String content){
        if(welcomeVisible){messages.removeAllViews();welcomeVisible=false;}messages.setGravity(Gravity.TOP);
        boolean user="user".equals(role);LinearLayout bubble=column();bubble.setPadding(dp(14),dp(12),dp(14),dp(12));bubble.setBackground(surface(user?USER:BG,18));
        bubble.addView(text(user?"You":"DragonZpyder",11,MUTED));gap(bubble,5);TextView body=text(content,16,TEXT);body.setLineSpacing(dp(4),1.08f);body.setTextIsSelectable(true);bubble.addView(body);
        if(!user){Button speak=button("Read aloud",()->{if(speechReady)tts.speak(content,TextToSpeech.QUEUE_FLUSH,null,"response");else status.setText("Speech engine unavailable");});LinearLayout tools=row();tools.addView(button("Copy",()->{android.content.ClipboardManager cb=(android.content.ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);cb.setPrimaryClip(android.content.ClipData.newPlainText("DragonZpyder",content));}));tools.addView(speak);bubble.addView(tools);}
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
                    if(e instanceof DragonApi.ApiError && ((DragonApi.ApiError)e).status==401 && signedIn){api.clear();attachment=null;attachmentName="";transcript.clear();conversation="";meshMessages=new JSONArray();meshMode=false;loginScreen("Session expired. Sign in again.");}
                    else if(report && status!=null)status.setText(e.getMessage()==null?"Request failed":e.getMessage());
                }
            });
        });
    }
    private void newChat(){transcript.clear();attachment=null;attachmentName="";if(attachmentLabel!=null)attachmentLabel.setVisibility(View.GONE);if(modeButton!=null)modeButton.setText(meshMode?"✦ AI Mesh":"✦ Agent");conversation="";meshMessages=new JSONArray();lastAnswer="";welcome();status.setText(meshMode?"AI Mesh · "+model:"Personal agent");}
    private void send(){
        String prompt=input.getText().toString().trim();if(prompt.isEmpty())return;
        hideKeyboard(input);input.setText("");if(welcomeVisible){messages.removeAllViews();welcomeVisible=false;}messages.setGravity(Gravity.TOP);append("user",prompt);
        if(meshMode){
            final JSONArray next=new JSONArray();
            try{for(int i=Math.max(0,meshMessages.length()-10);i<meshMessages.length();i++)next.put(meshMessages.get(i));Object content=attachment==null?prompt:new JSONArray().put(new JSONObject().put("type","text").put("text",prompt)).put(attachment);next.put(new JSONObject().put("role","user").put("content",content));}
            catch(JSONException e){status.setText("Message error");return;}
            submit("Generating…",()->api.call("/mesh/chat",new JSONObject().put("model",model).put("messages",next)),r->{
                JSONObject answer=(JSONObject)r;String value=answer.optString("message",answer.optString("text",answer.optString("content","")));
                if(value.isEmpty())throw new Exception("Model did not return text.");
                attachment=null;attachmentName="";attachmentLabel.setVisibility(View.GONE);meshMessages=next;meshMessages.put(new JSONObject().put("role","assistant").put("content",value));lastAnswer=value;append("assistant",value);
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
            meshMode=false;if(modeButton!=null)modeButton.setText("✦ Agent");attachment=null;attachmentName="";if(attachmentLabel!=null)attachmentLabel.setVisibility(View.GONE);conversation=id;transcript.clear();welcomeVisible=false;messages.removeAllViews();messages.setGravity(Gravity.TOP);JSONArray rows=(JSONArray)r;
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
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==43&&result==RESULT_OK&&data!=null&&data.getData()!=null){readAttachment(data.getData());return;}if(request==42&&result==RESULT_OK&&data!=null&&input!=null){ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())input.setText(words.get(0));}}
    private void signOut(){submit("Signing out…",()->{api.logout();return null;},r->{conversation="";attachment=null;attachmentName="";transcript.clear();meshMode=false;lastAnswer="";meshMessages=new JSONArray();history=new JSONArray();loginScreen("");},true);}
    @Override protected void onDestroy(){worker.shutdown();if(tts!=null)tts.shutdown();super.onDestroy();}
}
