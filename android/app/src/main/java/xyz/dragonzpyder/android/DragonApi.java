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
        final int status;
        ApiError(int status, String message) { super(message); this.status = status; }
    }
    static JSONObject object(String key, Object value) throws JSONException {
        return new JSONObject().put(key, value);
    }
    static String segment(String value) { return android.net.Uri.encode(value); }
    private String csrf(URI uri) {
        String active = cookies.value("__Host-operly_csrf");
        return active.isEmpty() ? bootstrapCsrf : active;
    }
    synchronized Object call(String path, JSONObject body) throws Exception {
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
                connection.setRequestMethod("POST");
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
                throw new ApiError(status, message);
            }
            return payload;
        } finally { connection.disconnect(); }
    }
    synchronized void login(String email, String password) throws Exception {
        clear();
        JSONObject bootstrap = (JSONObject) call("/api/auth/bootstrap", null);
        bootstrapCsrf = bootstrap.optString("csrf_token");
        try {
            call("/api/auth/login", new JSONObject().put("email",email).put("password",password));
            bootstrapCsrf = "";
            if (cookies.value("__Host-operly_session").isEmpty() || cookies.value("__Host-operly_csrf").isEmpty())
                throw new ApiError(401, "Server did not establish a secure session.");
            JSONArray sessions = (JSONArray) call("/api/auth/sessions", null);
            boolean personal = false;
            for (int i=0;i<sessions.length();i++) {
                JSONObject row=sessions.optJSONObject(i);
                if (row!=null && row.optBoolean("current") && "personal".equals(row.optString("scope"))) personal=true;
            }
            if (!personal) {
                call("/api/auth/personal-scope", new JSONObject());
                sessions = (JSONArray) call("/api/auth/sessions", null);
            }
            boolean ok = false;
            for (int i=0;i<sessions.length();i++) {
                JSONObject s=sessions.optJSONObject(i);
                if(s!=null && s.optBoolean("current") && "personal".equals(s.optString("scope"))) ok=true;
            }
            if (!ok) throw new ApiError(403,"Personal session unavailable");
        } catch(Exception failure) { clear(); throw failure; }
        finally { bootstrapCsrf=""; }
    }
    synchronized void logout() throws Exception {
        call("/api/auth/logout", new JSONObject());
        clear();
    }
    synchronized void clear() { cookies.clear(); bootstrapCsrf=""; }
}
