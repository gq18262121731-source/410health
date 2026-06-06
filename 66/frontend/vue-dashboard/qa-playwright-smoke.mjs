import { chromium } from "playwright";

const frontendUrl = "http://127.0.0.1:9000/";
const checkedPages = [
  { hash: "#/overview", text: /社区|总览|风险|设备/ },
  { hash: "#/topology", text: /关系|拓扑|老人|家属/ },
  { hash: "#/members", text: /设备|成员|台账|老人/ },
  { hash: "#/agent", text: /智能|助手|分析|Agent/ },
  { hash: "#/target-users", text: /目标|人物|姿态|摄像/ },
];

function visibleText(page) {
  return page.locator("body").innerText({ timeout: 5000 });
}

async function assertNoViteError(page, label) {
  const bodyText = await visibleText(page);
  const errorPatterns = [
    "Failed to resolve import",
    "Internal server error",
    "[plugin:vite",
    "Cannot find module",
  ];
  for (const pattern of errorPatterns) {
    if (bodyText.includes(pattern)) {
      throw new Error(`${label}: found Vite/runtime error text: ${pattern}`);
    }
  }
}

async function login(page, username, password) {
  await page.goto(frontendUrl, { waitUntil: "networkidle" });
  await assertNoViteError(page, "login page");
  await page.getByTestId("login-username").fill(username);
  await page.getByTestId("login-password").fill(password);
  await Promise.all([
    page.waitForResponse((res) => res.url().includes("/api/v1/auth/login") && res.status() < 500),
    page.getByTestId("login-submit").click(),
  ]);
  await page.waitForLoadState("networkidle");
}

const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const issues = [];

page.on("pageerror", (error) => issues.push(`pageerror: ${error.message}`));
page.on("console", (message) => {
  if (message.type() === "error") {
    issues.push(`console.error: ${message.text()}`);
  }
});
page.on("requestfailed", (request) => {
  const url = request.url();
  const errorText = request.failure()?.errorText ?? "";
  if (errorText === "net::ERR_ABORTED") {
    return;
  }
  if (!url.includes("/camera/stream") && !url.includes("/snapshot")) {
    issues.push(`requestfailed: ${url} ${errorText}`);
  }
});

await page.goto(frontendUrl, { waitUntil: "networkidle" });
await assertNoViteError(page, "initial login");
if (!(await page.getByTestId("login-submit").isVisible())) {
  throw new Error("login form is not visible");
}

await page.getByTestId("open-registration").click();
await page.waitForTimeout(800);
await assertNoViteError(page, "registration flow");
const registrationText = await visibleText(page);
if (!/请选择您的角色|注册/.test(registrationText)) {
  throw new Error("registration flow did not open");
}

await page.goto(frontendUrl, { waitUntil: "networkidle" });
await page.evaluate(() => localStorage.clear());
await login(page, "community_admin", "123456");
await page.waitForURL(/#\/overview/, { timeout: 10000 });
await assertNoViteError(page, "community overview");

for (const item of checkedPages) {
  await page.goto(`${frontendUrl}${item.hash}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await assertNoViteError(page, item.hash);
  const text = await visibleText(page);
  if (!item.text.test(text)) {
    throw new Error(`${item.hash}: expected page text was not found`);
  }
}

await page.evaluate(() => localStorage.clear());
await login(page, "family01", "123456");
await page.waitForURL(/#\/family/, { timeout: 10000 });
await assertNoViteError(page, "family page");
const familyText = await visibleText(page);
if (!/家属|老人|健康|报告/.test(familyText)) {
  throw new Error("family page expected text was not found");
}

await browser.close();

if (issues.length) {
  throw new Error(`browser issues:\n${issues.join("\n")}`);
}

console.log("Playwright smoke passed");
