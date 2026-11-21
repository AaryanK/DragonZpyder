import { test, expect } from "@playwright/test";

const reply = "This answer contains a short explanation and a useful conclusion.";
async function fixture(page) {
  const turns = Array.from({length:22}, (_,i) => [
    {role:"user",content:`Question ${i+1}: Can you describe the current design approach?`},
    {role:"assistant",content:`### Approach ${i+1}\n\n${reply} \n\nThe response stays readable and focused on evidence.`},
  ]).flat();
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    let result = {};
    if (path === "/api/auth/sessions") result = [{ id:"session-1", current:true, scope:"personal", device:"Browser" }];
    else if (path === "/api/personal-agent/conversations") result = [{id:"fixture-1",title:"Editorial design audit"}];
    else if (path === "/api/personal-agent/conversations/fixture-1/messages") result = turns;
    else if (path === "/api/personal-agent/chat" && method === "POST") result = {
      conversation_id:"fixture-1",message:"An answer from the real Personal chat response shape.",
      dispatch:"dragonzpyder_personal_mcp",run_id:"run-123",
      execution_receipts:{tool_names:["operly_tool_a"],failed_tool_count:0},
    };
    else if (path.endsWith("/approvals")) result = [];
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(result)});
  });
  await page.route("**/mesh/**", async route => route.fulfill({
    status:200,contentType:"application/json",
    body:JSON.stringify({models:[],imageEnabled:false,videoEnabled:false}),
  }));
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
  await expect(page.locator(".message.assistant").first()).toBeVisible();
}

test("editorial chat keeps assistant document layout and distinct user turns", async ({page}) => {
  await fixture(page);
  const user = page.locator(".message.user").first();
  const assistant = page.locator(".message.assistant").first();
  await expect(user).toBeVisible();
  await expect(assistant.getByRole("button",{name:"Copy assistant response"})).toBeAttached();
  const presentation = await page.evaluate(() => {
    const u = document.querySelector(".message.user");
    const assistant = document.querySelector(".message.assistant");
    return {
      userWidth:u.querySelector(".message-body").getBoundingClientRect().width,
      fullWidth:document.querySelector(".messages").getBoundingClientRect().width,
      fontSize:parseFloat(getComputedStyle(assistant.querySelector(".message-content")).fontSize),
      userAvatarVisible:getComputedStyle(u.querySelector(".message-avatar")).display,
    };
  });
  expect(presentation.userWidth).toBeLessThan(presentation.fullWidth);
  expect(presentation.fontSize).toBeGreaterThanOrEqual(15);
  expect(presentation.userAvatarVisible).toBe("none");
});

test("reading old messages does not auto-jump, jump control restores latest", async ({page}) => {
  await fixture(page);
  const main = page.locator("#chat-main");
  await main.evaluate(element => { element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  const jump = page.getByRole("button",{name:"Jump to latest message"});
  await expect(jump).toBeVisible();
  const before = await main.evaluate(e=>e.scrollTop);
  expect(before).toBe(0);
  await jump.click();
  await expect(jump).toBeHidden();
  const after = await main.evaluate(e=>e.scrollTop);
  expect(after).toBeGreaterThan(before);
});

test("only backend-supplied execution receipts become execution details", async ({page}) => {
  await fixture(page);
  await page.locator("#message-input").fill("Run the task");
  await page.locator("#send-button").click();
  const evidence = page.locator(".dz-execution-evidence").last();
  await expect(evidence).toBeVisible();
  await evidence.locator("summary").click();
  await expect(evidence.getByText("operly_tool_a")).toBeVisible();
  await expect(evidence.getByText(/not been independently verified/)).toBeVisible();
});

test("compact mobile conversation doesn't cause horizontal overflow", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await fixture(page);
  const size = await page.evaluate(() => ({width:document.documentElement.scrollWidth, viewport:innerWidth}));
  expect(size.width).toBeLessThanOrEqual(size.viewport+1);
  await expect(page.locator("#message-input")).toBeVisible();
});
