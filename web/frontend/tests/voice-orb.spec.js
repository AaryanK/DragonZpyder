import { test, expect } from "@playwright/test";

// Voice uses the existing companion transport. These browser tests inspect
// native React presentation only; they do not simulate provider success.
test.beforeEach(async ({ page }) => {
  // These presentation tests inject session events; do not acquire a real microphone.
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", { configurable:true, value:{getUserMedia:() => new Promise(() => {})} });
  });
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if (path === "/api/auth/sessions") body = [{ id:"fixture", current:true, scope:"personal", device:"test" }];
    if (path === "/api/personal-agent/conversations" || path.endsWith("/approvals")) body = [];
    await route.fulfill({ status:200, contentType:"application/json", body:JSON.stringify(body) });
  });
  await page.route("**/mesh/**", async route => route.fulfill({
    status:200, contentType:"application/json",
    body:'{"models":[],"imageEnabled":false,"videoEnabled":false}',
  }));
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
});

test("React voice controls surround the original uploaded fluid canvas, not a copied iframe", async ({ page }) => {
  await page.setViewportSize({width:1094,height:617});
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel).toBeVisible();
  const canvas=panel.locator("canvas.dz-voice-original-canvas");
  await expect(canvas).toBeVisible();
  await expect(panel.locator("iframe")).toHaveCount(0);
  await expect(panel.locator(".dz-voice-art-svg")).toHaveCount(0);
  await expect(panel.locator("img.dz-voice-brandmark")).toHaveAttribute("src","/brand-icon.png");
  await expect(panel.getByText("Your intelligence, in conversation.")).toBeVisible();
  await expect(panel.getByRole("button",{name:"End conversation"})).toBeVisible();
  await expect(page.locator("#message-input")).toBeAttached();
  await expect(panel.locator("#companion-audio")).toHaveCount(1);
  const art=await canvas.evaluate(el=>{
    const radius=Number(el.dataset.orbRadius),centerY=Number(el.dataset.orbCenterY);
    const context=el.getContext("2d");
    const rect=el.getBoundingClientRect();
    const scale=el.width/rect.width;
    const pixel=context.getImageData(Math.round(rect.width*.5*scale),Math.round(centerY*scale),1,1).data;
    return {radius,centerY,pixel:[...pixel],width:rect.width,height:rect.height};
  });
  // The preview's original geometry at 1094x617 is (cy=.435H, R=.248H).
  expect(art.radius).toBeGreaterThan(150);
  expect(art.radius).toBeLessThan(156);
  expect(art.centerY).toBeGreaterThan(265);
  expect(art.centerY).toBeLessThan(272);
  expect(art.width).toBe(1094);
  expect(art.height).toBe(617);
  expect(art.pixel[0]+art.pixel[1]+art.pixel[2]).toBeGreaterThan(70);
  await panel.getByRole("button",{name:"End conversation"}).click();
  await expect(panel).toBeHidden();
});

test("React owns real event-driven voice status and transcript, not DOM text injection", async ({ page }) => {
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-state", { detail: { kind:"thinking", message:"Thinking…" } }));
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-transcript", {
      detail:{ id:"transcript-1", label:"You", value:"Hello DragonZpyder", append:false },
    }));
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-transcript", {
      detail:{ id:"transcript-1", label:"You", value:" please help", append:true },
    }));
  });
  await expect(panel.locator("#companion-status")).toHaveText("Thinking…");
  await expect(panel.getByRole("button", { name:"Show transcript" })).toBeVisible();
  await panel.getByRole("button", { name:"Show transcript" }).click();
  await expect(panel.locator("#companion-transcript")).toContainText("Hello DragonZpyder please help");
  await panel.getByRole("button", { name:"Hide transcript" }).click();
  await expect(panel.locator("#companion-transcript")).toBeHidden();
  await panel.getByRole("button", { name:"End conversation" }).click();
});

test("microphone action becomes available only on confirmed WebRTC session event", async ({ page }) => {
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  const mic = panel.getByRole("button", { name:"Mute microphone" });
  await expect(mic).toBeDisabled();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("dragonzpyder:voice-session", { detail:{connected:true} })));
  await expect(mic).toBeEnabled();
  await expect(panel.getByText("VOICE CONNECTED")).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("dragonzpyder:voice-mute", { detail:{muted:true} })));
  await expect(panel.getByRole("button", { name:"Unmute microphone" })).toBeEnabled();
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("dragonzpyder:voice-session", { detail:{connected:false} })));
  await expect(panel.getByRole("button", { name:"Unmute microphone" })).toBeDisabled();
  await panel.getByRole("button", { name:"End conversation" }).click();
});

