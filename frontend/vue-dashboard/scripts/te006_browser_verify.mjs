import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendRoot, "..", "..");
const artifactDir = path.join(repoRoot, "tests", "artifacts", "te006-browser");
const frontendUrl = "http://127.0.0.1:5173";

const browserCandidates = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
];

async function findBrowser() {
  for (const candidate of browserCandidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // try next
    }
  }
  throw new Error("No supported browser binary found.");
}

async function main() {
  await fs.mkdir(artifactDir, { recursive: true });
  const executablePath = await findBrowser();
  const browser = await chromium.launch({
    executablePath,
    headless: true,
  });

  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
    const consoleMessages = [];
    const pageErrors = [];
    page.on("console", (message) => {
      consoleMessages.push({ type: message.type(), text: message.text() });
    });
    page.on("pageerror", (error) => {
      pageErrors.push(String(error));
    });
    await page.goto(frontendUrl, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    const summary = {
      url: page.url(),
      title: await page.title(),
      heading: await page.locator("h1").first().innerText().catch(() => null),
      helperTexts: await page.locator("p").allInnerTexts(),
      buttonTexts: await page.locator("button").allInnerTexts(),
      bodyText: await page.locator("body").innerText().catch(() => null),
      consoleMessages,
      pageErrors,
    };
    summary.hasRegistrationEntry = summary.buttonTexts.some((text) => text.includes("注册"));

    await page.screenshot({
      path: path.join(artifactDir, "te006-login-page-1600x900.png"),
      fullPage: false,
    });

    const registerButton = page.getByRole("button", { name: /注册/ }).first();
    if (await registerButton.count()) {
      await registerButton.click();
      await page.waitForTimeout(800);
      summary.afterRegisterClick = {
        bodyText: await page.locator("body").innerText().catch(() => null),
        buttonTexts: await page.locator("button").allInnerTexts(),
        inputCount: await page.locator("input").count(),
        selectCount: await page.locator("select").count(),
      };
      await page.screenshot({
        path: path.join(artifactDir, "te006-registration-panel-1600x900.png"),
        fullPage: false,
      });
    }

    await page.goto(frontendUrl, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);

    const ts = Date.now().toString().slice(-6);
    const roleConfigs = [
      {
        key: "elder",
        account: {
          name: `Browser Elder ${ts}`,
          phone: `138${ts}01`.slice(0, 11),
          password: "123456",
        },
        profile: {
          apartment: `A-${ts.slice(-3)}`,
          age: "78",
          bindPlan: "now",
        },
        expectedLogin: () => `138${ts}01`.slice(0, 11),
      },
      {
        key: "family",
        account: {
          name: `Browser Family ${ts}`,
          phone: `139${ts}02`.slice(0, 11),
          loginUsername: `browser_family_${ts}`,
          password: "123456",
        },
        profile: {
          relationship: "daughter",
          landingChoice: "report",
          bindPlan: "later",
        },
        expectedLogin: () => `browser_family_${ts}`,
      },
      {
        key: "community",
        account: {
          name: `Browser Community ${ts}`,
          phone: `137${ts}03`.slice(0, 11),
          loginUsername: `browser_community_${ts}`,
          password: "123456",
        },
        profile: {
          shift: "day",
          stationLabel: `值守台-${ts}`,
          landingChoice: "overview",
        },
        expectedLogin: () => `browser_community_${ts}`,
      },
    ];

    summary.roleResults = [];

    for (const role of roleConfigs) {
      await page.getByRole("button", { name: /注册/ }).first().click();
      await page.getByTestId(`registration-role-${role.key}`).click();
      await page.getByTestId("registration-open-account-step").click();

      await page.getByTestId("registration-name").fill(role.account.name);
      await page.getByTestId("registration-phone").fill(role.account.phone);
      if (role.account.loginUsername) {
        await page.getByTestId("registration-login-username").fill(role.account.loginUsername);
      }
      await page.getByTestId("registration-password").fill(role.account.password);
      await page.getByTestId("registration-confirm-password").fill(role.account.password);
      await page.getByTestId("registration-next-profile").click();

      if (role.key === "elder") {
        await page.getByTestId("registration-apartment").fill(role.profile.apartment);
        await page.getByTestId("registration-age").fill(role.profile.age);
        await page.getByTestId(role.profile.bindPlan === "now" ? "registration-bind-now" : "registration-bind-later").click();
      } else if (role.key === "family") {
        await page.getByTestId("registration-relationship").selectOption(role.profile.relationship);
        await page.getByTestId("registration-landing-choice").selectOption(role.profile.landingChoice);
        await page.getByTestId(role.profile.bindPlan === "now" ? "registration-bind-now" : "registration-bind-later").click();
      } else {
        await page.getByTestId("registration-shift").selectOption(role.profile.shift);
        await page.getByTestId("registration-station-label").fill(role.profile.stationLabel);
        await page.getByTestId("registration-community-landing-choice").selectOption(role.profile.landingChoice);
      }

      await page.screenshot({
        path: path.join(artifactDir, `te006-${role.key}-profile-1600x900.png`),
        fullPage: false,
      });

      await page.getByTestId("registration-submit").click();
      await page.getByTestId("registration-complete").waitFor({ state: "visible", timeout: 15000 });

      const completionSnapshot = {
        title: await page.locator("[data-testid='registration-complete'] h3").innerText().catch(() => null),
        summary: await page.locator("[data-testid='registration-complete']").innerText().catch(() => null),
      };

      await page.screenshot({
        path: path.join(artifactDir, `te006-${role.key}-complete-1600x900.png`),
        fullPage: false,
      });

      await page.getByTestId("registration-prefill-login").click();
      await page.waitForTimeout(800);

      const loginInputs = page.locator(".login-input");
      const username = await loginInputs.nth(0).inputValue();
      const password = await loginInputs.nth(1).inputValue();

      summary.roleResults.push({
        role: role.key,
        expectedLogin: role.expectedLogin(),
        actualLogin: username,
        actualPassword: password,
        completionSnapshot,
      });
    }

    await fs.writeFile(
      path.join(artifactDir, "te006-browser-report.json"),
      JSON.stringify(summary, null, 2),
      "utf-8",
    );

    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
