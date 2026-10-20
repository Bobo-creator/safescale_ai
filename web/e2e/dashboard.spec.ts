import { expect, type Page, test } from "@playwright/test";

const NIGHT_LIGHT = "Children's night light";
const DISCLAIMER = /does not certify that a product is safe or compliant/;

async function analyzeExample(page: Page, example = NIGHT_LIGHT) {
  await page.goto("/analyze");
  await page.getByRole("button", { name: example, exact: true }).click();
  await page.getByRole("button", { name: "Analyze hazards" }).click();
  await expect(page.getByText(/historical signal/)).toBeVisible();
}

test("night light: signal, profile, evidence, then a cited explanation @smoke", async ({ page }) => {
  await analyzeExample(page);
  await expect(page.getByText("High historical signal")).toBeVisible();
  await expect(page.getByRole("heading", { name: /recur in similar recalls/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Fire \/ overheating: \d+ of 25/ })).toBeVisible();
  await expect(page.locator('[id^="recall-"]')).toHaveCount(25);
  await expect(page.getByText("25 closest", { exact: true })).toBeVisible();

  await expect(page.getByRole("heading", { name: "Why these recalls match" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Show similar recall \d+$/ }).first()).toBeVisible();
  await expect(page.getByText(/Recall data only contains products that had problems/)).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Disclaimer" })).toContainText(DISCLAIMER);
});

test("a citation jumps to and focuses its evidence card @smoke", async ({ page }) => {
  await analyzeExample(page);
  const citation = page.getByRole("button", { name: /^Show similar recall \d+$/ }).last();
  await expect(citation).toBeVisible();
  const rank = (await citation.textContent())?.trim();
  await citation.click();
  const focused = page.locator('[id^="recall-"]:focus');
  await expect(focused).toBeInViewport();
  await expect(focused.locator("span").first()).toHaveText(rank ?? "");
});

test("selecting a hazard filters the evidence list", async ({ page }) => {
  await analyzeExample(page);
  const row = page.getByRole("button", { name: /Electrical shock: (\d+) of 25/ });
  const count = Number((await row.getAttribute("aria-label"))?.match(/: (\d+) of/)?.[1]);
  await row.click();
  await expect(row).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('[id^="recall-"]')).toHaveCount(count);
  await page.getByRole("button", { name: "Show all 25" }).click();
  await expect(page.locator('[id^="recall-"]')).toHaveCount(25);
});

test("depth and method can be changed", async ({ page }) => {
  await page.goto("/analyze");
  await page.getByRole("button", { name: "Baby crib", exact: true }).click();
  await page.getByText("50", { exact: true }).click();
  await page.getByText("Advanced").click();
  await page.getByLabel(/Keywords/).check();
  await page.getByRole("button", { name: "Analyze hazards" }).click();
  await expect(page.getByText("50 closest", { exact: true })).toBeVisible();
  await expect(page.locator('[id^="recall-"]')).toHaveCount(50);
});

test("an unrelated product gets the not-enough-evidence message", async ({ page }) => {
  await page.goto("/analyze");
  await page
    .getByRole("textbox")
    .fill("Cloud accounting software subscription for small businesses with invoicing dashboard");
  await page.getByRole("button", { name: "Analyze hazards" }).click();
  await expect(page.getByRole("heading", { name: "Not enough similar recalls to judge" })).toBeVisible();
  await expect(page.getByText("There isn't enough evidence to explain.")).toBeVisible();
  await expect(page.getByText("Weak match, not counted in the profile").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Areas to consider investigating" })).toHaveCount(0);
});

test("too-short descriptions can't be submitted", async ({ page }) => {
  await page.goto("/analyze");
  await page.getByRole("textbox").fill("lamp");
  await expect(page.getByRole("button", { name: "Analyze hazards" })).toBeDisabled();
  await expect(page.getByText("Add a few more words.")).toBeVisible();
});

test("keyboard only: type, submit with Ctrl+Enter, reach a citation", async ({ page }) => {
  await page.goto("/analyze");
  await page.keyboard.press("Tab"); // Skip to content
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab"); // the description box
  await expect(page.getByRole("textbox")).toBeFocused();
  await page.keyboard.type("Six-drawer wooden dresser for a child's bedroom, 48 inches tall.");
  await page.keyboard.press("Control+Enter");
  await expect(page.getByText("High historical signal")).toBeVisible();
  const citation = page.getByRole("button", { name: /^Show similar recall \d+$/ }).first();
  await expect(citation).toBeVisible();
  await citation.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator('[id^="recall-"]:focus')).toBeInViewport();
});

test("phone layout: no sideways scrolling, results stack @phone @smoke", async ({ page }) => {
  await analyzeExample(page);
  await expect(page.getByRole("heading", { name: "Similar recalls", exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await expect(page.getByRole("complementary", { name: "Disclaimer" })).toBeVisible();
});

test("landing page: explains the product and leads into the tool @smoke", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "See which hazards got products like yours recalled.",
  );
  await expect(page.getByText("A real result: the 25 closest of 10,039 U.S. recalls.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How it works" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What a signal tells you, and what it doesn't" })).toBeVisible();
  await expect(page.getByRole("contentinfo")).toContainText(DISCLAIMER);

  await page.getByRole("link", { name: "Try the night light example" }).click();
  await expect(page).toHaveURL(/\/analyze\?q=/);
  await expect(page.getByRole("textbox")).toHaveValue(/night light/);
  await expect(page.getByRole("textbox")).toBeFocused();
});

test("landing form sends the description to the tool", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Product description").fill("Folding electric bicycle with a 48 V lithium battery pack");
  await page.getByRole("button", { name: "Analyze a product" }).click();
  await expect(page).toHaveURL(/\/analyze\?q=Folding/);
  await expect(page.getByRole("textbox")).toHaveValue("Folding electric bicycle with a 48 V lithium battery pack");
});

test("the methodology page explains the signal", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("banner").getByRole("link", { name: "Methodology" }).click();
  await expect(page.getByRole("heading", { name: "What the signal means" })).toBeVisible();
  await expect(page.getByText(/not a probability/)).toBeVisible();
});
