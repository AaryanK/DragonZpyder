package xyz.dragonzpyder.android;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Native, first-party session client. No WebView, browser or service credentials. */
final class DragonApi {
    private static final URI ORIGIN = URI.create("https://dragonzpyder.xyz");
    private SessionCookies cookies = new SessionCookies();
    private volatile boolean firstParty=true;
    private volatile boolean modeKnown;
    private volatile boolean requestLedger,agentStream,voiceEnabled,filesEnabled,goalsEnabled;
    boolean supportsFiles(){return firstParty&&filesEnabled&&requestLedger;}
    boolean supportsGoals(){return firstParty&&goalsEnabled;}
    boolean supportsVoice(){return firstParty&&voiceEnabled;}
    boolean supportsRequestLedger(){return firstParty&&requestLedger;}
    boolean supportsAgentStream(){return supportsRequestLedger()&&agentStream;}
    private String googleState="";
    boolean isFirstParty(){return firstParty;}
    boolean isModeKnown(){return modeKnown;}
    synchronized void refreshAuthenticationMode() throws Exception { discoverMode(); }
    private void discoverMode() throws Exception {
        // Android identity belongs to DragonZpyder, independently of web cutover.
        // The public Web gateway forwards /dz/ to the first-party API.
        boolean nativeMode=true;
        if(!modeKnown||nativeMode!=firstParty){cookies.clear();cookies=new SessionCookies(nativeMode);authenticated=false;requestBinding="";bootstrapCsrf="";googleState="";firstParty=nativeMode;}
        requestLedger=false;agentStream=false;voiceEnabled=false;filesEnabled=false;goalsEnabled=false;
        if(nativeMode){try{JSONObject capabilities=(JSONObject)request("/dz/v2/personal/status","GET",null,true);requestLedger=capabilities.optBoolean("request_ledger_enabled",false);agentStream=capabilities.optBoolean("agent_stream_enabled",false);voiceEnabled=capabilities.optBoolean("voice_enabled",false);filesEnabled=capabilities.optBoolean("artifacts_enabled",false);goalsEnabled=capabilities.optBoolean("goal_management_enabled",false);}catch(Exception unavailable){/* Keep first-party mode; never downgrade identity. */}}
        modeKnown=true;
    }
    private void ensureMode() throws Exception {if(!modeKnown)discoverMode();}
    private ApiError unsupported(){return new ApiError(503,"FIRST_PARTY_FEATURE_UNAVAILABLE","This feature is not yet available through DragonZpyder first-party identity. No legacy request was sent.");}
    private String bootstrapCsrf = "";
    private SecureSessionStore store;
    private boolean authenticated;
    synchronized boolean restore(android.content.Context context) throws Exception {
        if(store==null)store=new SecureSessionStore(context);
        discoverMode();
        if(cookies.snapshot().isEmpty())cookies.restore(store.read());
        if(cookies.snapshot().isEmpty()){clear();return false;}
        try{if(firstParty){if(!((JSONObject)call("/dz/v2/personal/session",null)).optBoolean("authenticated")){clear();return false;}}else{JSONArray sessions=(JSONArray)call("/api/auth/sessions",null);if(!personal(sessions)){clear();return false;}}authenticated=true;persist();return true;}
        catch(ApiError failure){if(failure.status==401||failure.status==403){clear();return false;}throw failure;}
    }
    private volatile String requestBinding="";
    String pendingRequestBinding(){return requestBinding;}
    private void persist(){
        if(!authenticated)return;
        requestBinding="";
        if(firstParty){
            String session=cookies.value("__Host-dz_identity");
            if(!session.isEmpty()){
                try{
                    byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest(("dz-native-request-v1:"+session).getBytes(StandardCharsets.UTF_8));
                    StringBuilder hex=new StringBuilder(64);
                    for(byte value:digest)hex.append(String.format(Locale.ROOT,"%02x",value&255));
                    requestBinding=hex.toString();
                }catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException("SHA-256 unavailable",impossible);}
            }
        }
        if(store!=null)store.save(cookies.snapshot());
    }
    static final class ApiError extends IOException {
        final int status; final String code;
        ApiError(int status, String message) { this(status,"HTTP_"+status,message); }
        ApiError(int status, String code, String message) { super(message); this.status=status; this.code=code; }
    }
    static JSONObject object(String key, Object value) throws JSONException {
        return new JSONObject().put(key, value);
    }
    static String segment(String value) { return android.net.Uri.encode(value); }
    private String csrf(URI uri) {
        String active = cookies.value(firstParty?"__Host-dz_csrf":"__Host-operly_csrf");
        return active.isEmpty() ? bootstrapCsrf : active;
    }
    synchronized Object call(String path, JSONObject body) throws Exception { return call(path,body==null?"GET":"POST",body); }
    synchronized Object call(String path, String method, JSONObject body) throws Exception {
        ensureMode();
        path=ApiRoutePolicy.route(firstParty,path);
        if(path==null){if(firstParty)throw unsupported();throw new IOException("Unsupported compatibility API route");}
        Object result;
        try { result=request(path,method,body,false); }
        catch(ApiError failure) {
            if(failure.status==410 && !firstParty && "LEGACY_OPERLY_ROUTE_RETIRED".equals(failure.code)){
                // Never replay credentials or mutations across identity realms.
                clear();
                modeKnown=false;
                throw new ApiError(410,"IDENTITY_CUTOVER_REAUTH_REQUIRED",
                    "DragonZpyder account access has changed. Sign in again; if your imported account is not active, use account recovery at dragonzpyder.xyz/account.");
            }
            throw failure;
        }
        if(firstParty&&path.equals("/dz/v2/personal/conversations")){if(!(result instanceof JSONObject)||((JSONObject)result).optJSONArray("conversations")==null)throw new IOException("Invalid conversation list");return ((JSONObject)result).getJSONArray("conversations");}
        if(firstParty&&path.startsWith("/dz/v2/personal/conversations/")&&path.endsWith("/messages")){if(!(result instanceof JSONObject)||((JSONObject)result).optJSONArray("messages")==null)throw new IOException("Invalid conversation history");return ((JSONObject)result).getJSONArray("messages");}
        return result;
    }
    private Object request(String path,String method,JSONObject body,boolean discovery) throws Exception {
        if(!path.startsWith("/api/")&&!path.startsWith("/mesh/")&&!path.startsWith("/dz/"))throw new IOException("Unsupported API route");
        URI uri = ORIGIN.resolve(path);
        if (!ORIGIN.getHost().equals(uri.getHost()) || !"https".equals(uri.getScheme()))
            throw new IOException("Unexpected API destination");
        HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(150000);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Cache-Control", "no-store");
        connection.setRequestMethod(method);
        try {
            String cookieHeader = discovery?"":cookies.header();
            if (!cookieHeader.isEmpty()) connection.setRequestProperty("Cookie", cookieHeader);
            boolean changing=!"GET".equals(method)&&!"HEAD".equals(method)&&!"OPTIONS".equals(method);
            if(changing){
                connection.setRequestProperty("Origin",ORIGIN.toString());
                boolean nativePreauth=ApiRoutePolicy.nativePreauth(firstParty,path);
                if(!nativePreauth){
                    String token=csrf(uri);
                    if(token.isEmpty())throw new ApiError(401,"Secure session missing. Sign in again.");
                    connection.setRequestProperty(ApiRoutePolicy.csrfHeader(firstParty),token);
                }
            }
            if (body != null) {
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setDoOutput(true);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            if(!discovery){cookies.receive(connection.getHeaderFields());if(authenticated&&status==401){clear();}else if(authenticated&&status>=200&&status<300){persist();}}
            if (status >= 300 && status < 400) throw new ApiError(status, "Unexpected API redirect");
            InputStream input = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            if (input != null) try (InputStream in = input) {
                byte[] chunk = new byte[8192]; int n;
                while ((n = in.read(chunk)) != -1) {
                    if (out.size() + n > 8 * 1024 * 1024) throw new IOException("Response too large");
                    out.write(chunk, 0, n);
                }
            }
            String raw = new String(out.toByteArray(), StandardCharsets.UTF_8);
            Object payload;
            try { payload = raw.isEmpty()&&status==204 ? JSONObject.NULL : new JSONTokener(raw).nextValue(); } catch (JSONException bad) { if(status>=200&&status<300)throw new IOException("Server returned invalid JSON",bad);payload = new JSONObject(); }
            if (status >= 400) {
                Object detail = payload instanceof JSONObject ? ((JSONObject)payload).opt("detail") : null;
                String message = detail instanceof JSONObject ? ((JSONObject)detail).optString("message", "Request failed") :
                    detail instanceof String ? (String)detail : "Request failed (" + status + ")";
                if(status==410 && !firstParty && detail instanceof JSONObject && "LEGACY_OPERLY_ROUTE_RETIRED".equals(((JSONObject)detail).optString("code"))){clear();modeKnown=false;throw new ApiError(410,"LEGACY_OPERLY_ROUTE_RETIRED","Authentication has moved to DragonZpyder. Sign in again to refresh account access.");}
                throw new ApiError(status, detail instanceof JSONObject ? ((JSONObject)detail).optString("code","HTTP_"+status) : "HTTP_"+status, message);
            }
            return payload;
        } finally { connection.disconnect(); }
    }
    synchronized JSONObject uploadFile(String name,String mime,byte[] bytes) throws Exception {
        if(!supportsFiles()||!authenticated)throw unsupported();
        if(bytes.length<1||bytes.length>10*1024*1024)throw new IOException("File must be 1 byte to 10 MiB");
        HttpURLConnection c=(HttpURLConnection)ORIGIN.resolve("/dz/v2/personal/files?filename="+segment(name)).toURL().openConnection();
        try{
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(90000);
            c.setRequestMethod("POST");c.setDoOutput(true);c.setFixedLengthStreamingMode(bytes.length);
            c.setRequestProperty("Content-Type",mime!=null&&mime.matches("[A-Za-z0-9!#    interface Delta^_.+-]{1,80}/[A-Za-z0-9!#    interface Delta^_.+-]{1,80}")?mime:"application/octet-stream");
            c.setRequestProperty("Cookie",cookies.header());c.setRequestProperty("Origin",ORIGIN.toString());c.setRequestProperty("X-DZ-CSRF",csrf(ORIGIN));
            try(OutputStream out=c.getOutputStream()){out.write(bytes);}
            int status=c.getResponseCode();if(status!=200){if(status==401)clear();throw new ApiError(status,"File upload failed ("+status+").");}
            byte[] response=boundedBytes(c.getInputStream(),32768);
            JSONObject metadata=new JSONObject(new String(response,StandardCharsets.UTF_8));
            if(!metadata.optString("id").matches("[0-9a-f-]{36}")||metadata.optInt("size")!=bytes.length)throw new IOException("Invalid file receipt");
            if(!sha256(bytes).equals(metadata.optString("sha256")))throw new IOException("File upload integrity mismatch");
            return metadata;
        }finally{c.disconnect();}
    }
    synchronized byte[] downloadFile(String id,String digest) throws Exception {
        if(!supportsFiles()||!authenticated)throw unsupported();
        if(!id.matches("[0-9a-f-]{36}")||!digest.matches("[0-9a-f]{64}"))throw new IOException("Invalid file receipt");
        HttpURLConnection c=(HttpURLConnection)ORIGIN.resolve("/dz/v2/personal/files/"+id).toURL().openConnection();
        try{
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(90000);
            c.setRequestProperty("Cookie",cookies.header());c.setRequestProperty("Accept","application/octet-stream");
            int status=c.getResponseCode();if(status!=200){if(status==401)clear();throw new ApiError(status,"File download failed ("+status+").");}
            byte[] data=boundedBytes(c.getInputStream(),10*1024*1024);
            if(!sha256(data).equals(digest))throw new IOException("Downloaded file integrity mismatch");
            return data;
        }finally{c.disconnect();}
    }
    private static byte[] boundedBytes(InputStream stream,int limit) throws IOException {
        try(InputStream input=stream;ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] chunk=new byte[8192];int n;
            while((n=input.read(chunk))!=-1){if(out.size()+n>limit)throw new IOException("File exceeds limit");out.write(chunk,0,n);}
            return out.toByteArray();
        }
    }
    private static String sha256(byte[] data) throws Exception {
        byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder hex=new StringBuilder(64);for(byte value:digest)hex.append(String.format(Locale.ROOT,"%02x",value&255));return hex.toString();
    }
    interface Delta { void accept(String text); }
    private volatile HttpURLConnection activeStream;
    private volatile boolean streamCancelled;
    void prepareStream(){streamCancelled=false;}
    void cancelStream(){streamCancelled=true;HttpURLConnection c=activeStream;if(c!=null)c.disconnect();}
    synchronized String streamChat(JSONObject body,Delta listener) throws Exception{
        ensureMode();if(firstParty)throw unsupported();
        if(streamCancelled)throw new IOException("Reply stopped");
        HttpURLConnection c=(HttpURLConnection)ORIGIN.resolve("/mesh/chat-stream").toURL().openConnection();
        activeStream=c;c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(90000);
        c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Accept","text/event-stream");c.setRequestProperty("Cache-Control","no-store");
        String token=csrf(ORIGIN);String cookieHeader=cookies.header();
        try{
            if(token.isEmpty()||cookieHeader.isEmpty())throw new ApiError(401,"Secure session missing");
            c.setRequestProperty("X-CSRF-Token",token);c.setRequestProperty("Cookie",cookieHeader);
            if(streamCancelled)throw new IOException("Reply stopped");
            try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
            int status=c.getResponseCode();cookies.receive(c.getHeaderFields());
            if(status==401)clear();else if(status>=200&&status<300)persist();
            if(status<200||status>=300)throw new ApiError(status,"Streaming request failed ("+status+")");
            if(c.getContentType()==null||!c.getContentType().toLowerCase(Locale.ROOT).startsWith("text/event-stream"))throw new IOException("Unexpected streaming response");
            StringBuilder answer=new StringBuilder();boolean done=false;
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(c.getInputStream(),StandardCharsets.UTF_8))){
                String line;while(!streamCancelled&&(line=reader.readLine())!=null){
                    if(!line.startsWith("data:"))continue;
                    if(line.length()>65536)throw new IOException("Stream event too large");
                    JSONObject event=new JSONObject(line.substring(5).trim());String type=event.optString("type");
                    if("delta".equals(type)){String delta=event.optString("text");answer.append(delta);if(answer.length()>100_000)throw new IOException("Reply exceeds the native display limit; check the server response before retrying.");listener.accept(delta);}
                    else if("error".equals(type)||"notice".equals(type))throw new IOException(event.optString("message","Stream interrupted"));
                    else if("done".equals(type)){done=true;break;}
                }
            }
            if(streamCancelled)throw new IOException("Reply stopped");if(!done)throw new IOException("Reply interrupted before completion");
            return answer.toString();
        }finally{activeStream=null;c.disconnect();}
    }
    /** Fresh server-bound Google nonce. Credential Manager receives this unchanged. */
    synchronized JSONObject googleBootstrap() throws Exception {
        discoverMode();clear();
        if(!firstParty)throw unsupported();
        JSONObject result=(JSONObject)call("/dz/identity/v1/provider/google/start",new JSONObject());
        googleState=result.optString("state","");
        String nonce=result.optString("nonce","");
        String client=result.optString("client_id","");
        if(googleState.isEmpty()||nonce.isEmpty()||cookies.value("__Host-dz_provider").isEmpty()
                ||!client.matches("[0-9]+-[A-Za-z0-9._-]+\\.apps\\.googleusercontent\\.com"))
            throw new IOException("Google challenge or client configuration was incomplete");
        return result;
    }
    synchronized void loginWithGoogle(String idToken,boolean signup) throws Exception {
        if(idToken==null||idToken.isEmpty()||idToken.length()>16000)
            throw new IOException("Invalid Google credential");
        try {
            if(!firstParty)throw unsupported();
            if(googleState.isEmpty())throw new IOException("Google challenge expired");
            call("/dz/identity/v1/provider/google/"+(signup?"signup":"complete"),new JSONObject().put("state",googleState).put("credential",idToken));
            googleState="";
            bootstrapCsrf="";
            ensurePersonal();
        } catch(Exception e) { clear(); throw e; }
    }
    synchronized boolean browserProviderAvailable(String provider) throws Exception {
        ensureMode();
        if(!firstParty)return false;
        if(!"discord".equals(provider))return false;
        try{return ((JSONObject)call("/dz/identity/v1/mobile/capabilities",null)).optBoolean(provider,false);}
        catch(ApiError e){if(e.status==404||e.status==503)return false;throw e;}
    }
    synchronized void redeemBrowserProvider(String provider,String ticket,String verifier) throws Exception {
        ensureMode();
        if(!firstParty||!Arrays.asList("google","discord").contains(provider))throw unsupported();
        if(!ticket.matches("[A-Za-z0-9_-]{43,128}")||!verifier.matches("[A-Za-z0-9_-]{43,128}"))throw new IOException("Invalid device proof");
        try{clear();call("/dz/identity/v1/mobile/"+provider+"/redeem",new JSONObject().put("ticket",ticket).put("verifier",verifier));ensurePersonal();}
        catch(Exception failure){clear();throw failure;}
    }
    synchronized boolean discordMobileAvailable() throws Exception {
        ensureMode();if(firstParty)return false;
        JSONObject response=(JSONObject)call("/api/auth/bootstrap",null);
        bootstrapCsrf=response.optString("csrf_token","");
        return response.optBoolean("discord_mobile_enabled",false);
    }
    synchronized void redeemDiscordMobile(String ticket,String verifier) throws Exception {
        ensureMode();if(firstParty)throw unsupported();
        if(ticket==null||!ticket.matches("[A-Za-z0-9_-]{40,120}")||
            verifier==null||!verifier.matches("[A-Za-z0-9_-]{43,128}"))
            throw new IOException("Discord device proof is invalid");
        try{
            JSONObject init=(JSONObject)call("/api/auth/bootstrap",null);
            bootstrapCsrf=init.optString("csrf_token","");
            if(!init.optBoolean("discord_mobile_enabled",false))
                throw new ApiError(503,"DISCORD_MOBILE_NOT_CONFIGURED","Discord mobile sign-in is not enabled.");
            call("/api/identities/discord/mobile/redeem",new JSONObject()
                .put("ticket",ticket).put("verifier",verifier));
            bootstrapCsrf="";
            ensurePersonal();
        }catch(Exception e){clear();throw e;}
    }
    private void bootstrap() throws Exception {
        clear();
        JSONObject result=(JSONObject)call("/api/auth/bootstrap",null);
        bootstrapCsrf=result.optString("csrf_token");
        if(bootstrapCsrf.isEmpty())throw new ApiError(403,"Server did not provide a secure authentication token.");
    }
    synchronized Object preauth(String action, JSONObject body) throws Exception {
        if(!Arrays.asList("signup","verify-email","resend-verification","forgot-password","reset-password","login").contains(action))
            throw new IOException("Unsupported account action");
        if("login".equals(action)||"signup".equals(action)||"forgot-password".equals(action))discoverMode();else ensureMode();
        if(firstParty){if(!"login".equals(action))throw new ApiError(503,"NATIVE_ACCOUNT_ACTION_UNAVAILABLE","Use DragonZpyder account recovery or registration at https://dragonzpyder.xyz/account before signing in here.");clear();return call("/dz/identity/v1/password/login",body);}
        bootstrap();
        try { return call("/api/auth/"+action,body); }
        catch(Exception failure){clear();throw failure;}
        finally {bootstrapCsrf="";}
    }
    synchronized void ensurePersonal() throws Exception {
        ensureMode();if(firstParty){if(cookies.value("__Host-dz_identity").isEmpty()||cookies.value("__Host-dz_csrf").isEmpty()||!((JSONObject)call("/dz/v2/personal/session",null)).optBoolean("authenticated"))throw new ApiError(401,"DragonZpyder identity session unavailable");authenticated=true;persist();return;}
        if(cookies.value("__Host-operly_session").isEmpty() || cookies.value("__Host-operly_csrf").isEmpty())
            throw new ApiError(401,"Server did not establish a secure session.");
        JSONArray sessions=(JSONArray)call("/api/auth/sessions",null);
        if(!personal(sessions)){
            call("/api/auth/personal-scope",new JSONObject());
            sessions=(JSONArray)call("/api/auth/sessions",null);
        }
        if(!personal(sessions))throw new ApiError(403,"Personal session unavailable");
        authenticated=true;persist();
    }
    private boolean personal(JSONArray sessions){
        for(int i=0;i<sessions.length();i++){
            JSONObject row=sessions.optJSONObject(i);
            if(row!=null&&row.optBoolean("current")&&"personal".equals(row.optString("scope")))return true;
        }
        return false;
    }
    synchronized void login(String email,String password) throws Exception {
        try {preauth("login",new JSONObject().put("email",email).put("password",password));ensurePersonal();}
        catch(Exception failure){clear();throw failure;}
    }
    synchronized void verify(String email,String code,String challenge) throws Exception {
        JSONObject body=new JSONObject().put("email",email).put("code",code);
        if(!challenge.isEmpty())body.put("challenge_id",challenge);
        try{preauth("verify-email",body);ensurePersonal();}
        catch(Exception failure){clear();throw failure;}
    }
    interface AgentProgress { void accept(String type,String value); }
    private static final class CancelContext {
        final String id,cookie,csrf;
        CancelContext(String id,String cookie,String csrf){this.id=id;this.cookie=cookie;this.csrf=csrf;}
    }
    private volatile CancelContext cancelContext;
    synchronized JSONObject streamAgent(JSONObject body,AgentProgress progress) throws Exception {
        if(!supportsAgentStream())throw unsupported();
        String id=UUID.fromString(body.getString("request_id")).toString();
        String token=csrf(ORIGIN),cookie=cookies.header();
        if(token.isEmpty()||cookie.isEmpty())throw new ApiError(401,"Secure session missing");
        HttpURLConnection c=(HttpURLConnection)ORIGIN.resolve("/dz/v2/personal/chat/stream").toURL().openConnection();
        c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(35000);
        c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Accept","text/event-stream");
        c.setRequestProperty("Origin",ORIGIN.toString());c.setRequestProperty("X-DZ-CSRF",token);c.setRequestProperty("Cookie",cookie);
        c.setRequestProperty("Cache-Control","no-store");cancelContext=new CancelContext(id,cookie,token);
        try{
            try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
            int status=c.getResponseCode();cookies.receive(c.getHeaderFields());
            if(status==401){clear();throw new ApiError(401,"Session expired");}
            if(status!=200)throw new ApiError(status,"Agent stream request failed ("+status+")");
            persist();
            if(c.getContentType()==null||!c.getContentType().toLowerCase(Locale.ROOT).startsWith("text/event-stream"))throw new IOException("Invalid agent stream response");
            try(BufferedReader reader=new BufferedReader(new InputStreamReader(c.getInputStream(),StandardCharsets.UTF_8))){
                String line;
                while((line=reader.readLine())!=null){
                    if(!line.startsWith("data:"))continue;
                    if(line.length()>512*1024)throw new IOException("Agent stream event exceeds limit");
                    JSONObject event=new JSONObject(line.substring(5).trim());String type=event.optString("type");
                    if("phase".equals(type))progress.accept(type,event.optString("message"));
                    else if("reset".equals(type))progress.accept(type,"");
                    else if("delta".equals(type))progress.accept(type,event.optString("text"));
                    else if("error".equals(type))throw new ApiError(event.optInt("status",503),event.optString("message","Agent execution unconfirmed"));
                    else if("done".equals(type)){
                        JSONObject result=event.optJSONObject("response");
                        if(result==null||!id.equals(result.optString("request_id")))throw new IOException("Agent response identity mismatch");
                        return result;
                    }
                }
            }
            throw new IOException("Agent stream ended without confirmed completion");
        }finally{cancelContext=null;c.disconnect();}
    }
    /** Separate HTTP connection: never wait for the synchronized streaming call. */
    JSONObject cancelAgent(String id) throws Exception {
        CancelContext context=cancelContext;
        if(context==null||!context.id.equals(id))throw new IOException("Agent stream is not active; check request status");
        HttpURLConnection c=(HttpURLConnection)ORIGIN.resolve("/dz/v2/personal/requests/"+UUID.fromString(id)+"/cancel").toURL().openConnection();
        c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(15000);
        c.setRequestMethod("POST");c.setDoOutput(true);
        c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Accept","application/json");c.setRequestProperty("Origin",ORIGIN.toString());
        c.setRequestProperty("Cookie",context.cookie);c.setRequestProperty("X-DZ-CSRF",context.csrf);
        try{
            try(OutputStream out=c.getOutputStream()){out.write("{}".getBytes(StandardCharsets.UTF_8));}
            int status=c.getResponseCode();if(status!=200)throw new ApiError(status,"Cancellation request not confirmed");
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            try(InputStream in=c.getInputStream()){byte[] bytes=new byte[4096];int count;while((count=in.read(bytes))!=-1){if(out.size()+count>256*1024)throw new IOException("Cancellation response exceeds limit");out.write(bytes,0,count);}}
            JSONObject result=new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
            if(!id.equals(result.optString("request_id")))throw new IOException("Cancellation response identity mismatch");
            return result;
        }finally{c.disconnect();}
    }
    synchronized JSONObject requestStatus(String id) throws Exception {
        if(!supportsRequestLedger())throw new IOException("Request recovery is unavailable on this server.");
        UUID requestId=UUID.fromString(id);
        return (JSONObject)call("/dz/v2/personal/requests/"+requestId,null);
    }
    synchronized JSONObject profile() throws Exception { ensureMode();return (JSONObject)call(firstParty?"/dz/identity/v1/me":"/api/auth/me",null); }
    synchronized void updateName(String name) throws Exception { ensureMode();call(firstParty?"/dz/identity/v1/me":"/api/auth/me","PATCH",object("display_name",name)); }
    synchronized void logout() throws Exception {
        ensureMode();call(firstParty?"/dz/identity/v1/logout":"/api/auth/logout", new JSONObject());
        clear();
    }
    synchronized void clear() { authenticated=false;requestBinding="";cookies.clear();bootstrapCsrf="";googleState="";if(store!=null)store.clear(); }
}
