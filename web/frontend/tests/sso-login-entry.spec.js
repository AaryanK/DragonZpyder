import { test, expect } from "@playwright/test";

test("account and personal modal offer the dedicated native login", async ({ page }) => {
  await page.route("**/dz/status", route=>route.fulfill({json:{web_cutover_enabled:false}}));
  await page.route("**/api/auth/**", route=>route.fulfill({status:401}));
  await page.goto("/account");
  const account = page.locator("#dragonzpyder-central-signin");
  await expect(account).toHaveAttribute("href", "/login");
  await expect(account).toBeVisible();
  await page.goto("/app");
  const personal = page.locator("#dragonzpyder-central-signin-modal");
  await expect(personal).toHaveAttribute("href", "/login");
  await expect(personal).toBeVisible();
});
