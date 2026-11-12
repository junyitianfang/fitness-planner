# 随练 · 个人训练手记

Python / FastAPI + Vue 3 + SQLite。当前位于原项目的 `fitness/` 子目录，代码和数据独立。此阶段仅交付本地代码，GitHub 提交由用户后续进行，服务器部署另行准备。

## 已实现

- 个人访问密码、七天有效会话、退出和密码重置；没有默认密码。
- 周一至周日的周历，可切换周，训练日数量自由，每天可选不同模板或休息。
- 创建、编辑、删除模板。每个模板分别管理自己的动作；添加、移除及调整动作顺序。
- 每个动作包含名称、步骤、呼吸、发力提示、常见错误、注意事项及教学视频。
- 用户上传现成 3D 或真人教学视频；支持 MP4、MOV、WebM，单文件最大 200 MB。提供鉴权和分段播放。
- 训练后填写感受，保存当天模板及动作的快照。后续修改或删除模板不会改写旧记录。
- 历史记录查看；手机底部导航、iPad 双栏布局、键盘焦点和弹窗操作。

模板初始为空，由你创建内容后从周历选择使用。3D 指上传视频的内容形式；当前程序不生成 3D 视频。第一版不包含记录导出。

## 使用当前环境启动（不下载依赖）

本机已验证 Python 3.8.5 / FastAPI 0.103.2 / Uvicorn 0.23.2 / Pydantic 2.4.2 / python-multipart 0.0.6，Node 22.11 / Vue 3.5.45 / Vite 6.4.5。

在 `fitness/` 目录执行：

```powershell
# 检查并链接原项目已有的前端依赖，不运行 npm install。
./scripts/use-existing-frontend.ps1

# 构建前端。
npm run build --prefix frontend

# 交互设置个人密码，至少 10 字符；密码不会出现在命令行或代码中。
cd backend
python main.py init-password

# 启动本地服务，同时提供前端页面。
python -m uvicorn main:app --host 127.0.0.1 --port 8010 --no-proxy-headers
```

打开 [本地网站](http://127.0.0.1:8010)，输入刚设置的密码。重新运行 `init-password` 可以改密码，并撤销已有会话。

前端开发热更新时，另开终端在 `fitness/frontend` 运行 `npm run dev`；后端启动前设置 `$env:FITNESS_ORIGIN='http://127.0.0.1:5174'`。开发页面地址为 [127.0.0.1:5174](http://127.0.0.1:5174)。切回前后端同源访问时，应移除这条环境变量或改为实际来源。

`frontend/node_modules` 是指向原项目已安装目录的本地链接，不提交到 Git。`package-lock.json` 从现有项目锁定文件中提取所需依赖图生成，并做离线验证。整个实现与检查过程未下载 npm/pip 依赖或浏览器。将来单独取出项目时，可通过已有的兼容依赖目录使用同一脚本的 `-DependencyPath` 参数；需要新安装环境时再使用锁定文件，不影响当前环境。

## 数据与设置

- 默认数据目录 `fitness/data/`，数据库为 `fitness.sqlite`，视频在 `videos/`。
- `FITNESS_DATA_DIR` 可指定其他绝对目录，后续 Docker 将挂载到持久盘。
- `FITNESS_ORIGIN` 为浏览器访问来源（协议、域名及端口，不带末尾 `/`）；默认与本地请求来源一致。
- `FITNESS_SECURE_COOKIE=true` 用于后续 HTTPS 环境；本地 HTTP 默认 `false`。
- 用户安排日期按浏览器本地日期显示；未来训练记录校验使用中国标准时间（UTC+8）。
- 视频直接播放，不做转码。手机/iPad 优先上传 H.264 编码的 MP4；MOV/WebM 的播放取决于设备支持的编码。
- 记录快照可能引用旧视频，所以替换视频或删除模板后保留原视频文件，避免历史记录失效。备份时数据库与视频目录应一起保存。
- 数据、视频、依赖目录、构建产物与密码均不会进入 Git；源码中没有初始密码。
- 后续部署前单独确定 Python 基础镜像、依赖锁定、HTTPS、上传限制和持久盘。本次没有构建或启动 Docker 容器。

## 检查

在 `fitness/` 目录：

```powershell
python -m unittest discover -s backend/tests -v
npm run build --prefix frontend

# 本机已有这个 Firefox；不运行 playwright install。
$env:PLAYWRIGHT_FIREFOX_EXECUTABLE="$env:LOCALAPPDATA\ms-playwright\firefox-1532\firefox\firefox.exe"
node frontend/tests/e2e.mjs
```

后端测试使用真实 HTTP 和临时数据库；覆盖鉴权、请求来源校验、退出、任意训练日、无效日期、历史快照、视频验证、动作隔离及分段播放。浏览器检查创建模板和动作、上传现场生成的测试 WebM、播放、七天训练安排、记录与原始快照，以及 390px 手机 / 1024px iPad 布局和退出。测试数据独立，截图输出到忽略的 `data/screenshots/`。

## 后续提交 GitHub

提交时可将整个 `fitness/` 目录作为独立仓库根目录。保留 `backend/`、`frontend/`、`scripts/`、`docs/`、本说明及 `.gitignore`；不用上传原博客代码。现有依赖链接及本地数据由 `.gitignore` 排除。
