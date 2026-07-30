# Docker MySQL 宿主机端口调整设计

## 目标

让 Windows MySQL 与 Docker MySQL 可以同时运行，避免二者争用宿主机的 `3306` 端口，同时保持 Docker 内部和云服务器部署配置稳定。

## 设计

- Windows MySQL 继续监听 `127.0.0.1:3306`。
- Docker MySQL 的宿主机映射由 `127.0.0.1:3306:3306` 改为 `127.0.0.1:3307:3306`。
- Docker MySQL 容器内部端口仍为 `3306`。
- Docker 后端继续通过 Compose 服务名 `mysql:3306` 访问数据库，不修改 `DATABASE_URL`，也不修改后端业务代码。
- 端口只绑定 `127.0.0.1`，不向局域网或公网暴露 MySQL。

## 运行结果

| 访问方 | 地址 | 目标 |
| --- | --- | --- |
| Windows 本地程序 | `127.0.0.1:3306` | Windows MySQL |
| Windows 数据库客户端 | `127.0.0.1:3307` | Docker MySQL |
| Docker 后端 | `mysql:3306` | Docker MySQL |

## 数据迁移

旧数据从 Windows MySQL 的 `ai_smart_review` 导出，再导入 Docker MySQL 的同名数据库。迁移是复制操作，不删除或覆盖 Windows MySQL；迁移完成后两套数据库独立运行，不会自动同步。

## 验证

- `docker compose config` 能成功解析。
- Compose 中 MySQL 映射为 `127.0.0.1:3307:3306`。
- Docker 后端的数据库地址仍为 `mysql:3306`。
- Windows `3306` 与 Docker 映射的 `3307` 可同时监听。
