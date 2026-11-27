import { test, expect } from "@playwright/test";

test("native Agent mode never calls the Operly proxy and scopes MCP aliases", async ({ page }) => {
  const oldRoutes = [];
  const chats = [];
  const alias = "c" + "1".repeat(30);
  // Browser owns the CSRF cookie. An opaque bearer never enters model context.
  await page.context().addCookies([{
    name: "__Host-dz_csrf", value: "synthetic-native-csrf", secure: true,
    sameSite: "Lax", url: "https://127.0.0.1:5189",
  }]);

  await page.route("**/api/**", async route => {
    oldRoutes.push(new URL(route.request().url()).pathname);
    await route.fulfill({ status: 410, contentType: "application/json",
      body: JSON.stringify({ detail: "Retired Operly API" }) });
  });
  await page.route("**/dz/status", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ web_cutover_enabled: true }),
  }));
  await page.route("**/dz/v2/personal/session", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ authenticated: true, runtime: "dragonzpyder" }),
  }));
  await page.route("**/dz/v2/personal/conversations", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ conversations: [] }),
  }));
  await page.route("**/dz/internal/mcp/providers", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ providers: [] }),
  }));
  await page.route("**/dz/internal/mcp/connections", route => route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ connections: [
      { connection_id: alias, status: "active", label: "Test workspace", provider_id: "operly" },
    ] }),
  }));
  await page.route("**/dz/v2/personal/chat", async route => {
    expect(route.request().headers()["x-dz-csrf"]).toBe("synthetic-native-csrf");
    expect(route.request().headers()["x-csrf-token"]).toBeUndefined();
    chats.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ conversation_id: "00000000-0000-4000-8000-000000000001",
        message: "DragonZpyder native runtime", dispatch: "dragonzpyder_first_party",
        execution_receipts: { tool_names: [], failed_tool_count: 0, status: "completed" } }) });
  });
  await page.goto("/app");
  await expect(page.locator("#auth-modal")).toBeHidden();
  await expect(page.locator("#mesh-switch")).toBeHidden();
  await page.getByRole("button", { name: "Connections & tools" }).first().click();
  await expect(page.getByRole("dialog", { name: "DragonZpyder MCP connections" })).toBeVisible();
  await page.getByRole("dialog", { name: "DragonZpyder MCP connections" }).getByRole("checkbox").check();
  await page.getByRole("button", { name: /Close/ }).last().click();
  await page.locator("#message-input").fill("Research this for me");
  await page.locator("#composer").evaluate(element => element.requestSubmit());
  await expect(page.getByText("DragonZpyder native runtime")).toBeVisible();
  expect(chats.length).toBe(1);
  expect(chats[0].mcp_connection_ids).toEqual([alias]);
  expect(oldRoutes).toEqual([]);
});


