package xyz.dragonzpyder.android;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** Keeps the native identity cutover explicit and prevents cross-realm fallback. */
final class ApiRoutePolicy {
    private static final Set<String> FIRST_PARTY_PREAUTH=new HashSet<>(Arrays.asList(
        "/dz/identity/v1/password/login",
        "/dz/identity/v1/provider/google/start",
        "/dz/identity/v1/provider/google/complete",
        "/dz/identity/v1/provider/google/signup"));
    private static final Set<String> FIRST_PARTY_ROUTES=new HashSet<>(Arrays.asList(
        "/dz/v2/personal/session", "/dz/v2/personal/chat", "/dz/v2/personal/conversations",
        "/dz/identity/v1/me", "/dz/identity/v1/logout",
        "/dz/internal/mcp/connections", "/dz/internal/mcp/providers", "/dz/v2/personal/goals", "/dz/internal/mcp/connections/native/complete"));
    private ApiRoutePolicy(){}
    static String route(boolean firstParty,String requested){
        if(requested==null||requested.contains("..")||requested.contains("\\")||requested.contains("#"))return null;
        if(!firstParty)return requested.startsWith("/api/")||requested.startsWith("/mesh/")?requested:null;
        String value=requested;
        if(value.equals("/api/personal-agent/chat"))value="/dz/v2/personal/chat";
        else if(value.equals("/api/personal-agent/conversations")||value.startsWith("/api/personal-agent/conversations/"))
            value="/dz/v2/personal/"+value.substring("/api/personal-agent/".length());
        if(FIRST_PARTY_ROUTES.contains(value)||FIRST_PARTY_PREAUTH.contains(value))return value;
        if(value.matches("/dz/v2/personal/conversations/[0-9a-fA-F-]{36}/messages"))return value;
        if(value.matches("/dz/v2/personal/requests/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))return value;
        if(value.matches("/dz/v2/personal/goals/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(/cancel)?"))return value;
        if(value.matches("/dz/internal/mcp/connections/c[a-f0-9]{30}"))return value;
        if(value.matches("/dz/internal/mcp/connections/[a-z][a-z0-9_-]{1,30}/native/start"))return value;
        return null;
    }
    static boolean nativePreauth(boolean firstParty,String path){return firstParty&&FIRST_PARTY_PREAUTH.contains(path);}
    static String csrfHeader(boolean firstParty){return firstParty?"X-DZ-CSRF":"X-CSRF-Token";}
}
