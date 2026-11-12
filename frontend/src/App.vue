<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";

const page = ref("week"),
  loggedIn = ref(false),
  checking = ref(true);
const password = ref(""),
  error = ref(""),
  notice = ref(""),
  busy = ref(false);
const templates = ref([]),
  schedule = ref([]),
  records = ref([]);
const draft = ref(null),
  original = ref(""),
  expanded = ref(null);
const preview = ref(null),
  recordView = ref(null),
  uploading = ref(false),
  progress = ref(0);
let lastFocus;
watch(
  () => !!(preview.value || recordView.value),
  async (open) => {
    document.body.style.overflow = open ? "hidden" : "";
    if (open) {
      lastFocus = document.activeElement;
      await nextTick();
      document.querySelector(".modal .close-button")?.focus();
    } else lastFocus?.focus();
  },
);
function modalKeys(event) {
  if (event.key === "Escape") {
    preview.value = null;
    recordView.value = null;
  }
  if (event.key === "Tab") {
    const items = event.currentTarget.querySelectorAll(
      'button, summary, video, [tabindex="0"]',
    );
    const first = items[0],
      last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
}
const feeling = ref(""),
  choice = ref("");
const fields = [
  ["steps", "动作步骤"],
  ["breathing", "呼吸节奏"],
  ["cues", "发力提示"],
  ["mistakes", "常见错误"],
  ["precautions", "注意事项"],
];
const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const today = iso(new Date()),
  selected = ref(today);
const monday = ref(startOfWeek(new Date()));
function startOfWeek(d) {
  const result = new Date(d);
  result.setDate(result.getDate() - ((result.getDay() + 6) % 7));
  return iso(result);
}
function moveDate(day, n) {
  const d = new Date(day + "T12:00:00");
  d.setDate(d.getDate() + n);
  return iso(d);
}
const days = computed(() =>
  Array.from({ length: 7 }, (_, i) => {
    const day = moveDate(monday.value, i);
    return {
      day,
      label: weekdays[i],
      number: Number(day.slice(-2)),
      template: templateFor(day),
    };
  }),
);
const weekLabel = computed(
  () =>
    `${monday.value.replaceAll("-", " / ")} — ${moveDate(monday.value, 6).slice(5).replace("-", " / ")}`,
);
const trainingDays = computed(
  () => days.value.filter((d) => d.template).length,
);
const current = computed(() => templateFor(selected.value));
const dayRecords = computed(() =>
  records.value.filter((r) => r.day === selected.value),
);
const dirty = computed(
  () => draft.value && JSON.stringify(draft.value) !== original.value,
);
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2);
function templateFor(day) {
  return templates.value.find(
    (t) => t.id === schedule.value.find((s) => s.day === day)?.template_id,
  );
}
function selectDay(day) {
  if (feeling.value && !confirm("尚未保存训练感受，确定切换日期吗？")) return;
  selected.value = day;
  feeling.value = "";
  choice.value = templateFor(day)?.id || "";
}
let noticeTimer;
function flash(text) {
  notice.value = text;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (notice.value = ""), 4000);
}
async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers:
      options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (response.status === 401) loggedIn.value = false;
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const parsed = JSON.parse(text);
      message =
        typeof parsed.detail === "string"
          ? parsed.detail
          : "内容格式不正确，请检查必填项和文字长度";
    } catch {}
    throw new Error(message || `请求失败 (${response.status})`);
  }
  return response.json();
}
async function perform(fn) {
  error.value = "";
  busy.value = true;
  try {
    return await fn();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function loadWeek() {
  schedule.value = await api(
    `/schedule?start=${monday.value}&end=${moveDate(monday.value, 6)}`,
  );
  choice.value = templateFor(selected.value)?.id || "";
}
async function loadAll() {
  [templates.value, records.value] = await Promise.all([
    api("/templates"),
    api("/records"),
  ]);
  await loadWeek();
}
async function login() {
  await perform(async () => {
    await api("/login", {
      method: "POST",
      body: JSON.stringify({ password: password.value }),
    });
    password.value = "";
    loggedIn.value = true;
    await loadAll();
  });
}
async function logout() {
  if (uploading.value || busy.value || !canLeave()) return;
  await perform(async () => {
    await api("/logout", { method: "POST" });
    loggedIn.value = false;
    templates.value = [];
    records.value = [];
    schedule.value = [];
    draft.value = null;
    preview.value = null;
    recordView.value = null;
    feeling.value = "";
  });
}
function canLeave() {
  return (
    !(dirty.value || feeling.value) || confirm("有尚未保存的内容，确定离开吗？")
  );
}
function navigate(next) {
  if (next === page.value || busy.value || uploading.value || !canLeave())
    return;
  page.value = next;
  draft.value = null;
  feeling.value = "";
  error.value = "";
}
async function changeWeek(n) {
  if (busy.value || !canLeave()) return;
  await perform(async () => {
    monday.value = moveDate(monday.value, n * 7);
    selected.value = monday.value;
    feeling.value = "";
    await loadWeek();
  });
}
function edit(t) {
  if (
    uploading.value ||
    busy.value ||
    (dirty.value && !confirm("放弃尚未保存的模板修改吗？"))
  )
    return;
  draft.value = JSON.parse(JSON.stringify(t));
  original.value = JSON.stringify(draft.value);
  expanded.value = t.actions[0]?.id || null;
}
function newTemplate() {
  edit({ name: "", description: "", actions: [] });
}
function addAction() {
  const a = { id: uid(), name: "", video: null };
  fields.forEach(([key]) => (a[key] = ""));
  draft.value.actions.push(a);
  expanded.value = a.id;
}
function removeAction(index) {
  if (confirm("从当前模板移除这个动作？保存模板后生效。"))
    draft.value.actions.splice(index, 1);
}
function reorder(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= draft.value.actions.length) return;
  const [a] = draft.value.actions.splice(index, 1);
  draft.value.actions.splice(target, 0, a);
}
async function saveDraft() {
  if (!draft.value.name.trim()) throw new Error("请填写模板名称");
  if (draft.value.actions.some((a) => !a.name.trim()))
    throw new Error("请填写每个动作的名称");
  const value = await api(
    "/templates" + (draft.value.id ? "/" + draft.value.id : ""),
    {
      method: draft.value.id ? "PUT" : "POST",
      body: JSON.stringify(draft.value),
    },
  );
  draft.value = value;
  original.value = JSON.stringify(value);
  templates.value = await api("/templates");
  choice.value = templateFor(selected.value)?.id || "";
  return value;
}
async function save() {
  await perform(async () => {
    await saveDraft();
    flash("模板已保存");
  });
}
async function removeTemplate() {
  if (!confirm("删除此模板？使用它的日程会移除，已保存的训练记录会保留。"))
    return;
  await perform(async () => {
    await api("/templates/" + draft.value.id, { method: "DELETE" });
    draft.value = null;
    original.value = "";
    await loadAll();
    flash("模板已删除");
  });
}
async function uploadVideo(event, actionId) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (file.size > 200 * 1024 * 1024) {
    error.value = "视频不能超过 200 MB";
    return;
  }
  error.value = "";
  uploading.value = true;
  progress.value = 0;
  try {
    const saved = await saveDraft();
    const form = new FormData();
    form.append("file", file);
    const value = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `/api/templates/${saved.id}/actions/${actionId}/video`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable)
          progress.value = Math.round((e.loaded / e.total) * 100);
      };
      xhr.onerror = () => reject(new Error("上传失败，请检查网络后重试"));
      xhr.onload = () => {
        if (xhr.status === 401) loggedIn.value = false;
        try {
          const data = JSON.parse(xhr.responseText);
          xhr.status >= 200 && xhr.status < 300
            ? resolve(data)
            : reject(
                new Error(
                  typeof data.detail === "string" ? data.detail : "上传失败",
                ),
              );
        } catch {
          reject(new Error("上传失败，请重试"));
        }
      };
      xhr.send(form);
    });
    draft.value = value;
    original.value = JSON.stringify(value);
    templates.value = await api("/templates");
    flash("视频已上传，模板已保存");
  } catch (e) {
    error.value = e.message;
  } finally {
    uploading.value = false;
  }
}
async function assign() {
  await perform(async () => {
    await api("/schedule/" + selected.value, {
      method: "PUT",
      body: JSON.stringify({ template_id: choice.value || null }),
    });
    await loadWeek();
    flash("当天安排已保存");
  });
}
async function saveRecord() {
  if (!feeling.value.trim()) {
    error.value = "请先填写训练感受";
    return;
  }
  await perform(async () => {
    await api("/records", {
      method: "POST",
      body: JSON.stringify({ day: selected.value, feeling: feeling.value }),
    });
    feeling.value = "";
    records.value = await api("/records");
    flash("训练记录已保存");
  });
}
onMounted(async () => {
  try {
    await api("/session");
    loggedIn.value = true;
    await loadAll();
  } catch (e) {
    if (loggedIn.value) error.value = e.message;
  } finally {
    checking.value = false;
  }
});
window.addEventListener("beforeunload", (e) => {
  if (dirty.value || feeling.value || uploading.value) {
    e.preventDefault();
    e.returnValue = "";
  }
});
</script>

