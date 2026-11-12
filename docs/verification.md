# 本地检查记录

日期：2026-11-12。使用现有 Python、Node、npm 依赖及 Firefox；未下载新依赖和浏览器。

## 结果

- `python -m unittest discover -s fitness/backend/tests -v`：4 项通过。检查真实 HTTP 鉴权、CSRF 来源、退出撤销、7 天安排、休息日、无效日期、模板删除与历史快照、视频验证、分段请求和模板动作隔离。
- `npm run build --prefix fitness/frontend`：通过。Vue/Vite 生产构建正常。
- `node fitness/frontend/tests/e2e.mjs`：通过。使用现有 Firefox 1532，检查登录、创建模板/动作、生成并上传本地测试 WebM、播放视频、安排一周七天、填写感受、修改模板并回看原始记录、手机/iPad 尺寸布局、退出。
- 390×844、1024×1366 浏览器视口无横向溢出；已查看生成截图。
- `python -m compileall -q fitness/backend`：通过。
- 前端锁定文件从已有依赖图提取，排除依赖链接；仅读取本地文件。
- Git 排除检查：`data/`、`frontend/node_modules/`、`frontend/dist/` 已忽略。

截图在本地 `fitness/data/screenshots/`，不提交。测试使用独立临时数据库，未向产品中加入测试模板和视频。

## 范围

本次未部署 Docker、未提交 GitHub，也未在真实 iPhone/iPad Safari 上验收；视频实际兼容性仍取决于用户上传的编码格式。服务器部署及依赖版本锁定在后续阶段单独准备。

## Conda 启动检查

用户指定 `langchain1.2` 后，使用其 Python 3.13.12 运行 `pip install -r backend/requirements.txt`，四个依赖及其传递依赖均已满足，没有新增或升级包。

- 后端 4 项测试和完整 Firefox 浏览器流程在该环境下通过。
- 新增 `start.ps1` 与 `backend/check_environment.py`，自动定位 Conda 解释器、构建前端、检查密码设置并启动服务。
- 使用独立测试数据目录，执行启动脚本，确认首页 HTTP 200、匿名会话 HTTP 401；检查后关闭测试服务。
- 原始产品数据库尚未初始化个人密码，用户首次启动时通过终端自行设置。

## 固定密码调整

按用户新要求，访问密码改为后端常量 `12345678`，移除密码初始化命令及首次启动提示。既有模板、计划、视频和训练记录不做修改。新增空数据库直接登录及错误密码拒绝检查；5 项后端测试、完整 Firefox 浏览器流程通过。上述旧版初始化流程记录仅供历史参考，当前以 README 的固定密码说明为准。
