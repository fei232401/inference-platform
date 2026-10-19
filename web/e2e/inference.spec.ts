import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("browser generates through router and persists decision", async ({ page }) => {
  const key = readFileSync(new URL("../../.state/admin-key", import.meta.url), "utf8").trim();
  await page.addInitScript((value) => sessionStorage.setItem("ai-infra.api-key", value), key);
  await page.goto("/inference");
  await page.locator("select").first().selectOption({ label: process.env.BROWSER_MODEL! });
  await page.locator("textarea").fill("只回复你好");
  await page.getByLabel(process.env.BROWSER_BACKEND!, { exact: false }).fill(process.env.BROWSER_ENGINE_MODEL!);
  const response = page.waitForResponse((value) => value.url().endsWith("/v1/route") && value.request().method() === "POST");
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  await expect(page.getByText("决策已写回 PostgreSQL", { exact: true })).toBeVisible();
  await expect(page.getByText("生成结果", { exact: true })).toBeVisible();
  await page.screenshot({ path: new URL("../../artifacts/inference-browser.png", import.meta.url).pathname, fullPage: true });
});
