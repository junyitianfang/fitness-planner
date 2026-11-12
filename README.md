# 随练 · 个人训练手记

Python / FastAPI + Vue 3 + SQLite。本地项目位于 `D:\codex\fitness`，前端依赖通过本地链接复用原环境。已部署到现有 Instabox `dev` 的独立 Docker 服务，GitHub 提交仍由用户后续进行。

访问 [随练](https://8010-agq3u3z2gp4uo437ozlfvpdrwi.instabox.tech)，密码 `12345678`。部署路径和验证结果见 `docs/deployment.md`。

## 已实现

- 固定访问密码 `12345678`，七天有效会话与退出。
- 周一至周日的周历，可切换周，训练日数量自由，每天可选不同模板或休息。
- 创建、编辑、删除模板。每个模板分别管理自己的动作；添加、移除及调整动作顺序。
- 每个动作包含名称、步骤、呼吸、发力提示、常见错误、注意事项及教学视频。
- 用户上传现成 3D 或真人教学视频；支持 MP4、MOV、WebM，单文件最大 200 MB。提供鉴权和分段播放。
- 训练后填写感受，保存当天模板及动作的快照。后续修改或删除模板不会改写旧记录。
- 历史记录查看；手机底部导航、iPad 双栏布局、键盘焦点和弹窗操作。

模板初始为空，由你创建内容后从周历选择使用。3D 指上传视频的内容形式；当前程序不生成 3D 视频。第一版不包含记录导出。

## 使用当前环境启动（不下载依赖）

当前使用 Conda **langchain1.2**：Python 3.13.12 / FastAPI 0.135.1 / Uvicorn 0.46.0 / Pydantic 2.12.5 / python-multipart 0.0.32。已运行依赖安装检查，现有包全部满足要求，没有新增或升级。前端复用 Node 22.11 / Vue 3.5.45 / Vite 6.4.5。

推荐在 Anaconda PowerShell Prompt 执行：

```powershell
cd D:\codex\fitness
.\start.ps1
```

脚本会查找 `langchain1.2` 环境的 Python，检查依赖、构建前端，然后启动 [本地网站](http://127.0.0.1:8010)。输入固定密码 `12345678` 登录，无需初始化密码。按 Ctrl+C 停止。也可通过 `-PythonPath` 指定解释器，或通过 `-Port 8011` 换端口。不会自动下载依赖。

前端已经构建后，也可直接执行 `python backend/main.py` 启动。IDE 解释器选择 `langchain1.2`。模块启动方式仍支持 `uvicorn`、参数 `main:app --host 127.0.0.1 --port 8010 --no-proxy-headers`、工作目录 `D:\codex\fitness\backend`。

手动启动时，先激活环境，再执行原有命令：

```powershell
conda activate langchain1.2
# 仅在当前环境缺少依赖时安装，不要求升级。
python -m pip install -r D:\codex\fitness\backend\requirements.txt
```

在 `fitness/` 目录执行：

```powershell
# 检查并链接原项目已有的前端依赖，不运行 npm install。
./scripts/use-existing-frontend.ps1

# 构建前端。
npm run build --prefix frontend

cd backend

# 启动本地服务，同时提供前端页面。
python -m uvicorn main:app --host 127.0.0.1 --port 8010 --no-proxy-headers
```

打开 [本地网站](http://127.0.0.1:8010)，输入固定密码 `12345678`。密码固定在 `backend/main.py` 的 `ACCESS_PASSWORD` 常量中。

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
- 数据、视频、依赖目录和构建产物不进入 Git；固定访问密码按要求保存在后端源码中。
- Docker 使用 Python 3.13 slim 与 `backend/requirements.lock`，已配置 HTTPS 来源、Secure Cookie 和持久盘。服务器数据保存在 `/data/home/fitness-planner/data/`，本机数据仍保存在本机，两者不自动同步。

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

提交时可将整个 `fitness/` 目录作为独立仓库根目录。保留 `backend/`、`frontend/`、`scripts/`、`docs/`、`start.ps1`、本说明及 `.gitignore`；不用上传原博客代码。现有依赖链接及本地数据由 `.gitignore` 排除。

## Docker / Instabox 部署文件

已提供 `Dockerfile`、`compose.yaml`、`.env.example` 与部署依赖锁定文件。镜像使用本机构建好的 `frontend/dist`，不需要在服务器安装 Node 依赖。应用以 UID 10001 运行，数据库和视频挂载到容器外的 `/data`。

在本机执行 `npm run build --prefix frontend` 后，使用 Conda 解释器运行 `python scripts/package_deploy.py`，会生成忽略目录 `data/deploy/` 下两个文件：

- `fitness-release.tar.gz`：后端、前端源码及构建、Docker 配置和文档，排除依赖、编辑器配置及本地 Git 元数据。
- `fitness-seed.tar.gz`：SQLite 一致性备份和用户视频，备份副本中移除登录会话与失败计数；不修改本机原始数据。

将两个包上传到现有服务器后，可解出源码并运行 `scripts/deploy-server.sh RELEASE_ARCHIVE SEED_ARCHIVE HTTPS_ORIGIN`。脚本部署到 `/data/home/fitness-planner/`：`releases/` 保存发布代码，`current` 指向当前版本，`data/` 持久保存数据库与视频，更新时将数据备份到 `backups/`。首次部署导入种子数据，之后更新不覆盖服务器已有数据库。

服务独立使用 8010 端口，发布该端口取得 HTTPS URL，并将其不带路径和末尾斜杠的来源作为 `HTTPS_ORIGIN`。容器健康检查、退出自动重启、日志轮换、HTTPS Cookie 已配置。访问密码仍按用户要求固定为 `12345678`。

部署后的常用命令（在服务器 `/data/home/fitness-planner/current`）：

```bash
docker compose ps
docker compose logs --tail=100 fitness
docker compose restart fitness
```

Instabox 的空闲暂停和运行时长限制仍由平台管理；Docker 自动重启不会取消这些限制。本机与服务器的数据不会自动双向同步。
