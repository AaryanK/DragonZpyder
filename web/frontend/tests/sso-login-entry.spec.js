import { test, expect } from "@playwright/test";

test("React account and personal modal include fail-closed OIDC entry", async ({ page }) => {
  await page.goto("/account");
  const account = page.locator("#dragonzpyder-central-signin");
  await expect(account).toHaveAttribute("href", "/api/auth/dragonzpyder/web/start");
  // No SSO feature flag in the standalone preview: never fake readiness.
  await expect(account).toBeHidden();
  await page.goto("/app");
  const personal = page.locator("#dragonzpyder-central-signin-modal");
  await expect(personal).toHaveAttribute("href", "/api/auth/dragonzpyder/web/start");
  await expect(personal).toBeHidden();
});
