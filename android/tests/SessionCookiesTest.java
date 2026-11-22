package xyz.dragonzpyder.android;
import java.util.*;
public final class SessionCookiesTest {
    private static void require(boolean condition) {
        if (!condition) throw new AssertionError("Session cookie contract failed");
    }
    public static void main(String[] args) {
        SessionCookies jar=new SessionCookies();
        jar.receive(Collections.singletonMap("Set-Cookie",Arrays.asList(
            "operly_preauth_csrf=preauth_test; Max-Age=3600; Path=/; Secure; SameSite=Strict")));
        require(jar.header().equals("operly_preauth_csrf=preauth_test"));
        jar.receive(Collections.singletonMap("set-cookie",Arrays.asList(
            "__Host-operly_session=abc-123; HttpOnly; Max-Age=604800; Path=/; Secure; SameSite=Strict",
            "__Host-operly_csrf=csrf-456; Max-Age=604800; Path=/; Secure; SameSite=Strict",
            "operly_preauth_csrf=\"\"; Max-Age=0; Path=/")));
        require(jar.value("__Host-operly_session").equals("abc-123"));
        require(jar.value("__Host-operly_csrf").equals("csrf-456"));
        require(jar.value("operly_preauth_csrf").isEmpty());
        require(jar.header().contains("__Host-operly_csrf=csrf-456"));
        require(!jar.header().contains("$Version") && !jar.header().contains("\""));
        jar.receive(Collections.singletonMap("Set-Cookie",Arrays.asList(
            "__Host-operly_csrf=wrong; Domain=dragonzpyder.xyz; Path=/; Secure",
            "__Host-operly_csrf=wrong2; Path=/",
            "__Host-operly_csrf=wrong3; Path=/api; Secure")));
        require(jar.value("__Host-operly_csrf").equals("csrf-456"));
        jar.receive(Collections.singletonMap("Set-Cookie",Arrays.asList(
            "__Host-operly_csrf=rotated; Max-Age=604800; Path=/; Secure; SameSite=Strict")));
        require(jar.value("__Host-operly_csrf").equals("rotated"));
        Properties snapshot=jar.snapshot();require(snapshot.size()==4);
        SessionCookies restored=new SessionCookies();restored.restore(snapshot);require(restored.value("__Host-operly_session").equals("abc-123"));require(restored.value("__Host-operly_csrf").equals("rotated"));
        require(restored.value("operly_preauth_csrf").isEmpty());
        snapshot.setProperty("__Host-operly_session.expiry","1");restored.restore(snapshot);require(restored.header().isEmpty());
        jar.clear(); require(jar.header().isEmpty());require(jar.snapshot().isEmpty());
        System.out.println("Session cookie contract passed");
    }
}
