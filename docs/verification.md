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
