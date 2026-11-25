package xyz.dragonzpyder.android;
import java.net.HttpCookie;
import java.util.*;

/** Only the explicitly known cookies for a fixed HTTPS origin are retained.
 * Never serialize Java's legacy RFC2965 $Version or quoted Cookie format. */
final class SessionCookies {
    private final Set<String> names;
    private final String[] session;
    private final Map<String,HttpCookie> jar=new LinkedHashMap<>();
    private final Map<String,Long> expiry=new HashMap<>();
    SessionCookies(){this(false);}
    SessionCookies(boolean firstParty){
        session=firstParty?new String[]{"__Host-dz_identity","__Host-dz_csrf"}:new String[]{"__Host-operly_session","__Host-operly_csrf"};
        names=new LinkedHashSet<>(Arrays.asList(session));
        if(firstParty)names.add("__Host-dz_provider");
        else names.addAll(Arrays.asList("operly_preauth_csrf","operly_google_nonce"));
    }
    void receive(Map<String,List<String>> headers) {
        for (Map.Entry<String,List<String>> header:headers.entrySet()) {
            if (!"Set-Cookie".equalsIgnoreCase(header.getKey())) continue;
            for (String raw:header.getValue()) {
                try {
                    for (HttpCookie c:HttpCookie.parse(raw)) {
                        String name=c.getName();
                        if(!names.contains(name) || c.getDomain()!=null || !"/".equals(c.getPath())) continue;
                        if(c.getMaxAge()==0 || c.getValue().isEmpty()) {jar.remove(name);expiry.remove(name);continue;}
                        if(!c.getSecure() || c.getValue()==null || !c.getValue().matches("[A-Za-z0-9._~%+/=-]+")) continue;
                        jar.put(name,c);
                        long age=c.getMaxAge();long now=System.currentTimeMillis();expiry.put(name,age<0?0L:now+Math.min(age,604800L)*1000L);
                    }
                } catch(IllegalArgumentException ignored) {}
            }
        }
    }
    String value(String name) {
        HttpCookie c=jar.get(name);
        if(c==null)return "";
        if(c.hasExpired()||(expiry.getOrDefault(name,0L)>0&&System.currentTimeMillis()>=expiry.get(name))){jar.remove(name);expiry.remove(name);return "";}
        return c.getValue();
    }
    String header() {
        StringJoiner join=new StringJoiner("; ");
        for(String name:names){String value=value(name);if(!value.isEmpty())join.add(name+"="+value);}
        return join.toString();
    }
    Properties snapshot(){
        Properties p=new Properties();
        for(String name:session){String token=value(name);long until=expiry.getOrDefault(name,0L);if(token.isEmpty()||until<=System.currentTimeMillis())return new Properties();p.setProperty(name,token);p.setProperty(name+".expiry",Long.toString(until));}
        return p;
    }
    void restore(Properties p){
        clear();
        try{
            long now=System.currentTimeMillis();
            for(String name:session){String token=p.getProperty(name,"");long until=Long.parseLong(p.getProperty(name+".expiry","0"));if(!token.matches("[A-Za-z0-9._~%+/=-]+")||until<=now||until>now+604800000L){clear();return;}
                HttpCookie c=new HttpCookie(name,token);c.setPath("/");c.setSecure(true);c.setMaxAge((until-now+999)/1000);jar.put(name,c);expiry.put(name,until);}
        }catch(RuntimeException e){clear();}
    }
    void clear(){jar.clear();expiry.clear();}
}
