# Docker MySQL 内网化与本地数据迁移实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 移除 Docker MySQL 的宿主机端口映射，并把 Windows MySQL 中的既有业务数据、旧助手消息和上传文件安全复制到 Docker 数据服务。

**架构：** Docker 后端始终通过 Compose 内部 DNS 地址 `mysql:3306` 连接 MySQL；Windows MySQL 保持 `127.0.0.1:3306` 不变。先生成可恢复的 SQL 备份，再把备份导入未暴露宿主机端口的 MySQL 容器，随后启动完整服务并把旧助手消息迁移到 PostgreSQL。

**技术栈：** Docker Compose、MySQL 8.0、PostgreSQL 16、PowerShell、pytest、PyYAML、FastAPI

---

## 文件结构

- 修改：`docker-compose.yml`——删除 MySQL 的宿主机 `ports` 映射，保留内部 `mysql:3306` 连接。
- 修改：`backend_python/tests/unit/test_container_entrypoint.py`——锁定 MySQL 仅限 Docker 内网、PostgreSQL/Redis 继续绑定回环地址的部署契约。
- 修改：`README.MD`——说明 MySQL 不暴露宿主机端口，以及本地和 Docker 两种运行方式使用的数据库地址。
- 运行时产物（仓库外，不提交）：`../ai-smart-homework-review-backups/ai_smart_review-<时间戳>.sql`——Windows MySQL 的迁移前备份。

### 任务 1：以测试驱动方式移除 MySQL 宿主机端口

**文件：**
- 修改：`backend_python/tests/unit/test_container_entrypoint.py`
- 修改：`docker-compose.yml`
- 修改：`README.MD`

- [ ] **步骤 1：把现有端口测试改成目标部署契约**

将 `test_compose_documents_env_file_and_binds_databases_to_loopback` 替换为：

```python
def test_compose_keeps_mysql_internal_and_binds_supporting_data_services_to_loopback() -> None:
    compose_text = _read("docker-compose.yml")
    compose = yaml.safe_load(compose_text)

    assert "docker compose --env-file .env.docker up -d" in compose_text
    assert "ports" not in compose["services"]["mysql"]
    for service in ("postgres", "redis"):
        assert all(
            str(port).startswith("127.0.0.1:")
            for port in compose["services"][service]["ports"]
        )
    assert "@mysql:3306/ai_smart_review" in compose["services"]["backend"]["environment"]["DATABASE_URL"]
```

- [ ] **步骤 2：运行定向测试并确认失败**

运行：

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_container_entrypoint.py::test_compose_keeps_mysql_internal_and_binds_supporting_data_services_to_loopback -q
```

预期：FAIL，失败点为 MySQL 服务仍然包含 `ports`。

- [ ] **步骤 3：从 Compose 删除 MySQL 的端口映射**

从 `docker-compose.yml` 的 `mysql` 服务删除：

```yaml
ports:
  - "127.0.0.1:3306:3306"
```

保持后端连接不变：

```yaml
DATABASE_URL: mysql+pymysql://root:${MYSQL_ROOT_PASSWORD:?Set MYSQL_ROOT_PASSWORD via --env-file .env.docker}@mysql:3306/ai_smart_review?charset=utf8mb4
```

- [ ] **步骤 4：更新 Docker 部署文档**

把 `README.MD` Docker 部署段落中的数据库端口说明改为：

```markdown
共 6 个服务：`mysql` / `postgres` / `redis` / `backend`（:8000，启动时自动执行双库迁移与种子数据）/ `worker`（Celery 批改队列）/ `frontend`（:80，nginx 反代 + SSE 专用配置）。MySQL 仅在 Docker 内网通过 `mysql:3306` 访问，不映射宿主机端口；PostgreSQL 与 Redis 仅绑定 `127.0.0.1`。

直接在 Windows 运行后端时使用 `localhost:3306` 连接 Windows MySQL；通过 Compose 运行后端时使用 `mysql:3306` 连接 Docker MySQL。
```

- [ ] **步骤 5：验证配置测试与 Compose 解析通过**

运行：

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_container_entrypoint.py -q
docker compose --env-file .env.docker config --quiet
```

预期：pytest 全部 PASS；Compose 命令退出码为 0，且不输出配置错误。

- [ ] **步骤 6：提交部署配置变更**

```powershell
git add docker-compose.yml README.MD backend_python/tests/unit/test_container_entrypoint.py
git commit -m "fix: 避免 Docker MySQL 占用宿主机端口"
```

### 任务 2：备份 Windows MySQL 并导入 Docker MySQL

**文件：**
- 创建（仓库外）：`../ai-smart-homework-review-backups/ai_smart_review-<时间戳>.sql`

- [ ] **步骤 1：确认源数据库与 Docker 目标状态**

运行：

```powershell
Get-Service MySQL80
Get-NetTCPConnection -LocalPort 3306 -State Listen
docker compose --env-file .env.docker ps
docker volume ls
```

预期：`MySQL80` 为 Running，Windows `3306` 正在监听；首次迁移前不存在本项目正在运行的 MySQL 容器。若目标 MySQL 数据卷已经包含数据，停止导入并先比较目标数据，不能覆盖未知数据。

- [ ] **步骤 2：把 Windows MySQL 导出到仓库外备份目录**

