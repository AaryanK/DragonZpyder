import { test, expect } from "@playwright/test";

async function mockPersonalApi(page) {
  // The native cutover probe must be explicit, not an HTML SPA fallback.
  await page.route("**/dz/status", async route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ web_cutover_enabled: false }) }));
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let response = {};
    if (path === "/api/auth/sessions") {
      response = [{ id:"fixture", current:true, scope:"personal", device:"UI test" }];
    } else if (path === "/api/personal-agent/conversations" ||
               path.endsWith("/approvals")) {
      response = [];
    }
    await route.fulfill({ status:200, contentType:"application/json", body:JSON.stringify(response) });
  });
  await page.route("**/mesh/**", async route => {
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({models:[],imageEnabled:false,videoEnabled:false})});
  });
}

test.beforeEach(async ({ page }) => {
  await mockPersonalApi(page);
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator("#auth-modal")).toBeHidden();
});

test("keyboard command palette is searchable, readable, and closes with Escape", async ({page}) => {
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog",{name:"What would you like to do?"});
  await expect(dialog).toBeVisible();
  const search = dialog.getByRole("textbox",{name:"Search DragonZpyder commands"});
  await expect(search).toBeFocused();
  await search.fill("camera");
  await expect(dialog.getByRole("button",{name:/Capture a photo/})).toBeVisible();
  await expect(dialog.getByRole("button",{name:/Start live voice/})).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("attaching a file requires explicit context change approval", async ({page}) => {
  await page.waitForFunction(() => Boolean(window.dragonzpyderMesh));
  const mode = page.locator("#mesh-switch");
  await expect(mode).toHaveAttribute("aria-pressed","false");
  await page.locator("#dz-add-toggle").click();
  await expect(page.locator("#dz-add-menu")).toBeVisible();
  await page.locator("#mesh-upload").setInputFiles({
    name:"notes.txt", mimeType:"text/plain", buffer:Buffer.from("For testing only")
  });
  const dialog = page.getByRole("alertdialog",{name:"Switch to AI Mesh?"});
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button",{name:"Keep Agent chat"}).click();
  await expect(dialog).toHaveCount(0);
  await expect(mode).toHaveAttribute("aria-pressed","false");
});

test("desktop sidebar collapses and expands without removing chat", async ({page}) => {
  await page.setViewportSize({width:1365,height:850});
  await page.getByRole("button",{name:"Collapse sidebar"}).click();
  await expect(page.locator("#sidebar")).toBeHidden();
  await expect(page.locator("#message-input")).toBeVisible();
  await page.getByRole("button",{name:"Expand sidebar"}).click();
  await expect(page.locator("#sidebar")).toBeVisible();
});

test("workspace navigation discloses planned items rather than promising working tools", async ({page}) => {
  await page.locator("#dz-workspace-trigger").click();
  const drawer = page.getByRole("dialog",{name:"Everything, in one place."});
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button",{name:/Jobs & automations/})).toBeEnabled();
  await expect(drawer.getByRole("button",{name:/Conversations/})).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
});

test("workspace drawer traps focus and returns it on close", async ({page}) => {
  const trigger=page.locator("#dz-workspace-trigger");
  await trigger.click();
  const drawer=page.getByRole("dialog",{name:"Everything, in one place."});
  await expect(drawer).toBeVisible();
  const close=drawer.getByRole("button",{name:"Close workspace navigation"});
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(drawer.getByRole("button",{name:/Search all available commands/})).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("all presentation stylesheets are served, not intercepted by the API proxy", async ({page}) => {
  for (const file of ["app.css","mesh.css","workspace.css","ui-v1.css"]) {
    const result = await page.evaluate(async path => {
      const response = await fetch("/"+path, {cache:"no-store"});
      return {status:response.status, contentType:response.headers.get("content-type") || ""};
    }, file);
    expect(result.status, file+" status").toBe(200);
    expect(result.contentType, file+" content type").toContain("text/css");
  }
});

test("light shortcut keys have readable contrast and the command list scrolls", async ({page}) => {
  await page.keyboard.press("Control+k");
  const computed = await page.locator(".dz-command-foot kbd").first().evaluate(node => {
    const color = value => {
      const m=value.match(/\d+(?:\.\d+)?/g).slice(0,3).map(Number);
      return m.map(x => { x /= 255; return x <= .04045 ? x / 12.92 : ((x+.055)/1.055)**2.4; })
        .reduce((sum,x,i) => sum + x * [.2126,.7152,.0722][i],0);
    };
    const styles=getComputedStyle(node);
    const ancestor=getComputedStyle(node.parentElement);
    const fore=color(styles.color), back=color(styles.backgroundColor==="rgba(0, 0, 0, 0)" ? ancestor.backgroundColor : styles.backgroundColor);
    return { contrast:(Math.max(fore,back)+.05)/(Math.min(fore,back)+.05),
      parentScroll:node.closest(".dz-command-panel").querySelector(".dz-command-results").scrollHeight };
  });
  expect(computed.contrast).toBeGreaterThanOrEqual(4.5);
  const results = page.locator(".dz-command-results");
  const dims = await results.evaluate(node => ({height:node.clientHeight, scroll:node.scrollHeight}));
  expect(dims.height).toBeLessThanOrEqual(340);
  expect(dims.scroll).toBeGreaterThan(dims.height);
});

test("phone layout has no horizontal overflow and can reach starter actions", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator("#message-input")).toBeVisible();
  const metrics = await page.evaluate(() => ({
    scrollWidth:document.documentElement.scrollWidth,
    viewport:window.innerWidth
  }));
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewport+1);
  await page.locator(".prompt-chip").last().scrollIntoViewIfNeeded();
  await expect(page.locator(".prompt-chip").last()).toBeInViewport();
  await page.locator("#open-sidebar").click();
  await expect(page.locator("#sidebar")).toHaveClass(/open/);
});

test("dark-mode shortcuts remain readable", async ({page}) => {
  await page.locator("#workspace-theme-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-workspace-theme","dark");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog",{name:"What would you like to do?"})).toBeVisible();
  await expect(page.locator(".dz-command-foot kbd").first()).toBeVisible();
});


test("identical legacy and Kernel approval IDs render once with Kernel authority", async ({page}) => {
  const approval = {
    id: "571daf1e-fb54-484a-875a-4701992165cf",
    capability_id: "workspace.create",
    status: "pending",
    arguments: { name: "DragonZpyder MCP Experiment", timezone: "America/Chicago" },
    conversation_id: "test-conversation",
  };
  // Both existing projections may return the SAME underlying Kernel row.
  await page.route(url => {
    const path = new URL(url).pathname;
    return path === "/api/personal-tools/approvals" || path === "/api/kernel/personal/approvals";
  }, async route => {
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ approvals: [approval] }),
    });
  });
  await page.locator("#approvals-top").click();
  await expect(page.locator("#approvals-drawer")).toBeVisible();
  await expect(page.locator("#approval-list .approval-card")).toHaveCount(1);
  await expect(page.locator("#approval-count")).toHaveText("1");
  // Mocked login does not set a real CSRF cookie. Exercise the POST path
  // with a synthetic same-origin token; production still checks it server-side.
  await page.evaluate(() => { document.cookie = "operly_csrf=ui-fixture; path=/"; });
  // The preferred Kernel source must own the actionable button, not legacy.
  let decisionPath = "";
  await page.route("**/api/kernel/personal/approvals/*/decision", async route => {
    decisionPath = new URL(route.request().url()).pathname;
    await route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ ...approval, status: "rejected" }) });
  });
  await page.locator("#approval-list .reject-btn").click();
  await expect.poll(() => decisionPath).toBe("/api/kernel/personal/approvals/" + approval.id + "/decision");
});


