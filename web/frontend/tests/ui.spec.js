import { test, expect } from "@playwright/test";

async function mockPersonalApi(page) {
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
  await expect(drawer.getByRole("button",{name:/Jobs & automations/})).toBeDisabled();
  await expect(drawer.getByRole("button",{name:/Conversations/})).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
});

test("all presentation stylesheets are served, not intercepted by the API proxy", async ({page}) => {
  for (const file of ["app.css","mesh.css","workspace.css","ui-v1.css"]) {
    const result = await page.evaluate(async path => {
      const response = await fetch("/"+path, {cache:"no-store"});
      return {status:response.status, contentType:response.headers.get("content-type") || ""};
    }, file);
    expect(result.status, file+" status").toBe(200);
    expect(result.contentType, file+" content type").toMatch(/text\\/css/);
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
