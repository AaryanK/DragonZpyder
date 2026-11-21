import { test, expect } from "@playwright/test";

function json(body, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(body) };
}
async function prepare(page, responder) {
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname, method = route.request().method();
    if (path === "/api/auth/sessions") return route.fulfill(json([{ id:"fixture", current:true, scope:"personal", device:"browser" }]));
    if (path === "/api/auth/bootstrap") return route.fulfill(json({ csrf_token:"test-token" }));
    const custom = await responder?.(path, method, route);
    if (custom === true) return;
    if (path === "/api/personal-agent/conversations" || path === "/api/personal-agent/approvals") return route.fulfill(json([]));
    return route.fulfill(json({}));
  });
  await page.route("**/mesh/**", async route => route.fulfill(json({models:[],imageEnabled:false,videoEnabled:false})));
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
  await page.getByRole("button", { name: /Connections & tools/ }).click();
  await expect(page.getByRole("dialog", { name: "Your DragonZpyder" })).toBeVisible();
}

test("connection management uses actual Personal connector response and tested endpoint", async ({page}) => {
  let tested = false;
  await prepare(page, async (path, method, route) => {
    if (path === "/api/personal-connectors" && method === "GET") {
      await route.fulfill(json([{ id:"google-1", provider:"google", displayName:"Google", enabled:true, status:"active", account:"person@example.com", healthStatus:"healthy", capabilities:["google.gmail.search"] }]));
      return true;
    }
    if (path === "/api/personal-connectors/google-1/test" && method === "POST") {
      tested = true;
      await route.fulfill(json({ ok:true }));
      return true;
    }
    return false;
  });
  const center = page.getByRole("dialog",{name:"Your DragonZpyder"});
  await expect(center.getByText("person@example.com")).toBeVisible();
  await expect(center.getByText("healthy")).toBeVisible();
  await center.getByRole("button",{name:"Test"}).click();
  await expect.poll(() => tested).toBe(true);
  await expect(center.getByRole("status")).toContainText("Test Google completed");
});

test("Personal approval shows arguments and posts a deliberate allow-once decision", async ({page}) => {
  let payload = null;
  await prepare(page, async (path, method, route) => {
    if (path === "/api/personal-tools/approvals" && method === "GET") {
      await route.fulfill(json({ approvals:[{id:"approval-7", status:"pending", capability_id:"google.gmail.send", arguments:{to:"test@example.com",subject:"Draft"}}] }));
      return true;
    }
    if (path === "/api/personal-tools/approvals/approval-7/decision" && method === "POST") {
      payload = route.request().postDataJSON();
      await route.fulfill(json({id:"approval-7",status:"approved"}));
      return true;
    }
    return false;
  });
  const center = page.getByRole("dialog",{name:"Your DragonZpyder"});
  await center.getByRole("button",{name:"Approvals",exact:true}).click();
  await expect(center.getByText("google.gmail.send")).toBeVisible();
  await center.getByText("Arguments").click();
  await expect(center.getByText("test@example.com")).toBeVisible();
  page.once("dialog", confirmation => confirmation.accept());
  await center.getByRole("button",{name:"Allow once"}).click();
  await expect.poll(() => payload?.approved).toBe(true);
});

test("Tasks lists actual Personal workflow definitions and runs, then invokes authorized run", async ({page}) => {
  let started = null;
  await prepare(page, async (path, method, route) => {
    if (path === "/api/personal-tools" && method === "GET") {
      await route.fulfill(json({tools:[
        {id:"workflow.list"},{id:"workflow.run.list"},{id:"workflow.run.start"}
      ]})); return true;
    }
    if (path === "/api/personal-tools/workflow.list/execute") {
      await route.fulfill(json({done:true,status:"completed",result:{workflows:[{id:"wf-1",name:"Weekly review",status:"enabled",description:"Summarize upcoming work"}]}})); return true;
    }
    if (path === "/api/personal-tools/workflow.run.list/execute") {
      await route.fulfill(json({done:true,status:"completed",result:{runs:[{id:"run-1",workflow_id:"wf-1",status:"completed"}]}})); return true;
    }
    if (path === "/api/personal-tools/workflow.run.start/execute" && method === "POST") {
      started = route.request().postDataJSON();
      await route.fulfill(json({done:true,status:"completed",result:{}})); return true;
    }
    return false;
  });
  const center = page.getByRole("dialog",{name:"Your DragonZpyder"});
  await center.getByRole("button",{name:"Tasks",exact:true}).click();
  await expect(center.getByText("Weekly review").first()).toBeVisible();
  await expect(center.getByText("Recent execution")).toBeVisible();
  page.once("dialog", confirmation => confirmation.accept());
  await center.getByRole("button",{name:"Run now"}).click();
  await expect.poll(() => started?.arguments?.workflow_id).toBe("wf-1");
});

test("without available capability, Tasks doesn't pretend scheduled work is enabled", async ({page}) => {
  await prepare(page, async () => false);
  const center = page.getByRole("dialog",{name:"Your DragonZpyder"});
  await center.getByRole("button",{name:"Tasks",exact:true}).click();
  await expect(center.getByText("Personal workflows unavailable")).toBeVisible();
  await expect(center.getByRole("button",{name:"Run now"})).toHaveCount(0);
});

test("workspace creation is explicit and uses the existing authenticated endpoint", async ({page}) => {
  let created = null;
  await prepare(page, async (path, method, route) => {
    if (path === "/api/auth/workspaces" && method === "GET") {
      await route.fulfill(json(created ? [{id:"ws-1",name:created.name,role:"owner"}] : [])); return true;
    }
    if (path === "/api/auth/workspaces" && method === "POST") {
      created = route.request().postDataJSON();
      await route.fulfill(json({ok:true,workspace:{id:"ws-1",name:created.name,role:"owner"}})); return true;
    }
    return false;
  });
  const center = page.getByRole("dialog",{name:"Your DragonZpyder"});
  await center.getByRole("button",{name:"Workspaces",exact:true}).click();
  await expect(center.getByText("No business workspaces")).toBeVisible();
  await center.getByRole("textbox",{name:"Create a workspace"}).fill("Demo organization");
  page.once("dialog", confirmation => confirmation.accept());
  await center.getByRole("button",{name:"Create",exact:true}).click();
  await expect.poll(() => created?.name).toBe("Demo organization");
  await expect(center.getByText("Demo organization")).toBeVisible();
});
