import {test,expect} from "@playwright/test";

// The existing companion adapter must remain the only source of voice sessions.
// These tests do not claim to complete a live provider call in mocked CI.
test.beforeEach(async ({page})=>{
  await page.route("**/api/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    let body={};
    if(path==="/api/auth/sessions")body=[{id:"fixture",current:true,scope:"personal",device:"test"}];
    if(path==="/api/personal-agent/conversations"||path.endsWith("/approvals"))body=[];
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  });
  await page.route("**/mesh/**",async route=>route.fulfill({status:200,contentType:"application/json",body:'{"models":[],"imageEnabled":false,"videoEnabled":false}'}));
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
});

test("Live voice uses the supplied full-screen orb without replacing the chat composer",async ({page})=>{
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel).toBeVisible();
  await expect(panel.locator("canvas.dz-voice-orb-stage")).toBeVisible();
  await expect(panel.getByText("Voice, without interruption.")).toBeVisible();
  await expect(panel.getByRole("button",{name:"End conversation"})).toBeVisible();
  await expect(page.locator("#message-input")).toBeAttached();
  await expect(page.locator("#companion-audio")).toHaveCount(1);
  await panel.getByRole("button",{name:"End conversation"}).click();
  await expect(panel).toBeHidden();
});

test("Voice transcript is revealed on demand and retains production transcript container",async ({page})=>{
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  const transcript=panel.locator("#companion-transcript");
  await expect(transcript).toHaveCount(1);
  await expect(panel.getByRole("button",{name:"Show transcript"})).toBeVisible();
  await panel.getByRole("button",{name:"Show transcript"}).click();
  await expect(transcript).toBeVisible();
  await panel.getByRole("button",{name:"Hide transcript"}).click();
  await expect(transcript).toBeHidden();
  await panel.getByRole("button",{name:"End conversation"}).click();
});

test("Voice playback toggle controls the real audio element",async ({page})=>{
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await panel.getByRole("button",{name:"Mute speaker"}).click();
  await expect.poll(()=>page.locator("#companion-audio").evaluate(element=>element.muted)).toBe(true);
  await panel.getByRole("button",{name:"Unmute speaker"}).click();
  await expect.poll(()=>page.locator("#companion-audio").evaluate(element=>element.muted)).toBe(false);
  await panel.getByRole("button",{name:"End conversation"}).click();
});

test("Voice orb does not introduce horizontal overflow on mobile",async ({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel.locator("canvas")).toBeVisible();
  const bounds=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,screen:innerWidth}));
  expect(bounds.scroll).toBeLessThanOrEqual(bounds.screen+1);
  await panel.getByRole("button",{name:"End conversation"}).click();
});