运行以下 PowerShell；`mysqldump` 提示时输入 Windows MySQL 的 root 密码：

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path (Split-Path $PWD -Parent) 'ai-smart-homework-review-backups'
New-Item -ItemType Directory -Force $backupDir | Out-Null
$backupFile = Join-Path $backupDir "ai_smart_review-$timestamp.sql"
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' --host=127.0.0.1 --port=3306 --user=root --password --single-transaction --routines --triggers --events --set-gtid-purged=OFF --default-character-set=utf8mb4 --databases ai_smart_review --result-file=$backupFile
if ($LASTEXITCODE -ne 0) { throw 'Windows MySQL 备份失败，停止迁移' }
Get-Item $backupFile | Select-Object FullName, Length, LastWriteTime
```

预期：生成非空 SQL 文件；当前数据库约 0.78 MB，因此备份文件应明显大于 0 字节。后续步骤在同一个 PowerShell 会话中继续使用 `$backupFile`。

- [ ] **步骤 3：只启动 Docker MySQL 并等待健康**

```powershell
docker compose --env-file .env.docker up -d mysql
docker compose --env-file .env.docker ps mysql
```

预期：`ai-review-mysql` 最终显示 healthy；Windows `MySQL80` 仍保持 Running，宿主机 `3306` 没有 Docker 端口冲突。

- [ ] **步骤 4：将备份复制进容器并导入**

```powershell
docker cp $backupFile ai-review-mysql:/tmp/ai_smart_review.sql
docker exec ai-review-mysql sh -c 'mysql --user=root --password="$MYSQL_ROOT_PASSWORD" < /tmp/ai_smart_review.sql'
if ($LASTEXITCODE -ne 0) { throw 'Docker MySQL 导入失败，保留 SQL 备份并停止启动应用' }
```

预期：导入命令退出码为 0，Windows 源数据库不发生修改。

- [ ] **步骤 5：核对 Docker MySQL 核心数据量**

```powershell
docker exec ai-review-mysql sh -c 'mysql --user=root --password="$MYSQL_ROOT_PASSWORD" --batch ai_smart_review -e "SELECT (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM assignments) AS assignments, (SELECT COUNT(*) FROM submissions) AS submissions, (SELECT COUNT(*) FROM agent_chat_messages) AS legacy_messages;"'
```

预期：`users=34`、`assignments=20`、`submissions=189`、`legacy_messages=6`，与迁移前使用精确 `COUNT(*)` 读取到的源数据库一致。

- [ ] **步骤 6：清理容器内临时副本但保留仓库外备份**

```powershell
docker exec ai-review-mysql rm -f /tmp/ai_smart_review.sql
```

预期：容器临时 SQL 被删除；`$backupFile` 指向的宿主机备份继续保留用于恢复。

### 任务 3：启动完整栈并迁移助手消息与上传文件

**文件：**
- 读取：`backend_python/scripts/migrate_agent_chat_to_pg.py`
- 复制到 Docker 数据卷：`backend_python/uploads/`

- [ ] **步骤 1：构建并启动全部服务**

```powershell
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps
```

预期：6 个服务均启动；MySQL、PostgreSQL、Redis 为 healthy，后端、Worker、前端为 running。后端启动时完成 MySQL 与 PostgreSQL 两套 Alembic 迁移并执行幂等种子初始化。

- [ ] **步骤 2：检查后端启动日志没有迁移错误**

```powershell
docker compose --env-file .env.docker logs --tail 200 backend
```

预期：日志包含依赖就绪与服务启动信息，不包含 Alembic traceback、连接拒绝或表重复创建错误。

- [ ] **步骤 3：把旧助手消息迁移到 PostgreSQL**

```powershell
docker compose --env-file .env.docker exec backend python -m scripts.migrate_agent_chat_to_pg
docker exec ai-review-postgres psql -U langgraph_user -d ai_smart_review -c 'SELECT COUNT(*) AS agent_chat_messages FROM agent_chat_messages;'
```

预期：迁移脚本报告 MySQL 共 6 条并新增 6 条（重复执行则跳过 6 条）；PostgreSQL 查询结果为 6。

- [ ] **步骤 4：复制既有上传文件到 Docker 上传数据卷**

```powershell
docker cp 'backend_python/uploads/.' ai-review-backend:/app/uploads
docker exec ai-review-backend find /app/uploads -type f -maxdepth 2
```

预期：当前本地上传目录中的 1 个业务文件出现在 `/app/uploads`；该目录由 `uploads_data` 数据卷持久化，并由后端与 Worker 共享。

- [ ] **步骤 5：运行部署配置回归测试和服务冒烟检查**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_container_entrypoint.py backend_python/tests/unit/test_assistant_migrations.py -q
Invoke-WebRequest http://localhost:8000/api/docs -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest http://localhost -UseBasicParsing | Select-Object StatusCode
```

预期：pytest 全部 PASS；后端文档和前端首页均返回 HTTP 200。

- [ ] **步骤 6：记录最终运行状态与恢复边界**

```powershell
docker compose --env-file .env.docker ps
Get-Service MySQL80
Get-Item $backupFile | Select-Object FullName, Length, LastWriteTime
git status --short
```

预期：Docker 栈与 Windows MySQL 同时运行；SQL 备份存在；工作区没有未预期改动。若需停止 Docker 栈，使用 `docker compose --env-file .env.docker down`，不要添加 `-v`，以免删除已迁移的数据卷。
