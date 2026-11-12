# Instabox 部署结果

2026-11-12，已部署到现有服务器 `dev`（`m_agq3u3z2gp4uo437ozlfvpdrwi`）。

入口：[随练](https://8010-agq3u3z2gp4uo437ozlfvpdrwi.instabox.tech)，用户指定的固定密码为 `12345678`。

## 服务器配置

- Compose 项目：`fitness-planner`，容器：`fitness-planner-fitness-1`。
- 端口：宿主 8010 → 容器 8000；原博客的 8000 端口服务仍健康运行。
- 当前源码：`/data/home/fitness-planner/current`，指向 `releases/20261112T135920Z`。
- 数据：`/data/home/fitness-planner/data` → 容器 `/data`，位于 Instabox 持久盘。
- 数据库：`data/fitness.sqlite`；视频：`data/videos/`。
- 镜像：`fitness-planner:local`，Python 3.13 slim + `backend/requirements.lock`；前端使用本机构建产物。
- 非 root UID 10001、只读根文件系统、临时上传目录、Secure/HttpOnly Cookie、健康检查、`unless-stopped` 重启策略与日志轮换。

## 验证

- Docker 构建并启动成功，容器状态 `healthy`。
- 容器内 5 项后端 HTTP 测试通过，使用独立临时数据库。
- 公网 HTTPS 登录成功；确认 Secure / HttpOnly 会话 Cookie。
- 临时模板保存、真实 WebM 视频上传、浏览器视频元数据加载和 HTTP 206 范围读取通过。
- 执行容器重启并等待健康恢复；重启后 API 查询确认临时模板及视频引用保留。
- 测试模板和视频已清理；服务器最终业务数据计数为 1 个模板、1 天安排、0 条记录，与导入数据一致。
- 数据库一致性备份：宿主 `data/backups/fitness-20261112T141106Z.sqlite`，通过 SQLite backup API 生成。
- 最终公网复查脚本 `frontend/tests/deployed-readonly.mjs` 通过：HTTPS 登录、Secure Cookie、原有业务数据恢复、390px 手机 / 1024px iPad 无横向溢出、截图与退出；测试模板清理已确认。

公网验证期间本机代理存在间歇性 TLS / 页面完整 load 超时，服务器服务仍健康。验证改按 DOM 就绪和关键功能分别检查，不把网络超时视为应用测试通过。

## 使用与维护

```bash
cd /data/home/fitness-planner/current
docker compose ps
docker compose logs --tail=100 fitness
docker compose restart fitness
```

备份应同时包含数据库和视频。当前已有一次数据库快照，不代表已设置定时备份。本机和服务器的数据不自动双向同步。

Instabox 空闲暂停为 1800 秒；本次唤醒时观测到运行上限为 120 分钟，平台可能按实际活动和套餐调整。平台暂停和运行时长限制不由 Docker 重启策略取消，访问可能需要等待平台唤醒或运行限制恢复。
