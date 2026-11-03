import AxeBuilder from "@axe-core/playwright";
import { type Page, type Route, expect, test } from "@playwright/test";
import detail from "./fixtures/lot.json" with { type: "json" };
import lots from "./fixtures/lots.json" with { type: "json" };
import monitoring from "./fixtures/monitoring.json" with { type: "json" };
import plan from "./fixtures/plan.json" with { type: "json" };
import results from "./fixtures/results.json" with { type: "json" };
import shortlist from "./fixtures/shortlist.json" with { type: "json" };

type Handler = (route: Route) => Promise<void>;

async function mockApi(page: Page, overrides: Record<string, Handler> = {}) {
  const posts: { path: string; body: unknown }[] = [];
  await page.route("**/v1/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    // a key starting with "=" matches the path exactly, any other key is a prefix
    for (const [key, h] of Object.entries(overrides))
      if (key.startsWith("=") ? p === key.slice(1) : p.startsWith(key)) return h(route);
    if (route.request().method() === "POST") {
      posts.push({ path: p, body: route.request().postDataJSON() });
      if (p === "/v1/agent/plan") return route.fulfill({ json: plan });
      return route.fulfill({
        json: { invited: (route.request().postDataJSON() as { firm_ids: number[] }).firm_ids.length },
      });
    }
    if (p === "/v1/lots") return route.fulfill({ json: lots });
    if (p.endsWith("/shortlist")) return route.fulfill({ json: shortlist });
    if (p.startsWith("/v1/lots/")) return route.fulfill({ json: detail });
    if (p === "/v1/experiments") return route.fulfill({ json: results });
    if (p === "/v1/monitoring") return route.fulfill({ json: monitoring });
    return route.fulfill({ status: 404, json: { detail: "No such endpoint" } });
  });
  return posts;
}

async function accessible(page: Page) {
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== "running"));
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
}

test("the first open lot opens with its trade, the tape and the shortlist", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: detail.title })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Comparable bids to expect" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Shortlist" }).getByRole("listitem")).toHaveCount(
    shortlist.firms.length,
  );
  await accessible(page);
});

test("selecting firms moves the expected comparable bids", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/#/lots/${detail.lot_id}`);
  const out = page.locator("output.tape-number");
  await expect(page.getByRole("button", { name: "Invite 10 firms" })).toBeVisible(); // the default selection is in
  const before = Number(await out.textContent());
  await page.getByRole("checkbox").first().uncheck();
  await expect(out).not.toHaveText(before.toFixed(1));
  expect(Number(await out.textContent())).toBeLessThan(before);
});

test("inviting sends the selected firms and confirms", async ({ page }) => {
  const posts = await mockApi(page);
  await page.goto(`/#/lots/${detail.lot_id}`);
  await page.getByRole("button", { name: /^Invite \d+ firms$/ }).click();
  await expect(page.getByText(/^Invited \d+ firms/)).toBeVisible();
  expect(posts[0].path).toBe(`/v1/lots/${detail.lot_id}/invitations`);
  expect((posts[0].body as { firm_ids: number[] }).firm_ids.length).toBe(10);
});

test("a lot without fitting firms says what to do", async ({ page }) => {
  await mockApi(page, {
    "/v1/lots/": async (route) =>
      route.request().url().endsWith("/shortlist")
        ? route.fulfill({ json: { ...shortlist, firms: [], candidates: 0 } })
        : route.fulfill({ json: detail }),
  });
  await page.goto(`/#/lots/${detail.lot_id}`);
  await expect(page.getByRole("heading", { name: "No firm fits this lot" })).toBeVisible();
});

test("a failed shortlist explains itself and retries", async ({ page }) => {
  let calls = 0;
  await mockApi(page, {
    "/v1/lots/": async (route) => {
      if (!route.request().url().endsWith("/shortlist")) return route.fulfill({ json: detail });
      calls += 1;
      if (calls <= 2) return route.fulfill({ status: 503, json: { detail: "ranker restarting" } });
      return route.fulfill({ json: shortlist });
    },
  });
  await page.goto(`/#/lots/${detail.lot_id}`);
  await expect(page.getByRole("alert")).toContainText("ranker restarting");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("list", { name: "Shortlist" })).toBeVisible();
});

test("lots show a skeleton while loading and an empty state for a search without results", async ({
  page,
}) => {
  await mockApi(page, {
    "=/v1/lots": async (route) => {
      const u = new URL(route.request().url());
      if (u.searchParams.get("q")) return route.fulfill({ json: [] });
      await new Promise((r) => setTimeout(r, 700));
      return route.fulfill({ json: lots });
    },
  });
  await page.goto("/");
  await expect(page.getByLabel("Loading lots")).toBeVisible();
  await expect(page.getByRole("heading", { name: detail.title })).toBeVisible();
  await page.getByLabel("Search lots").fill("zzz");
  await expect(page.getByRole("heading", { name: "No lot matches" })).toBeVisible();
});

test("the evaluation shows estimates against the truth", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#/evaluation");
  await expect(page.getByRole("heading", { name: "Offline estimates against the truth" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Shipping/ })).toBeVisible();
  await accessible(page);
});

test("monitoring shows the checks and the alerts", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#/monitoring");
  await expect(page.getByRole("heading", { name: "Monitoring" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();
  await accessible(page);
});

test("the planner turns a request into invitations", async ({ page }) => {
  const posts = await mockApi(page);
  await page.goto("/#/planner");
  await expect(page.getByRole("heading", { name: "No plan yet" })).toBeVisible();
  await page.getByRole("button", { name: "Plan invitations" }).click();
  await expect(page.getByRole("heading", { name: plan.lots[0].title })).toBeVisible();
  expect(posts[0].path).toBe("/v1/agent/plan");
  await accessible(page);
});

test("works on a phone without sideways scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  for (const hash of [`#/lots/${detail.lot_id}`, "#/evaluation", "#/monitoring", "#/planner"]) {
    await page.goto(`/${hash}`);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, hash).toBeLessThanOrEqual(0);
  }
});
