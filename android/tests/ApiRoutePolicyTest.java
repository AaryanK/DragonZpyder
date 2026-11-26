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
        for(String provider:new String[]{"discord"}){
            String redeem="/dz/identity/v1/mobile/"+provider+"/redeem";
            require(redeem.equals(ApiRoutePolicy.route(true,redeem)));
            require(ApiRoutePolicy.nativePreauth(true,redeem));
            require(!ApiRoutePolicy.nativePreauth(false,redeem));
            require(ApiRoutePolicy.route(false,redeem)==null);
            require(ApiRoutePolicy.route(true,redeem+"/extra")==null);
            require(ApiRoutePolicy.route(true,redeem+"?redirect=https://evil.example")==null);
            require(ApiRoutePolicy.route(true,redeem+"#fragment")==null);
            require(ApiRoutePolicy.route(true,redeem.replace("/redeem","/callback"))==null);
        }
        require(ApiRoutePolicy.route(true,"/dz/identity/v1/mobile/google/redeem")==null);
        require(!ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/mobile/google/redeem"));
        require(ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/provider/google/start"));
        require(ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/provider/google/signup"));
        require("/dz/identity/v1/mobile/capabilities".equals(ApiRoutePolicy.route(true,"/dz/identity/v1/mobile/capabilities")));
        require(!ApiRoutePolicy.nativePreauth(true,"/dz/identity/v1/mobile/capabilities"));
        require(ApiRoutePolicy.route(true,"/dz/identity/v1/mobile/unknown/redeem")==null);
        require(ApiRoutePolicy.route(true,"/dz/identity/v1/mobile/google/%72edeem")==null);
        require(ApiRoutePolicy.route(true,"//evil.example/dz/identity/v1/mobile/google/redeem")==null);
        System.out.println("Identity route contract passed");
    }
}
