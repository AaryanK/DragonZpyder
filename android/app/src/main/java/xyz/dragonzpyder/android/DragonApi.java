package xyz.dragonzpyder.android;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Native, first-party session client. No WebView, browser or service credentials. */
final class DragonApi {
    private static final URI ORIGIN = URI.create("https://dragonzpyder.xyz");
    private final SessionCookies cookies = new SessionCookies();
    private String bootstrapCsrf = "";
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
        String active = cookies.value("__Host-operly_csrf");
        return active.isEmpty() ? bootstrapCsrf : active;
    }
    synchronized Object call(String path, JSONObject body) throws Exception { return call(path,body==null?"GET":"POST",body); }
    synchronized Object call(String path, String method, JSONObject body) throws Exception {
        if (!path.startsWith("/api/") && !path.startsWith("/mesh/"))
            throw new IOException("Unsupported API route");
        URI uri = ORIGIN.resolve(path);
        if (!ORIGIN.getHost().equals(uri.getHost()) || !"https".equals(uri.getScheme()))
            throw new IOException("Unexpected API destination");
        HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(150000);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Cache-Control", "no-store");
        try {
            String cookieHeader = cookies.header();
            if (!cookieHeader.isEmpty()) connection.setRequestProperty("Cookie", cookieHeader);
            if (body != null) {
                String token = csrf(uri);
                if (token.isEmpty()) throw new ApiError(401, "Secure session missing. Sign in again.");
                connection.setRequestMethod(method);
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setRequestProperty("X-CSRF-Token", token);
                connection.setDoOutput(true);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            cookies.receive(connection.getHeaderFields());
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
            try { payload = new JSONTokener(raw).nextValue(); } catch (JSONException bad) { payload = new JSONObject(); }
            if (status >= 400) {
                Object detail = payload instanceof JSONObject ? ((JSONObject)payload).opt("detail") : null;
                String message = detail instanceof JSONObject ? ((JSONObject)detail).optString("message", "Request failed") :
                    detail instanceof String ? (String)detail : "Request failed (" + status + ")";
                throw new ApiError(status, detail instanceof JSONObject ? ((JSONObject)detail).optString("code","HTTP_"+status) : "HTTP_"+status, message);
            }
            return payload;
        } finally { connection.disconnect(); }
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
        bootstrap();
        try { return call("/api/auth/"+action,body); }
        catch(Exception failure){clear();throw failure;}
        finally {bootstrapCsrf="";}
    }
    synchronized void ensurePersonal() throws Exception {
        if(cookies.value("__Host-operly_session").isEmpty() || cookies.value("__Host-operly_csrf").isEmpty())
            throw new ApiError(401,"Server did not establish a secure session.");
        JSONArray sessions=(JSONArray)call("/api/auth/sessions",null);
        if(!personal(sessions)){
            call("/api/auth/personal-scope",new JSONObject());
            sessions=(JSONArray)call("/api/auth/sessions",null);
        }
        if(!personal(sessions))throw new ApiError(403,"Personal session unavailable");
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
    synchronized JSONObject profile() throws Exception { return (JSONObject)call("/api/auth/me",null); }
    synchronized void updateName(String name) throws Exception { call("/api/auth/me","PATCH",object("display_name",name)); }
    synchronized void logout() throws Exception {
        call("/api/auth/logout", new JSONObject());
        clear();
    }
    synchronized void clear() { cookies.clear(); bootstrapCsrf=""; }
}