<template>
  <div v-if="checking" class="loading" role="status">正在打开你的训练手记…</div>
  <main v-else-if="!loggedIn" class="login-layout">
    <section class="login-story">
      <div class="wordmark">随练<span>SUÍ LIÀN</span></div>
      <div>
        <p class="eyebrow">MY TRAINING JOURNAL</p>
        <h1>按自己的节奏，<br />练好每一天。</h1>
        <p>把动作、安排和每一次训练的感受，<br />留在自己的训练手记里。</p>
      </div>
      <div class="track-art" aria-hidden="true">
        <i></i><i></i><i></i><span>MOVE AT YOUR OWN PACE</span>
      </div>
    </section>
    <section class="login-form">
      <p class="eyebrow">欢迎回来</p>
      <h2>打开我的训练手记</h2>
      <p class="muted">输入个人访问密码，继续你的训练安排。</p>
      <form @submit.prevent="login">
        <label
          >访问密码<input
            v-model="password"
            type="password"
            required
            autocomplete="current-password"
            autofocus
            maxlength="1024"
        /></label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary wide" :disabled="busy">
          {{ busy ? "正在打开…" : "进入手记 →" }}
        </button>
      </form>
      <p class="privacy-note">你的安排、教学视频与训练感受，集中保存在这里。</p>
    </section>
  </main>
  <div v-else class="app-shell">
    <header class="topbar">
      <div class="wordmark">随练<span>我的训练手记</span></div>
      <nav aria-label="主导航">
        <button
          v-for="[key, label] in [
            ['week', '本周安排'],
            ['templates', '我的模板'],
            ['records', '训练记录'],
          ]"
          :key="key"
          :class="{ active: page === key }"
          :aria-current="page === key ? 'page' : undefined"
          @click="navigate(key)"
        >
          {{ label }}
        </button>
      </nav>
      <button class="quiet" :disabled="busy || uploading" @click="logout">
        退出
      </button>
    </header>
    <main class="workspace" :aria-busy="busy || uploading">
      <p v-if="error" class="error global-error" role="alert">
        {{ error }}<button class="quiet" @click="error = ''">关闭</button>
      </p>
      <template v-if="page === 'week'">
        <section class="page-heading">
          <div>
            <p class="eyebrow">YOUR WEEK, YOUR PACE</p>
            <h1>把训练，放进这一周。</h1>
            <p class="muted">选择想练的日子，给每一天安排适合的模板。</p>
          </div>
          <div class="week-summary">
            <strong>{{ trainingDays }}</strong
            ><span>天已安排训练<br />这周的节奏，由你决定</span>
          </div>
        </section>
        <section class="calendar-section">
          <div class="section-bar">
            <h2>训练周历</h2>
            <div class="week-switch">
              <button
                class="icon-button"
                aria-label="上一周"
                :disabled="busy"
                @click="changeWeek(-1)"
              >
                ‹</button
              ><span>{{ weekLabel }}</span
              ><button
                class="icon-button"
                aria-label="下一周"
                :disabled="busy"
                @click="changeWeek(1)"
              >
                ›
              </button>
            </div>
          </div>
          <div class="calendar">
            <button
              v-for="d in days"
              :key="d.day"
              class="day"
              :class="{
                selected: d.day === selected,
                today: d.day === today,
                training: !!d.template,
              }"
              :aria-pressed="d.day === selected"
              @click="selectDay(d.day)"
            >
              <span class="day-week"
                >{{ d.label }}<i v-if="d.day === today">今天</i></span
              ><strong>{{ d.number }}</strong
              ><span class="day-template">{{
                d.template?.name || "自由安排"
              }}</span
              ><span class="day-mark">{{
                d.template
                  ? `${d.template.actions.length} 个动作`
                  : "＋ 选择模板"
              }}</span>
            </button>
          </div>
        </section>
        <div class="day-layout">
          <section class="panel day-content">
            <div class="section-bar">
              <div>
                <p class="eyebrow">{{ selected }}</p>
                <h2>{{ current?.name || "今天，怎样安排？" }}</h2>
              </div>
              <span class="pill">{{ current ? "训练日" : "自由安排" }}</span>
            </div>
            <p v-if="current?.description" class="muted prewrap">
              {{ current.description }}
            </p>
            <div class="assignment">
              <label :for="'template-choice'">当天模板</label>
              <div class="input-row">
                <select id="template-choice" v-model="choice" :disabled="busy">
                  <option value="">自由安排 / 休息</option>
                  <option v-for="t in templates" :key="t.id" :value="t.id">
                    {{ t.name }}
                  </option></select
                ><button
                  class="primary"
                  :disabled="busy || choice === (current?.id || '')"
                  @click="assign"
                >
                  保存安排
                </button>
              </div>
            </div>
            <template v-if="current"
              ><div class="action-list">
                <button
                  v-for="(a, index) in current.actions"
                  :key="a.id"
                  class="action-row"
                  @click="preview = a"
                >
                  <span class="action-number">{{
                    String(index + 1).padStart(2, "0")
                  }}</span
                  ><span class="action-copy"
                    ><strong>{{ a.name }}</strong
                    ><small>{{
                      a.video ? "视频教学 · 动作讲解" : "动作讲解"
                    }}</small></span
                  ><span class="play-icon" aria-hidden="true">{{
                    a.video ? "▷" : "↗"
                  }}</span>
                </button>
              </div>
              <p v-if="!current.actions.length" class="empty">
                这个模板还没有动作。前往“我的模板”添加动作和教学内容。
              </p></template
            >
            <div v-else class="empty">
              <span class="empty-symbol">↗</span>
              <h3>留一点时间给身体</h3>
              <p>
                {{
                  templates.length
                    ? "从上方选择一个模板，开始安排这一天。"
                    : "先创建一个自己的训练模板，再把它放进周历。"
                }}
              </p>
              <button
                v-if="!templates.length"
                class="secondary"
                @click="navigate('templates')"
              >
                创建第一个模板
              </button>
            </div>
          </section>
          <aside class="panel reflection">
            <p class="eyebrow">AFTER YOUR SESSION</p>
            <h2>练完，记下感受。</h2>
            <p class="muted">
              哪里练得顺，哪里需要调整？留给下一次训练的自己。
            </p>
            <form @submit.prevent="saveRecord">
              <label for="feeling">{{ selected }} 的训练感受</label
              ><textarea
                id="feeling"
                v-model="feeling"
                rows="6"
                maxlength="10000"
                placeholder="今天的身体状态、动作感受、下次想调整的地方…"
                :disabled="!current || selected > today"
              ></textarea>
              <p v-if="selected > today" class="muted small">
                训练结束后再来记录这一天。
              </p>
              <button
                class="primary wide"
                :disabled="
                  busy ||
                  !current?.actions.length ||
                  !feeling.trim() ||
                  selected > today
                "
              >
                保存训练记录
              </button>
            </form>
            <div v-if="dayRecords.length" class="day-records">
              <h3>当天已保存 {{ dayRecords.length }} 条</h3>
              <button
                v-for="r in dayRecords"
                :key="r.id"
                class="text-link"
                @click="recordView = r"
              >
                查看记录 · {{ r.snapshot.name }} ↗
              </button>
            </div>
          </aside>
        </div>
      </template>
      <template v-if="page === 'templates'">
        <section class="page-heading">
          <div>
            <p class="eyebrow">MAKE IT YOURS</p>
            <h1>自己的动作，自己的模板。</h1>
            <p class="muted">每个模板独立保存动作、教学视频和文字细节。</p>
          </div>
          <button
            class="primary"
            :disabled="busy || uploading"
            @click="newTemplate"
          >
            ＋ 新建模板
          </button>
        </section>
        <div class="editor-layout">
          <aside class="template-list">
            <button
              v-for="t in templates"
              :key="t.id"
              class="template-card"
              :class="{ chosen: draft?.id === t.id }"
              @click="edit(t)"
            >
              <strong>{{ t.name }}</strong
              ><span>{{ t.actions.length }} 个动作</span>
              <p>{{ t.description || "点击编辑模板" }}</p>
            </button>
            <div v-if="!templates.length" class="empty compact">
              <h3>从你的第一个模板开始</h3>
              <p>例如“上肢训练”或“周末全身训练”。</p>
              <button class="secondary" @click="newTemplate">创建模板</button>
            </div>
          </aside>
          <section v-if="draft" class="panel editor">
            <div class="section-bar">
              <h2>{{ draft.id ? "编辑模板" : "新建模板" }}</h2>
              <span class="muted small">{{
                dirty ? "有未保存的修改" : "已保存"
              }}</span>
            </div>
            <fieldset :disabled="busy || uploading">
              <label
                >模板名称<input
                  v-model="draft.name"
                  maxlength="120"
                  placeholder="例如：哑铃上肢训练" /></label
              ><label
                >模板说明<textarea
                  v-model="draft.description"
                  rows="2"
                  maxlength="2000"
                  placeholder="写下这套训练的目标或使用场景"
                ></textarea>
              </label>
              <div class="section-bar">
                <h3>训练动作 · {{ draft.actions.length }}</h3>
                <button
                  class="secondary"
                  :disabled="draft.actions.length >= 100"
                  @click="addAction"
                >
                  ＋ 添加动作
                </button>
              </div>
              <p v-if="!draft.actions.length" class="empty compact">
                添加动作后，可以填写教学细节并上传视频。
              </p>
              <article
                v-for="(a, index) in draft.actions"
                :key="a.id"
                class="action-editor"
              >
                <div class="action-editor-heading">
                  <button
                    class="expand-button"
                    :aria-expanded="expanded === a.id"
                    @click="expanded = expanded === a.id ? null : a.id"
                  >
                    <span class="action-number">{{
                      String(index + 1).padStart(2, "0")
                    }}</span
                    ><strong>{{ a.name || "未命名动作" }}</strong
                    ><span>{{ expanded === a.id ? "−" : "＋" }}</span>
                  </button>
                  <div class="order-buttons">
                    <button
                      class="icon-button"
                      aria-label="动作上移"
                      :disabled="index === 0"
                      @click="reorder(index, -1)"
                    >
                      ↑</button
                    ><button
                      class="icon-button"
                      aria-label="动作下移"
                      :disabled="index === draft.actions.length - 1"
                      @click="reorder(index, 1)"
                    >
                      ↓
                    </button>
                  </div>
                </div>
                <div v-if="expanded === a.id" class="action-editor-body">
                  <label
                    >动作名称<input
                      v-model="a.name"
                      maxlength="120"
                      placeholder="例如：哑铃划船"
                  /></label>
                  <div class="video-upload">
                    <video
                      v-if="a.video"
                      :src="'/api/videos/' + a.video"
                      controls
                      playsinline
                      preload="metadata"
                    ></video>
                    <div v-else class="video-placeholder">
                      <span>▷</span>
                      <p>放入这个动作的教学视频</p>
                    </div>
                    <label class="upload-label secondary"
                      >{{ a.video ? "替换教学视频" : "上传教学视频"
                      }}<input
                        type="file"
                        accept=".mp4,.mov,.webm"
                        @change="uploadVideo($event, a.id)"
                    /></label>
                    <p class="muted small">
                      MP4 / WebM / MOV，最大 200 MB。手机与 iPad 建议使用 H.264
                      MP4。上传时会同时保存当前模板。
                    </p>
                  </div>
                  <label v-for="[key, label] in fields" :key="key"
                    >{{ label
                    }}<textarea
                      v-model="a[key]"
                      :rows="key === 'steps' ? 4 : 2"
                      :maxlength="key === 'steps' ? 10000 : 5000"
                      :placeholder="`填写${label}`"
                    ></textarea></label
                  ><button class="danger-text" @click="removeAction(index)">
                    移除此动作
                  </button>
                </div>
              </article>
            </fieldset>
            <div v-if="uploading" class="upload-status" role="status">
              <progress :value="progress" max="100"></progress>正在上传视频
              {{ progress }}%
            </div>
            <div class="editor-footer">
              <button
                v-if="draft.id"
                class="danger-text"
                :disabled="busy || uploading"
                @click="removeTemplate"
              >
                删除模板</button
              ><span v-else></span
              ><button
                class="primary"
                :disabled="busy || uploading"
                @click="save"
              >
                {{ busy ? "正在保存…" : "保存模板" }}
              </button>
            </div>
          </section>
          <section v-else class="panel empty editor-empty">
            <span class="empty-symbol">＋</span>
            <h2>让每个动作都有自己的讲解</h2>
            <p>选择一个模板开始编辑，或创建新的训练模板。</p>
          </section>
        </div>
      </template>
      <template v-if="page === 'records'"
        ><section class="page-heading">
          <div>
            <p class="eyebrow">A LITTLE BETTER, EVERY TIME</p>
            <h1>把进步，慢慢留下来。</h1>
            <p class="muted">
              记录保留训练当天的动作和讲解，方便回看当时的安排。
            </p>
          </div>
          <span class="pill">{{ records.length }} 条训练记录</span>
        </section>
        <div v-if="!records.length" class="panel empty">
          <span class="empty-symbol">↗</span>
          <h2>第一条记录，从下一次训练开始</h2>
          <p>在周历里安排训练，练完填写感受，就会保存在这里。</p>
          <button class="secondary" @click="navigate('week')">回到周历</button>
        </div>
        <div class="records-grid">
          <button
            v-for="r in records"
            :key="r.id"
            class="panel record-card"
            @click="recordView = r"
          >
            <time>{{ r.day }}</time>
            <h2>{{ r.snapshot.name }}</h2>
            <p class="prewrap">{{ r.feeling }}</p>
            <span
              >{{ r.snapshot.actions.length }} 个动作
              <b>查看当天记录 ↗</b></span
            >
          </button>
        </div></template
      >
    </main>
    <footer class="site-footer">随练 · 每一次认真练习，都值得被记住。</footer>
    <p v-if="notice" class="toast" role="status">{{ notice }}</p>
    <div
      v-if="preview || recordView"
      class="modal-backdrop"
      @click.self="
        preview = null;
        recordView = null;
      "
      @keydown="modalKeys"
    >
      <section
        class="modal panel"
        role="dialog"
        aria-modal="true"
        :aria-label="preview?.name || '训练记录'"
        tabindex="-1"
      >
        <button
          class="close-button secondary"
          autofocus
          @click="
            preview = null;
            recordView = null;
          "
        >
          关闭 ×</button
        ><template v-if="preview"
          ><p class="eyebrow">动作教学</p>
          <h2>{{ preview.name }}</h2>
          <video
            v-if="preview.video"
            :src="'/api/videos/' + preview.video"
            controls
            playsinline
            preload="metadata"
          ></video>
          <p v-else class="muted">还没有上传教学视频，可先查看下方动作讲解。</p>
          <section
            v-for="[key, label] in fields"
            :key="key"
            class="teaching-section"
          >
            <h3>{{ label }}</h3>
            <p class="prewrap">{{ preview[key] || "尚未填写" }}</p>
          </section></template
        ><template v-else-if="recordView"
          ><p class="eyebrow">{{ recordView.day }} · 训练记录</p>
          <h2>{{ recordView.snapshot.name }}</h2>
          <section class="teaching-section">
            <h3>当天的训练感受</h3>
            <p class="prewrap">{{ recordView.feeling }}</p>
          </section>
          <h3>当天的动作</h3>
          <details
            v-for="a in recordView.snapshot.actions"
            :key="a.id"
            class="record-action"
          >
            <summary>{{ a.name }}</summary>
            <video
              v-if="a.video"
              :src="'/api/videos/' + a.video"
              controls
              playsinline
              preload="none"
            ></video>
            <section
              v-for="[key, label] in fields"
              :key="key"
              class="teaching-section"
            >
              <h4>{{ label }}</h4>
              <p class="prewrap">{{ a[key] || "尚未填写" }}</p>
            </section>
          </details></template
        >
      </section>
    </div>
  </div>
</template>
