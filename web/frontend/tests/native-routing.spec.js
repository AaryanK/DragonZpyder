import { test, expect } from "@playwright/test";

test("native Agent mode never calls the Operly proxy and scopes MCP aliases", async ({ page }) => {
  const oldRoutes = [];
  const chats = [];
  const alias = "c" + "1".repeat(30);

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
