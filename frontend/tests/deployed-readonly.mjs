import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { firefox } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const base = process.argv[2];
assert(base?.startsWith("https://"));
const browser = await firefox.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE }
    : {}),
  ...(process.env.FITNESS_TEST_PROXY
    ? { proxy: { server: process.env.FITNESS_TEST_PROXY } }
    : {}),
});
try {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.getByLabel("访问密码", { exact: true }).fill("12345678");
  await page.getByRole("button", { name: "进入手记 →" }).click();
  await page
    .getByRole("heading", { name: "把训练，放进这一周。" })
    .waitFor({ timeout: 60000 });
  let templates = await (
    await context.request.get(base + "/api/templates", { timeout: 60000 })
  ).json();
  const previous = JSON.parse(
    await readFile(resolve(root, "data/deploy/live-result.json"), "utf8"),
  );
  const temporary = templates.find(
    (t) => t.id === previous.templateId && t.name === previous.marker,
  );
  if (temporary) {
    const removed = await context.request.delete(
      base + "/api/templates/" + temporary.id,
      { headers: { Origin: base }, timeout: 60000 },
    );
    assert([200, 404].includes(removed.status()));
    templates = await (
      await context.request.get(base + "/api/templates", { timeout: 60000 })
    ).json();
  }
  assert(
    !templates.some((t) => t.name.startsWith("部署验证-")),
    "Temporary test template remains",
  );
  assert(
    (await context.cookies()).some(
      (c) => c.name === "fitness_session" && c.secure && c.httpOnly,
    ),
  );
  const out = resolve(root, "data/deploy");
  await mkdir(out, { recursive: true });
  for (const [name, width, height] of [
    ["mobile", 390, 844],
    ["ipad", 1024, 1366],
  ]) {
    await page.setViewportSize({ width, height });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.screenshot({
      path: resolve(out, "live-" + name + ".png"),
      fullPage: true,
      animations: "disabled",
    });
  }
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("heading", { name: "打开我的训练手记" }).waitFor();
  assert.deepEqual(errors, []);
  await writeFile(
    resolve(out, "readonly-result.json"),
    JSON.stringify({
      passed: true,
      templateCount: templates.length,
      https: base,
      mobile: true,
      ipad: true,
    }),
  );
  console.log(
    "PASS: deployed HTTPS login, secure cookie, restored user data, mobile/iPad layouts, logout.",
  );
} finally {
  await browser.close();
}
