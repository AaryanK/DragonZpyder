package xyz.dragonzpyder.android;

public final class ApiRoutePolicyTest {
    private static void require(boolean condition){if(!condition)throw new AssertionError("Route isolation failed");}
    public static void main(String[] args){
        require("/dz/v2/personal/chat".equals(ApiRoutePolicy.route(true,"/api/personal-agent/chat")));
        require("/dz/v2/personal/conversations".equals(ApiRoutePolicy.route(true,"/api/personal-agent/conversations")));
        require("/dz/v2/personal/conversations/00000000-0000-0000-0000-000000000001/messages".equals(ApiRoutePolicy.route(true,"/api/personal-agent/conversations/00000000-0000-0000-0000-000000000001/messages")));
        require(ApiRoutePolicy.route(true,"/api/auth/login")==null);
        require(ApiRoutePolicy.route(true,"/mesh/chat-stream")==null);
        require(ApiRoutePolicy.route(true,"/dz/internal/v1/chat/completions")==null);
        require(ApiRoutePolicy.route(true,"/dz/identity/v1/token")==null);
        require(ApiRoutePolicy.route(true,"/api/personal-agent/conversations/../../messages")==null);
        require(ApiRoutePolicy.route(true,"/api/personal-agent/conversations/not-a-uuid/messages")==null);
        require(ApiRoutePolicy.route(false,"/dz/v2/personal/chat")==null);
        require("/api/auth/login".equals(ApiRoutePolicy.route(false,"/api/auth/login")));
        require(ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/password/login"));
        require(ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/provider/google/complete"));
        require(!ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/logout"));
        require(!ApiRoutePolicy.nativePreauth(false,"/dz/identity/v1/password/login"));
        require("X-DZ-CSRF".equals(ApiRoutePolicy.csrfHeader(true)));
        require("X-CSRF-Token".equals(ApiRoutePolicy.csrfHeader(false)));
        System.out.println("Identity route contract passed");
    }
}