test("iPhone Safari offers accessible Home Screen instructions without an install prompt", async ({page}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "userAgent", { configurable:true, get: () =>
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" });
    Object.defineProperty(navigator, "platform", { configurable:true, get: () => "iPhone" });
  });
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  const tip = page.locator(".empty-state .dz-ios-install");
  await expect(tip).toBeVisible();
  await tip.getByRole("button", {name:"How to add to Home Screen"}).click();
  await expect(tip).toContainText("Add to Home Screen");
  await expect(tip).toContainText("Share");
  await tip.getByRole("button", {name:"Dismiss installation tip"}).click();
  await expect(tip).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".empty-state .dz-ios-install")).toHaveCount(0);
});

test("standalone iOS installation does not show the install tutorial", async ({page}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "userAgent", {configurable:true, get: () =>
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"});
    Object.defineProperty(navigator, "standalone", {configurable:true, get: () => true});
  });
  await page.reload();
  await expect(page.locator(".empty-state .dz-ios-install")).toHaveCount(0);
});

test("small phones keep the chat composer visible and avoid horizontal scrolling", async ({page}) => {
  for (const width of [320, 360, 375, 390, 430]) {
    await page.setViewportSize({width,height:740});
    const metrics = await page.evaluate(() => ({
      overflow:document.documentElement.scrollWidth-window.innerWidth,
      composer:getComputedStyle(document.querySelector("#message-input")).fontSize,
      textarea:document.querySelector("#message-input").getBoundingClientRect().toJSON()
    }));
    expect(metrics.overflow, "document overflow at "+width+"px").toBeLessThanOrEqual(1);
    expect(parseFloat(metrics.composer), "iOS text size at "+width+"px").toBeGreaterThanOrEqual(16);
    expect(metrics.textarea.right, "composer right edge at "+width+"px").toBeLessThanOrEqual(width+1);
    expect(metrics.textarea.left, "composer left edge at "+width+"px").toBeGreaterThanOrEqual(0);
  }
});

test("public landing explains Safari install and fits phone/tablet widths", async ({page}) => {
  await page.goto("/");
  const section = page.locator("#install-ios");
  await expect(section).toContainText("Add to Home Screen");
  await expect(section.getByRole("link", {name:/Open DragonZpyder/})).toHaveAttribute("href","/app");
  for (const width of [320,360,375,390,430,768]) {
    await page.setViewportSize({width,height:812});
    const bounds = await page.evaluate(() => ({
      scrollWidth:document.documentElement.scrollWidth,
      viewport:window.innerWidth,
      offenders:[...document.querySelectorAll("body *")].map(el => ({
        tag:el.tagName.toLowerCase(), className:typeof el.className === "string" ? el.className.slice(0,90) : "",
        right:Math.round(el.getBoundingClientRect().right),
        left:Math.round(el.getBoundingClientRect().left)
      })).filter(el => el.right > window.innerWidth+2 || el.left < -2)
        .sort((a,b) => b.right-a.right).slice(0,16),
    }));
    expect(bounds.scrollWidth, width+"px: "+JSON.stringify(bounds.offenders)).toBeLessThanOrEqual(bounds.viewport+1);
  }
});
