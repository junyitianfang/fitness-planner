// Verify an existing deployment without modifying the user's templates/schedule/records.
// A temporary template/video is created. The template is removed; output names the
// test video so the deployment operator can remove that exact file afterwards.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { firefox } from "playwright";

const root = fileURLToPath(new URL("../../", import.meta.url));
const base = process.argv[2];
assert(base?.startsWith("https://"), "Pass the deployed HTTPS origin");
const browser = await firefox.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE }
    : {}),
  ...(process.env.FITNESS_TEST_PROXY
    ? { proxy: { server: process.env.FITNESS_TEST_PROXY } }
    : {}),
});
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
});
const page = await context.newPage(),
  errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const output = resolve(root, "data/deploy/live-result.json");
const previous = process.argv.includes("--resume")
  ? JSON.parse(await readFile(output, "utf8"))
  : null;
const marker = previous?.marker || "部署验证-" + Date.now();
let templateId = previous?.templateId,
  videoName = previous?.videoName;
const headers = { Origin: base };
try {
  const anonymous = await context.request.get(base + "/api/session", {
    timeout: 45000,
  });
  assert.equal(anonymous.status(), 401);
  await page.goto(base, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.getByLabel("访问密码", { exact: true }).fill("12345678");
  await page.getByRole("button", { name: "进入手记 →" }).click();
  await page
    .getByRole("heading", { name: "把训练，放进这一周。" })
    .waitFor({ timeout: 45000 });
  const cookies = await context.cookies();
  assert(
    cookies.some((c) => c.name === "fitness_session" && c.secure && c.httpOnly),
  );
  const originalTemplates = (
    await (await context.request.get(base + "/api/templates")).json()
  ).filter((t) => t.id !== previous?.templateId);
  const originalRecords = await (
    await context.request.get(base + "/api/records")
  ).json();
  if (!previous) {
    await page.getByRole("button", { name: "我的模板", exact: true }).click();
    await page.getByRole("button", { name: "＋ 新建模板" }).click();
    await page.getByLabel("模板名称", { exact: true }).fill(marker);
    await page.getByRole("button", { name: "＋ 添加动作" }).click();
    await page.getByLabel("动作名称", { exact: true }).fill("临时视频验证");
    await page
      .getByLabel("动作步骤", { exact: true })
      .fill("仅用于部署验证，验证结束后移除。");
    await page.getByRole("button", { name: "保存模板", exact: true }).click();
    await page.getByRole("status").filter({ hasText: "模板已保存" }).waitFor();
    const all = await (
      await context.request.get(base + "/api/templates")
    ).json();
    templateId = all.find((t) => t.name === marker).id;
    await mkdir(resolve(root, "data/deploy"), { recursive: true });
    await writeFile(
      output,
      JSON.stringify({ templateId, marker, phase: "created" }),
    );

    const bytes = await page.evaluate(async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 180;
      const ctx = canvas.getContext("2d"),
        stream = canvas.captureStream(10);
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
        const timer = setInterval(() => {
          ctx.fillStyle = "#245c73";
          ctx.fillRect(0, 0, 320, 180);
          ctx.fillStyle = "#fff";
          ctx.font = "18px sans-serif";
          ctx.fillText("Deployment playback check", 18, 90);
        }, 100);
        setTimeout(() => {
          clearInterval(timer);
          recorder.stop();
        }, 1200);
      });
    });
    await page
      .locator("input[type=file]")
      .setInputFiles({
        name: "deployment-check.webm",
        mimeType: "video/webm",
        buffer: Buffer.from(bytes),
      });
    await page
      .getByRole("status")
      .filter({ hasText: "视频已上传" })
      .waitFor({ timeout: 45000 });
    await page.waitForFunction(
      () => document.querySelector("video")?.readyState >= 1,
      {},
      { timeout: 45000 },
    );
    const saved = (
      await (await context.request.get(base + "/api/templates")).json()
    ).find((t) => t.id === templateId);
    videoName = saved.actions[0].video;
    const range = await context.request.get(base + "/api/videos/" + videoName, {
      headers: { Range: "bytes=0-3" },
    });
    assert.equal(range.status(), 206);
    assert.equal((await range.body()).toString("hex"), "1a45dfa3");
    await writeFile(
      output,
      JSON.stringify({ templateId, videoName, marker, phase: "uploaded" }),
    );
  }
  console.log(
    "READY_FOR_RESTART: HTTPS login, template save, real video upload, playback and range checks passed.",
  );
  if (process.argv.includes("--wait-for-restart")) {
    const signal = resolve(root, "data/deploy/restart-confirmed");
    for (let i = 0; i < 240; i++) {
      try {
        await readFile(signal);
        break;
      } catch {}
      if (i === 239) throw new Error("Restart confirmation timed out");
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
  const persisted = await context.request.get(base + "/api/templates", {
    timeout: 45000,
  });
  assert.equal(persisted.status(), 200, "Session should survive restart");
  assert(
    (await persisted.json()).some(
      (t) => t.id === templateId && t.actions[0].video === videoName,
    ),
  );
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await page.getByRole("heading", { name: "把训练，放进这一周。" }).waitFor();
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.screenshot({
    path: resolve(root, "data/deploy/live-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1024, height: 1366 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  );
  await page.screenshot({
    path: resolve(root, "data/deploy/live-ipad.png"),
    fullPage: true,
  });
  const deleted = await context.request.delete(
    base + "/api/templates/" + templateId,
    { headers },
  );
  assert.equal(deleted.status(), 200);
  const after = await (
    await context.request.get(base + "/api/templates")
  ).json();
  assert.equal(after.length, originalTemplates.length);
  assert.deepEqual(
    await (await context.request.get(base + "/api/records")).json(),
    originalRecords,
  );
  assert.deepEqual(errors, []);
  await writeFile(
    output,
    JSON.stringify({
      templateId,
      videoName,
      marker,
      passed: true,
      originalTemplateCount: originalTemplates.length,
      originalRecordCount: originalRecords.length,
    }),
  );
  templateId = null;
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("heading", { name: "打开我的训练手记" }).waitFor();
  console.log(
    "PASS: HTTPS, secure cookie, templates, video playback/ranges, restart persistence, mobile/iPad viewports, logout. User data restored.",
  );
} finally {
  if (templateId)
    await context.request
      .delete(base + "/api/templates/" + templateId, { headers })
      .catch(() => {});
  await browser.close();
}