test("speaker button still controls the one real provider audio element", async ({ page }) => {
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await panel.getByRole("button", { name:"Mute speaker" }).click();
  await expect.poll(() => page.locator("#companion-audio").evaluate(element => element.muted)).toBe(true);
  await panel.getByRole("button", { name:"Unmute speaker" }).click();
  await expect.poll(() => page.locator("#companion-audio").evaluate(element => element.muted)).toBe(false);
  await panel.getByRole("button", { name:"End conversation" }).click();
});

test("original canvas voice view fits phone without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width:390, height:844 });
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await expect(panel.locator(".dz-voice-original-canvas")).toBeVisible();
  const bounds = await page.evaluate(() => ({
    scroll:document.documentElement.scrollWidth,
    screen:innerWidth,
    artwork:document.querySelector(".dz-voice-orb-shell").getBoundingClientRect().width,
  }));
  expect(bounds.scroll).toBeLessThanOrEqual(bounds.screen + 1);
  expect(bounds.artwork).toBeLessThanOrEqual(bounds.screen + 1);
  const controls = await panel.locator(".dz-voice-orb-controls").boundingBox();
  const end = await panel.getByRole("button", { name:"End conversation" }).boundingBox();
  expect(controls).not.toBeNull();
  expect(end).not.toBeNull();
  // The compact close action must sit beneath the main controls, never cover them.
  expect(end.y).toBeGreaterThanOrEqual(controls.y + controls.height - 2);
  const style = await panel.getByRole("button", { name:"End conversation" }).evaluate(button => {
    const css = getComputedStyle(button);
    return { background: css.backgroundColor, fontSize: parseFloat(css.fontSize), width: button.getBoundingClientRect().width };
  });
  expect(style.background).not.toBe("rgb(238, 234, 225)");
  expect(style.fontSize).toBeLessThan(14);
  expect(style.width).toBeLessThan(200);
  await panel.getByRole("button", { name:"End conversation" }).click();
});


test("mobile error state keeps the rendered orb separate from diagnostics and controls", async ({ page }) => {
  await page.setViewportSize({ width:390, height:700 });
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("dragonzpyder:voice-state", {
    detail:{kind:"error", message:"Live voice is not configured"}
  })));
  await expect(panel.getByRole("button", { name:"Back to chat" })).toBeVisible();
  await expect(panel.getByRole("alert")).toContainText("Live voice is not configured");
  const positions = await page.evaluate(() => {
    const canvas = document.querySelector(".dz-voice-original-canvas");
    const globe = {bottom:canvas.getBoundingClientRect().top+
      Number(canvas.dataset.orbCenterY)+Number(canvas.dataset.orbRadius)};
    const alert = document.querySelector(".dz-voice-error-message").getBoundingClientRect();
    const controls = document.querySelector(".dz-voice-orb-controls").getBoundingClientRect();
    const back = document.querySelector("#companion-end").getBoundingClientRect();
    return {globeBottom:globe.bottom,alertTop:alert.top,alertBottom:alert.bottom,
      controlsTop:controls.top,controlsBottom:controls.bottom,backTop:back.top,
      backBottom:back.bottom,viewHeight:innerHeight};
  });
  // The uploaded preview places the headline near the orb rim; allow that
  // intentional composition while keeping the controls below the status.
  expect(positions.globeBottom - positions.alertTop).toBeLessThan(40);
  expect(positions.controlsTop - positions.alertBottom).toBeGreaterThan(8);
  expect(positions.backTop - positions.controlsBottom).toBeGreaterThanOrEqual(-2);
  expect(positions.backBottom).toBeLessThanOrEqual(positions.viewHeight);
  await panel.getByRole("button", { name:"Back to chat" }).click();
  await expect(panel).toBeHidden();
});

test("short phone viewport preserves a usable exit from voice error", async ({ page }) => {
  await page.setViewportSize({ width:360, height:600 });
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("dragonzpyder:voice-state", {
    detail:{kind:"error", message:"Live voice is not configured"}
  })));
  const exit = panel.getByRole("button", { name:"Back to chat" });
  await expect(exit).toBeInViewport();
  const globe = await panel.locator(".dz-voice-original-canvas").evaluate(canvas=>({
    bottom:canvas.getBoundingClientRect().top+
      Number(canvas.dataset.orbCenterY)+Number(canvas.dataset.orbRadius)
  }));
  const alert = await panel.locator(".dz-voice-error-message").boundingBox();
  expect(globe.bottom - alert.y).toBeLessThan(40);
  await exit.click();
});
