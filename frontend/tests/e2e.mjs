import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:net";
import { firefox } from "playwright";

const root = fileURLToPath(new URL("../../", import.meta.url));
const temporary = await mkdtemp(join(tmpdir(), "fitness-browser-"));
const port = await new Promise((resolve) => {
  const server = createServer();
  server.listen(0, "127.0.0.1", () => {
    const port = server.address().port;
    server.close(() => resolve(port));
  });
});
const base = `http://127.0.0.1:${port}`;
const password = "12345678";
const env = {
  ...process.env,
  FITNESS_DATA_DIR: temporary,
  FITNESS_ORIGIN: base,
  FITNESS_SECURE_COOKIE: "false",
};
const python = process.env.FITNESS_PYTHON || "python";
const cwd = resolve(root, "backend");
const server = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "main:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
    "--no-proxy-headers",
  ],
  { cwd, env, stdio: ["ignore", "pipe", "pipe"] },
);
let logs = "";
server.stdout.on("data", (c) => (logs += c));
server.stderr.on("data", (c) => (logs += c));
let browser;
try {
  let ready = false;
  for (let i = 0; i < 80; i++) {
    try {
      const res = await fetch(base + "/api/session");
      if (res.status === 401) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  assert(ready, "Server startup: " + logs);
  browser = await firefox.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE }
      : {}),
  });
  const context = await browser.newContext({
    viewport: { width: 1024, height: 1366 },
  });
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await page.getByLabel("访问密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "进入手记 →" }).click();
  await page.getByRole("heading", { name: "把训练，放进这一周。" }).waitFor();
  await page.getByRole("button", { name: "我的模板", exact: true }).click();
  await page.getByRole("button", { name: "＋ 新建模板" }).click();
  await page.getByLabel("模板名称", { exact: true }).fill("上肢训练");
  await page
    .getByLabel("模板说明", { exact: true })
    .fill("按自己的节奏练习哑铃动作。");
  await page.getByRole("button", { name: "＋ 添加动作" }).click();
  await page.getByLabel("动作名称", { exact: true }).fill("哑铃划船");
  await page
    .getByLabel("动作步骤", { exact: true })
    .fill("这是用户填写的原始教学说明。");
  await page.getByLabel("呼吸节奏", { exact: true }).fill("这里填写呼吸提示。");
  await page.getByRole("button", { name: "保存模板", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "模板已保存" }).waitFor();

  // Generate a tiny real WebM locally. No media downloads or extra software.
  const videoBytes = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 180;
    const ctx = canvas.getContext("2d"),
      stream = canvas.captureStream(15);
    const recorder = new MediaRecorder(stream, { mimeType: "video/webm" }),
      chunks = [];
    return await new Promise((resolve) => {
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        resolve(
          Array.from(
            new Uint8Array(
              await new Blob(chunks, { type: "video/webm" }).arrayBuffer(),
            ),
          ),
        );
      };
      recorder.start();
      let frame = 0;
      const draw = setInterval(() => {
        ctx.fillStyle = "#245c73";
        ctx.fillRect(0, 0, 320, 180);
        ctx.fillStyle = "#fff";
        ctx.font = "20px sans-serif";
        ctx.fillText("Local video playback check", 25, 80);
        ctx.fillRect(25 + (frame++ % 20) * 10, 110, 20, 10);
      }, 66);
      setTimeout(() => {
        clearInterval(draw);
        recorder.stop();
      }, 1200);
    });
  });
  await page
    .locator("input[type=file]")
    .setInputFiles({
      name: "local-demo.webm",
      mimeType: "video/webm",
      buffer: Buffer.from(videoBytes),
    });
  await page.getByRole("status").filter({ hasText: "视频已上传" }).waitFor();
  await page.waitForFunction(
    () => document.querySelector("video")?.readyState >= 1,
  );
  await page.getByRole("button", { name: "本周安排", exact: true }).click();
  await page
    .getByLabel("当天模板", { exact: true })
    .selectOption({ label: "上肢训练" });
  await page.getByRole("button", { name: "保存安排", exact: true }).click();
  await page.locator(".action-row").waitFor();
  await page.getByLabel(/的训练感受/).fill("这次训练状态很好，下次继续。");
  await page.getByRole("button", { name: "保存训练记录", exact: true }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "训练记录已保存" })
    .waitFor();
  for (let i = 0; i < 7; i++) {
    await page.locator(".day").nth(i).click();
    const select = page.getByLabel("当天模板", { exact: true });
    if (!(await select.inputValue())) {
      await select.selectOption({ label: "上肢训练" });
      await page.getByRole("button", { name: "保存安排", exact: true }).click();
      await page.waitForFunction(
        () => !document.querySelector("main[aria-busy=true]"),
      );
    }
  }
  assert.equal(await page.locator(".day.training").count(), 7);
  await page.locator(".day.today").click();
  const screenshots = resolve(root, "data/screenshots");
  await mkdir(screenshots, { recursive: true });
  const noOverflow = async () =>
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "Horizontal overflow",
    );
  await noOverflow();
  await page.screenshot({
    path: resolve(screenshots, "ipad-week.png"),
    fullPage: true,
  });
  await page.locator(".action-row").click();
  await page.getByRole("dialog").waitFor();
  await page.waitForFunction(
    () => document.querySelector(".modal video")?.readyState >= 1,
  );
  await page.screenshot({
    path: resolve(screenshots, "ipad-teaching.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "我的模板", exact: true }).click();
  await page.locator(".template-card").click();
  await page.getByLabel("动作步骤", { exact: true }).fill("已经修改过的讲解。");
  await page.getByRole("button", { name: "保存模板", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "模板已保存" }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await page.screenshot({
    path: resolve(screenshots, "mobile-template.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "训练记录", exact: true }).click();
  await page.locator(".record-card").click();
  await page.getByRole("dialog").getByText("哑铃划船", { exact: true }).click();
  await page
    .getByRole("dialog")
    .getByText("这是用户填写的原始教学说明。", { exact: true })
    .waitFor();
  await noOverflow();
  await page.screenshot({
    path: resolve(screenshots, "mobile-record.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "关闭 ×" }).click();
  await page.getByRole("button", { name: "本周安排", exact: true }).click();
  await noOverflow();
  await page.screenshot({
    path: resolve(screenshots, "mobile-week.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("heading", { name: "打开我的训练手记" }).waitFor();
  assert.equal(
    (await context.request.get(base + "/api/templates")).status(),
    401,
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: login → template/action → local video upload/playback → 7 training days → feeling record → snapshot preservation → mobile/iPad layout → logout",
  );
  console.log("Screenshots: " + screenshots);
} finally {
  await browser?.close();
  server.kill();
  await new Promise((resolve) =>
    server.exitCode !== null ? resolve() : server.once("exit", resolve),
  );
  if (resolve(temporary).startsWith(resolve(tmpdir(), "fitness-browser-")))
    await rm(temporary, { recursive: true, force: true });
}
