package xyz.dragonzpyder.android;
import java.net.HttpCookie;
import java.util.*;

/** Only the explicitly known cookies for a fixed HTTPS origin are retained.
 * Never serialize Java's legacy RFC2965 $Version or quoted Cookie format. */
final class SessionCookies {
    private static final Set<String> NAMES = new HashSet<>(Arrays.asList(
        "__Host-operly_session", "__Host-operly_csrf", "operly_preauth_csrf"));
    private final Map<String,HttpCookie> jar=new LinkedHashMap<>();
    void receive(Map<String,List<String>> headers) {
        for (Map.Entry<String,List<String>> header:headers.entrySet()) {
            if (!"Set-Cookie".equalsIgnoreCase(header.getKey())) continue;
            for (String raw:header.getValue()) {
                try {
                    for (HttpCookie c:HttpCookie.parse(raw)) {
                        String name=c.getName();
                        if(!NAMES.contains(name) || c.getDomain()!=null || !"/".equals(c.getPath())) continue;
                        if(c.getMaxAge()==0 || c.getValue().isEmpty()) {jar.remove(name);continue;}
                        if(!c.getSecure() || c.getValue()==null || !c.getValue().matches("[A-Za-z0-9._~%+/=-]+")) continue;
                        jar.put(name,c);
                    }
                } catch(IllegalArgumentException ignored) {}
            }
        }
    }
    String value(String name) {
        HttpCookie c=jar.get(name);
        if(c==null)return "";
        if(c.hasExpired()){jar.remove(name);return "";}
        return c.getValue();
    }
    String header() {
        StringJoiner join=new StringJoiner("; ");
        for(String name:NAMES){String value=value(name);if(!value.isEmpty())join.add(name+"="+value);}
        return join.toString();
    }
    void clear(){jar.clear();}
}
