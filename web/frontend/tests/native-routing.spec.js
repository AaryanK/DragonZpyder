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
  await page.getByRole("checkbox").check();
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


test("dedicated native login works before global web cutover", async ({page}) => {
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
    await page.goto("/login");
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
