# Docker MySQL 内网访问设计

## 目标

让 Windows MySQL 与 Docker MySQL 同时运行且互不争用宿主机端口，并让本地 Docker 与云服务器使用同一套内部连接配置。

## 设计

- Windows MySQL 继续监听 Windows 的 `127.0.0.1:3306`。
- 删除 Docker Compose 中 MySQL 服务的整个 `ports` 配置，不把 Docker MySQL 映射到宿主机。
- Docker MySQL 容器内部继续监听 `3306`。
- Docker 后端继续通过 Compose 服务名 `mysql:3306` 访问 Docker MySQL，不修改 `DATABASE_URL`，也不修改后端业务代码。
- 本地与云服务器均由 Docker Compose 创建内部网络，并通过 Docker 内部 DNS 解析 `mysql` 服务名。

## 运行结果

| 访问方 | 地址 | 目标 |
| --- | --- | --- |
| Windows 本地后端 | `127.0.0.1:3306` | Windows MySQL |
| Docker 后端 | `mysql:3306` | Docker MySQL |
| 云服务器 Docker 后端 | `mysql:3306` | 云服务器上的 Docker MySQL |

Docker MySQL 不再提供宿主机访问端口。需要管理数据库时，可使用 `docker exec`，或临时通过单独的本地 Compose 覆盖文件增加回环地址端口映射。

## 数据迁移

旧数据从 Windows MySQL 的 `ai_smart_review` 导出，再通过 `docker exec` 导入 Docker MySQL 的同名数据库，无需为 Docker MySQL长期开放宿主机端口。迁移是复制操作，不删除或覆盖 Windows MySQL；迁移完成后两套数据库独立运行，不会自动同步。

## 验证

- `docker compose config` 能成功解析。
- Compose 的 MySQL 服务不存在 `ports` 配置。
- Docker 后端的数据库地址仍为 `mysql:3306`。
- Windows MySQL 保持监听宿主机 `3306`，Docker MySQL 健康启动。
- Docker 后端可以连接 Docker MySQL，且 Windows MySQL 不受影响。
