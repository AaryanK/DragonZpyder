import { test, expect } from "@playwright/test";

// Voice uses the existing companion transport. These browser tests inspect
// native React presentation only; they do not simulate provider success.
test.beforeEach(async ({ page }) => {
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

test("live voice uses React SVG, not the old imperative canvas or a copied HTML iframe", async ({ page }) => {
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await expect(panel).toBeVisible();
  await expect(panel.locator(".dz-voice-art-svg")).toBeVisible();
  // Real product logo, not a generated placeholder or decorative CSS circle.
  await expect(panel.locator("img.dz-voice-brandmark")).toHaveAttribute("src", "/brand-icon.png");
  await expect(panel.locator(".dz-voice-orb-shell canvas")).toHaveCount(0);
  await expect(panel.locator("iframe")).toHaveCount(0);
  await expect(panel.locator(".dz-voice-fluid-ribbons path")).toHaveCount(24);
  await expect(panel.locator(".dz-voice-stars circle")).toHaveCount(90);
  await expect(panel.getByText("Your intelligence, in conversation.")).toBeVisible();
  await expect(panel.getByRole("button", { name:"End conversation" })).toBeVisible();
  await expect(page.locator("#message-input")).toBeAttached();
  await expect(panel.locator("#companion-audio")).toHaveCount(1);
  await expect(page.locator("#companion-audio")).toHaveCount(1);
  await panel.getByRole("button", { name:"End conversation" }).click();
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

test("native SVG voice view fits phone without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width:390, height:844 });
  await page.locator("#companion-open").click();
  const panel = page.getByRole("dialog", { name:"Live companion" });
  await expect(panel.locator(".dz-voice-art-svg")).toBeVisible();
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
