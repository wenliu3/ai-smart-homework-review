# Docker MySQL 双入口访问设计

## 目标

让 Windows MySQL 与 Docker MySQL 同时运行且互不争用宿主机端口；Docker 后端使用内部连接，Navicat 使用仅绑定回环地址的宿主机连接。

## 设计

- Windows MySQL 继续监听 Windows 的 `127.0.0.1:3306`。
- Docker MySQL 映射为 `127.0.0.1:3307:3306`，供宿主机上的 Navicat 访问。
- Docker MySQL 容器内部继续监听 `3306`。
- Docker 后端继续通过 Compose 服务名 `mysql:3306` 访问 Docker MySQL，不修改 `DATABASE_URL`，也不修改后端业务代码。
- 本地与云服务器均由 Docker Compose 创建内部网络，并通过 Docker 内部 DNS 解析 `mysql` 服务名。
- 映射只绑定 `127.0.0.1`，不向局域网或公网直接开放；远程 Navicat 通过 SSH 隧道访问云服务器的 `127.0.0.1:3307`。

## 运行结果

| 访问方 | 地址 | 目标 |
| --- | --- | --- |
| Windows 本地后端 | `127.0.0.1:3306` | Windows MySQL |
| Windows Navicat | `127.0.0.1:3307` | Docker MySQL |
| Docker 后端 | `mysql:3306` | Docker MySQL |
| 云服务器 Docker 后端 | `mysql:3306` | 云服务器上的 Docker MySQL |

云端 Navicat 不直接连接公网 `3307`，而是使用 SSH 隧道把本机连接转发到云服务器的回环地址。

## 数据迁移

旧数据已从 Windows MySQL 的 `ai_smart_review` 导入 Docker MySQL 的同名数据库。修改端口映射只重建容器，不删除 `mysql_data` 数据卷；两套数据库继续独立运行，不会自动同步。

## 验证

- `docker compose config` 能成功解析。
- Compose 的 MySQL 服务端口映射为 `127.0.0.1:3307:3306`。
- Docker 后端的数据库地址仍为 `mysql:3306`。
- Windows MySQL 保持监听宿主机 `3306`，Docker MySQL 映射宿主机 `3307` 并健康启动。
- Docker 后端和 Navicat 均可连接 Docker MySQL，且 Windows MySQL 不受影响。
