import { test, expect } from "@playwright/test";
import path from "node:path";
const fixture = (name: string) =>
  path.resolve(process.cwd(), "../api/tests/fixtures", name);

test("seven dashboard views and dedicated data management pages remain usable", async ({
  page,
}) => {
  await page.goto("/");
  for (const name of [
    "Overview",
    "Meta Ads Search",
    "TikTok Ads Search",
    "Product Intelligence",
    "Competitor Tracker",
    "Saved Ads",
    "Settings",
  ]) {
    await page
      .getByRole("button", {
        name: name === "Saved Ads" ? /^Saved Ads/ : name,
        exact: name !== "Saved Ads",
      })
      .click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      name === "Overview" ? "Discover what’s gaining traction." : name,
    );
    await expect(
      page.locator('[role="alert"]:not(#__next-route-announcer__)'),
    ).toHaveCount(0);
  }
  await expect(
    page.getByRole("heading", { name: "Data workspace" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Meta Ads Library", exact: true }),
  ).toBeVisible();
  for (const route of ["/data-sources", "/import-history", "/imports"]) {
    await page.goto(route);
    await expect(
      page.getByRole("heading", { name: "Data workspace" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "← DROPSpy Radar dashboard" }),
    ).toBeVisible();
  }
});

test("DEMO JSON preview, batch import, search, raw evidence and partition isolation", async ({
  page,
}) => {
  const dataset = `e2e-json-${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Import Data", exact: true }).click();
  await page.getByLabel("Import data label").selectOption("DEMO");
  await page.getByLabel("Dataset identity").fill(dataset);
  await page
    .getByLabel("Advertising data file")
    .setInputFiles(fixture("complete.json"));
  await page.getByRole("button", { name: "Preview file", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Preview: 2 valid/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Import valid rows", exact: true })
    .click();
  const row = page.getByRole("row").filter({ hasText: dataset });
  await expect(row).toContainText("completed", { timeout: 20000 });
  await row
    .getByRole("button", { name: "Search imported ads", exact: true })
    .click();
  await page
    .getByLabel("Search ads", { exact: true })
    .fill("Solar garden lights");
  await page
    .getByRole("button", { name: "Inspect Solar garden lights", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Raw evidence & provenance",
  );
  await page.locator(".raw-evidence summary").first().click();
  await expect(page.getByRole("dialog")).toContainText("fixture-light-1");
  await expect(page.getByRole("dialog")).toContainText("Source: demo");
  await page.getByRole("button", { name: "Close details" }).click();
  await page.getByLabel("Country", { exact: true }).selectOption("EU");
  await expect(
    page.getByRole("button", {
      name: "Inspect Solar garden lights",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.getByLabel("Search data partition").selectOption("real");
  await page.getByLabel("Country", { exact: true }).selectOption("");
  await page
    .getByLabel("Search ads", { exact: true })
    .fill("Fixture Garden Co");
  await expect(
    page.getByRole("heading", { name: "No ads found" }),
  ).toBeVisible();
});

test("CSV flexible mapping is revalidated before ingest", async ({ page }) => {
  const dataset = `e2e-csv-${Date.now()}`;
  await page.goto("/imports");
  await page.getByLabel("Import data label").selectOption("DEMO");
  await page.getByLabel("Dataset identity").fill(dataset);
  await page
    .getByLabel("Advertising data file")
    .setInputFiles(fixture("mapped.csv"));
  await page.getByRole("button", { name: "Preview file", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Preview: 0 valid/ }),
  ).toBeVisible();
  const mapping = {
    external_id: "Ad ID",
    platform: "Channel",
    advertiser: "Brand",
    title: "Product",
    country: "Market",
    status: "State",
    observed_at: "Seen",
    creative_text: "Copy",
  };
  for (const [field, column] of Object.entries(mapping))
    await page.getByLabel(`Map ${field}`, { exact: true }).selectOption(column);
  await expect(
    page.getByRole("button", { name: "Import valid rows", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Revalidate mapping", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /Preview: 1 valid/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Import valid rows", exact: true })
    .click();
  await expect(
    page.getByRole("row").filter({ hasText: dataset }).first(),
  ).toContainText("completed", { timeout: 20000 });
});

test("fixture upload cannot be relabeled REAL despite user attestation", async ({
  page,
}) => {
  await page.goto("/imports");
  await page
    .getByLabel("Advertising data file")
    .setInputFiles(fixture("complete.json"));
  await page
    .getByLabel("Rights reference", { exact: true })
    .fill("E2E synthetic fixture rejection only");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Preview file", exact: true }).click();
  await expect(
    page.locator('[role="alert"]:not(#__next-route-announcer__)'),
  ).toContainText("Test/demo fixtures may only be imported as DEMO");
  await expect(
    page.getByRole("button", { name: "Import valid rows", exact: true }),
  ).toHaveCount(0);
});