test("native archived transcripts are read-only and never submitted to the harness", async ({ page }) => {
  const cid = "00000000-0000-4000-8000-000000000012";
  const calls = [];
  await page.route("**/api/**", route => route.fulfill({status:410,body:"legacy disabled"}));
  await page.route("**/dz/status", route => route.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/session", route => route.fulfill({json:{authenticated:true,runtime:"dragonzpyder"}}));
  await page.route("**/dz/v2/personal/conversations", route => route.fulfill({json:{conversations:[]}}));
  await page.route("**/dz/v2/personal/archive/conversations?*", route => route.fulfill({
    json:{conversations:[{id:cid,title:"Imported conversation",archived:true}],next_offset:null}
  }));
  await page.route("**/dz/v2/personal/archive/conversations/*/messages?*", route => {
    const offset = new URL(route.request().url()).searchParams.get("offset");
    return route.fulfill({json:{archived:true,messages:[{role:"user",content:offset==="0"?"<img src=x onerror=alert(1)>":"Second page"}],next_offset:offset==="0"?10:null}});
  });
  await page.route("**/dz/v2/personal/chat", route => { calls.push(route.request().postDataJSON()); return route.fulfill({json:{conversation_id:cid,message:"Unexpected send"}}); });
  await page.goto("/app");
  await expect(page.getByRole("button",{name:"Archive · Imported conversation"})).toBeVisible();
  await expect(page.getByText("Read-only Operly archive. Start a new chat to use DragonZpyder.")).toBeVisible();
  await expect(page.getByText("<img src=x onerror=alert(1)>",{exact:true})).toBeVisible();
  await expect(page.getByText("Second page",{exact:true})).toBeVisible();
  await expect(page.locator("#message-input")).toBeDisabled();
  await page.locator("#composer").evaluate(form => form.requestSubmit());
  expect(calls).toEqual([]);
});


test("migration proof pilot does not sign in or call Operly", async ({page}) => {
  const legacy=[], login=[], proofs=[];
  const ref="00000000-0000-4000-8000-000000000023";
  await page.route("**/api/**",route=>{legacy.push(route.request().url());return route.fulfill({status:410,body:"not allowed"});});
  await page.route("**/dz/import-proof/status",route=>route.fulfill({json:{enabled:true}}));
  await page.route("**/dz/identity/v1/import-proof/google/start",route=>route.fulfill({status:503,json:{detail:"not configured"}}));
  await page.route("**/dz/identity/v1/password/login",route=>{login.push(route.request().url());return route.fulfill({status:500});});
  await page.route("**/dz/identity/v1/import-proof/password",route=>{
    proofs.push(route.request().postDataJSON());
    return route.fulfill({status:202,json:{proof_reference:ref,status:"awaiting_review"}});
  });
  await page.goto("/account?mode=migration");
  await expect(page.getByRole("heading",{name:"Verify your existing account."})).toBeVisible();
  await page.locator("#migration-email").fill("synthetic@example.test");
  await page.locator("#migration-password").fill("synthetic-test-password");
  await page.getByRole("button",{name:"Verify existing account"}).click();
  await expect(page.getByText("Verification recorded. No account has been activated. Review reference: "+ref)).toBeVisible();
  await expect(page.locator("#migration-password")).toHaveValue("");
  expect(proofs).toEqual([{email:"synthetic@example.test",password:"synthetic-test-password"}]);
  expect(legacy).toEqual([]);
  expect(login).toEqual([]);
  expect(new URL(page.url()).pathname).toBe("/account");
});

test("migration proof pilot fails closed when disabled", async ({page})=>{
  await page.route("**/dz/import-proof/status",route=>route.fulfill({json:{enabled:false}}));
  await page.goto("/account?mode=migration");
  await expect(page.getByText("Account migration verification is not available. Return to /account for regular access.")).toBeVisible();
  await expect(page.locator("#migration-form")).toBeHidden();
  await expect(page.locator("#login-form")).toBeHidden();
});


for(const entry of ["/login","/account"]) test("only native login before global web cutover: "+entry, async ({page}) => {
    const legacy = [], logins = [];
    await page.route("**/api/**", route => { legacy.push(route.request().url()); return route.fulfill({status:410}); });
    await page.route("**/dz/status", route => route.fulfill({json:{web_cutover_enabled:false,native_session_present:logins.length>0}}));
    await page.route("**/dz/recovery/status", route => route.fulfill({json:{enabled:false}}));
    await page.route("**/dz/identity/v1/provider/google/start", route => route.fulfill({status:503}));
    await page.route("**/dz/identity/v1/me", route => route.fulfill(logins.length?
        {json:{id:"test-account",email:"test@example.test"}}:{status:401}));
    await page.route("**/dz/identity/v1/password/login", route => {
        logins.push(route.request().postDataJSON()); return route.fulfill({json:{authenticated:true}});
    });
    await page.route("**/dz/v2/personal/session", route => route.fulfill({json:{authenticated:true,runtime:"dragonzpyder"}}));
    await page.route("**/dz/v2/personal/conversations", route => route.fulfill({json:{conversations:[]}}));
    await page.goto(entry);
    await expect(page.getByText("Use an existing Operly account")).toHaveCount(0);
    await expect(page.locator("#dragonzpyder-central-signin")).toHaveCount(0);
    await page.locator("#login-email").fill("test@example.test");
    await page.locator("#login-password").fill("test-password");
    await page.locator("#login-form button[type=submit]").click();
    await expect(page).toHaveURL(/\/app$/);
    expect(logins).toEqual([{email:"test@example.test",password:"test-password"}]);
    expect(legacy).toEqual([]);
});

test("native identity initials are not the device name and unavailable chat cannot submit", async ({page}) => {
  let submissions=0;
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({json:{authenticated:true,native_chat_enabled:false}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({json:{display_name:"Ada Lovelace"}}));
  await page.route("**/dz/v2/personal/chat",r=>{submissions++;return r.fulfill({json:{}})});
  await page.goto("/app");
  await expect(page.locator("#profile-initial")).toHaveText("AL");
  await expect(page.locator("#dz-runtime-notice")).toBeVisible();
  await expect(page.getByText("Conversation history is unavailable while the runtime is offline.")).toBeVisible();
  await page.locator("#message-input").fill("Preserve this draft");
  await expect(page.locator("#send-button")).toBeDisabled();
  await expect(page.locator(".prompt-chip").first()).toBeDisabled();
  await page.locator("#composer").evaluate(form=>form.requestSubmit());
  await expect(page.locator("#message-input")).toHaveValue("Preserve this draft");
  expect(submissions).toBe(0);
});

test("native Personal goals show server receipts without legacy execution", async ({page}) => {
  const id="00000000-0000-4000-8000-000000000042",legacy=[];
  await page.route("**/api/**",r=>{legacy.push(r.request().url());return r.fulfill({status:410,body:"legacy retired"})});
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({json:{authenticated:true,native_chat_enabled:true}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({json:{display_name:"Ada Lovelace"}}));
  await page.route("**/dz/v2/personal/conversations",r=>r.fulfill({json:{conversations:[]}}));
  await page.route("**/dz/v2/personal/archive/conversations?*",r=>r.fulfill({json:{conversations:[],next_offset:null}}));
  await page.route("**/dz/v2/personal/goals",r=>r.fulfill({json:{goals:[{goal_id:id,state:"active",completed_wakes:2,total_wakes:5,updated_at:"2026-11-26T00:00:00Z"}]}}));
  await page.route("**/dz/v2/personal/goals/"+id,r=>r.fulfill({json:{goal_id:id,state:"active",receipts:[{sequence:1,status:"completed",tool_names:["tasks.list"],at:"2026-11-26T00:00:00Z"}]}}));
  await page.goto("/app");
  await page.locator(".sidebar").getByRole("button",{name:"Tasks & goals"}).click();
  const dialog=page.getByRole("dialog",{name:"DragonZpyder Personal goals"});
  await expect(dialog.getByText("2 of 5 scheduled wakes")).toBeVisible();
  await dialog.getByRole("button",{name:"Details",exact:true}).click();
  await expect(dialog.getByText("tasks.list",{exact:true})).toBeVisible();
  await dialog.getByRole("button",{name:"Cancel goal",exact:true}).click();
  await expect(dialog.getByRole("button",{name:"Confirm cancellation"})).toBeVisible();
  await dialog.getByRole("button",{name:"Keep goal"}).click();
  await expect(dialog.getByRole("button",{name:"Confirm cancellation"})).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect(legacy).toEqual([]);
});

test("verified avatar uses only the owner-scoped image route and falls back when unavailable",async({page})=>{
  let missing=false,requests=0;
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({json:{authenticated:true,native_chat_enabled:false}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({json:{display_name:"Ada Lovelace",avatar_available:true}}));
  await page.route("**/dz/identity/v1/avatar",r=>{
    requests++;return missing?r.fulfill({status:404,body:"unavailable"}):r.fulfill({contentType:"image/png",body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8R0AAAAASUVORK5CYII=","base64")});
  });
  await page.goto("/app");
  await expect(page.locator("#profile-avatar")).toBeVisible();
  await expect(page.locator("#profile-initial")).toBeHidden();
  expect(requests).toBe(1);
  missing=true;await page.reload();
  await expect(page.locator("#profile-initial")).toHaveText("AL");
  await expect(page.locator("#profile-initial")).toBeVisible();
  await expect(page.locator("#profile-avatar")).toBeHidden();
});

test("native realtime voice preserves orb and uses owner-scoped start and hangup",async({page})=>{
  const starts=[],ends=[],legacy=[];
  await page.context().addCookies([{name:"__Host-dz_csrf",value:"native-voice-csrf",secure:true,sameSite:"Lax",url:"https://127.0.0.1:5189"}]);
  await page.addInitScript(()=>{
    window.__voiceNative={closed:0,stopped:0};
    const track={enabled:true,stop(){window.__voiceNative.stopped++}};
    Object.defineProperty(navigator,"mediaDevices",{configurable:true,value:{getUserMedia:async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]})}});
    class Peer {
      addTrack(){}
      createDataChannel(){return {readyState:"open",close(){},send(){}}}
      async createOffer(){return {type:"offer",sdp:"v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"}}
      async setLocalDescription(o){this.localDescription=o}
      async setRemoteDescription(a){window.__voiceNative.answer=a.sdp}
      close(){window.__voiceNative.closed++}
    }
    Object.defineProperty(window,"RTCPeerConnection",{configurable:true,value:Peer});
  });
  await page.route("**/api/**",r=>{legacy.push(r.request().url());return r.fulfill({status:410})});
  await page.route("**/companion/realtime",r=>{legacy.push(r.request().url());return r.fulfill({status:410})});
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({json:{authenticated:true,native_chat_enabled:true,voice_enabled:true}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({json:{display_name:"Test User"}}));
  await page.route("**/dz/v2/personal/conversations",r=>r.fulfill({json:{conversations:[]}}));
  await page.route("**/dz/v2/personal/archive/conversations?*",r=>r.fulfill({json:{conversations:[],next_offset:null}}));
  await page.route("**/dz/v2/personal/voice/start",r=>{
    expect(r.request().headers()["x-dz-csrf"]).toBe("native-voice-csrf");
    expect(r.request().headers()["x-csrf-token"]).toBeUndefined();
    const body=r.request().postDataJSON();starts.push(body);
    return r.fulfill({json:{session_id:body.session_id,sdp:body.sdp,duration_seconds:60,expires_at:new Date(Date.now()+60000).toISOString()}});
  });
  await page.route("**/dz/v2/personal/voice/*/end",r=>{
    const id=new URL(r.request().url()).pathname.split("/").at(-2);ends.push(id);
    expect(r.request().headers()["x-dz-csrf"]).toBe("native-voice-csrf");
    return r.fulfill({json:{session_id:id,state:"closed"}});
  });
  await page.goto("/app");
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel.locator("canvas.dz-voice-original-canvas")).toBeVisible();
  await expect(panel.getByText("VOICE CONNECTED")).toBeVisible();
  await panel.getByRole("button",{name:"Mute microphone"}).click();
  await expect(panel.getByRole("button",{name:"Unmute microphone"})).toBeEnabled();
  await panel.getByRole("button",{name:"End conversation"}).click();
  await expect(panel).toBeHidden();
  await expect.poll(()=>ends.length).toBe(1);
  expect(starts.length).toBe(1);expect(ends[0]).toBe(starts[0].session_id);
  expect(await page.evaluate(()=>window.__voiceNative.stopped)).toBe(1);
  expect(legacy).toEqual([]);
});

test("signed-out native chat goes directly to compact sign-in",async({page})=>{
  const legacy=[];
  await page.setViewportSize({width:360,height:740});
  await page.route("**/api/**",r=>{legacy.push(r.request().url());return r.fulfill({status:410})});
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/status",r=>r.fulfill({json:{}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({status:401,json:{detail:"Sign in required"}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({status:401}));
  await page.route("**/dz/recovery/status",r=>r.fulfill({json:{enabled:false}}));
  await page.route("**/dz/identity/v1/provider/google/start",r=>r.fulfill({status:503}));
  await page.goto("/app");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading",{name:"Sign in",exact:true})).toBeVisible();
  await expect(page.locator("#login-email")).toBeInViewport();
  await expect(page.locator("#login-password")).toBeInViewport();
  await expect(page.locator("#legacy-login-link")).toHaveCount(0);
  await expect(page.locator(".intro")).toHaveCount(0);
  expect(legacy).toEqual([]);
});
test("failed native session probe offers retry, not a duplicate credential form",async({page})=>{
  await page.route("**/dz/status",r=>r.fulfill({json:{web_cutover_enabled:true}}));
  await page.route("**/dz/v2/personal/status",r=>r.fulfill({json:{}}));
  await page.route("**/dz/v2/personal/session",r=>r.fulfill({status:503,json:{detail:"Runtime unavailable"}}));
  await page.goto("/app");
  await expect(page.getByRole("dialog",{name:"Unable to connect"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Try again"})).toBeVisible();
  await expect(page.locator("#login-form")).toHaveCount(0);
});

test("mobile sign-in has one brand and accessible password visibility",async({page})=>{
  await page.setViewportSize({width:360,height:640});
  await page.route("**/dz/recovery/status",r=>r.fulfill({json:{enabled:false}}));
  await page.route("**/dz/identity/v1/me",r=>r.fulfill({status:401}));
  await page.route("**/dz/identity/v1/provider/google/start",r=>r.fulfill({status:503}));
  await page.goto("/login");
  await expect(page.locator(".dz-auth-brand")).toBeVisible();
  await expect(page.locator("header.top")).toBeHidden();
  await expect(page.locator("#login-form button[type=submit]")).toBeInViewport();
  await page.locator("#login-password").fill("synthetic-test-password");
  await page.getByRole("button",{name:"Show password"}).click();
  await expect(page.locator("#login-password")).toHaveAttribute("type","text");
  await page.getByRole("button",{name:"Hide password"}).click();
  await expect(page.locator("#login-password")).toHaveAttribute("type","password");
  await page.getByRole("button",{name:"Create account"}).click();
  await expect(page.getByText("Google sign-up is temporarily unavailable.")).toBeVisible();
  await expect(page.getByRole("button",{name:"Try again"})).toBeVisible();
  await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await expect(page.locator("#login-password")).toHaveValue("");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(361);
});
