# Docker MySQL Navicat 端口实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 Docker MySQL 安全映射到宿主机 `127.0.0.1:3307`，供 Navicat 连接，同时保持 Docker 后端使用 `mysql:3306`。

**架构：** Compose 通过 `127.0.0.1:3307:3306` 提供宿主机回环入口，Docker 内部服务发现与容器端口不变。重建 MySQL 容器时复用现有 `mysql_data` 命名卷。

**技术栈：** Docker Compose、MySQL 8.0、pytest、PyYAML

---

### 任务 1：以测试驱动方式增加 Navicat 端口

**文件：**
- 修改：`backend_python/tests/unit/test_container_entrypoint.py`
- 修改：`docker-compose.yml`
- 修改：`README.MD`

- [ ] 修改部署契约测试，断言 MySQL 端口严格等于 `127.0.0.1:3307:3306`，且后端地址仍包含 `@mysql:3306/ai_smart_review`。
- [ ] 运行定向测试，确认因当前 MySQL 没有 `ports` 而失败。
- [ ] 给 MySQL 服务增加 `ports: ["127.0.0.1:3307:3306"]`。
- [ ] 更新 README，分别说明 Navicat、Windows 本地后端和 Docker 后端的连接地址。
- [ ] 运行部署单元测试和 `docker compose --env-file .env.docker config --quiet`，确认通过。

### 任务 2：重建容器并验证数据

- [ ] 记录当前 Docker MySQL 核心表精确计数和 `mysql_data` 卷名。
- [ ] 运行 `docker compose --env-file .env.docker up -d mysql`，只重建 MySQL 服务。
- [ ] 确认 Windows MySQL 继续监听 `3306`，Docker MySQL 监听 `127.0.0.1:3307`。
- [ ] 从宿主机使用 `127.0.0.1:3307` 查询 Docker MySQL，并确认核心表计数未变化。
- [ ] 确认 Docker 后端继续把 `mysql` 解析为 MySQL 容器地址，前后端 HTTP 冒烟检查返回 200。
- [ ] 运行完整部署回归测试，检查 Git 状态并提交修改。
