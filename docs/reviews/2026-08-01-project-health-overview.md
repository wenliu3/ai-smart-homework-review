# 项目健康总览

审计日期：2026-08-01

审计分支：`codex/ci-regression-recovery`

审计范围：后端、前端、双 Alembic 历史、Docker Compose、GitHub Actions、依赖与仓库卫生。

## 执行摘要

项目在定向恢复 `e723154` 删除的助手运行时、前端助手 API 和测试配置后，已经重新达到可导入、可测试、可类型检查、可构建的状态。后端完整测试为 `649 passed, 1 skipped`，前端完整测试为 `159 passed`，Vite 生产构建成功。因此，本次 GitHub Actions 红灯不是普通推送或网络问题，而是该提交造成的真实代码回归；恢复后的原有业务代码和四份 2026-07-31 设计/计划文档均保留。

当前基线适合继续开发，但不宜直接表述为“项目没有问题”或直接暴露到不受信任网络。静态审计确认了两组最高优先级风险：多个后台管理和教师接口只有登录校验而没有角色/数据归属校验；附件路径由客户端字符串直接拼接到磁盘路径，删除流程缺少目录边界检查。生产前应先修复这两组问题并补充反向权限测试。

## 已验证的健康项

### CI 与构建基线

- `backend_python/app` 可正常导入和编译，恢复前的 `agent_session` 导入错误已消失。
- 后端完整 pytest：`649 passed, 1 skipped, 252 warnings`。
- 前端完整 Vitest：`16` 个测试文件、`159` 个测试全部通过。
- `vue-tsc --noEmit` 与 Vite 生产构建均通过。
- CI 工作流在 `main` 推送和 Pull Request 上执行后端编译/pytest及前端 Vitest/类型检查/构建。

### 助手运行时边界

- PostgreSQL 助手会话、运行、步骤、产物和审批 CRUD 已恢复，`frontend/src/api/assistant.ts` 与后端 API 契约重新对应。
- 教师快捷聊天 `backend_python/app/routers/chat.py` 使用 `require_roles("teacher")`。
- 多角色助手敏感管理端点使用显式角色依赖，管理数据源端点限制为 `superadmin`。
- Agent 工具按调用创建独立业务数据库会话，避免把请求级 pymysql Session 传入 LangGraph 后台线程。
- SSE 输出只发送面向用户的 AI 文本块，不直接透出工具原始结果。

### 数据库、部署与依赖一致性

- 业务 Alembic 只有一个 head：`e2b6c9d4a7f1`。
- 助手 Alembic 只有一个 head：`20260727_03`。
- `pip check` 返回 `No broken requirements found`。
- 使用本机未跟踪的 `.env.docker` 执行 `docker compose config --quiet` 成功。
- Compose 将 MySQL、PostgreSQL、Redis 端口限制在 `127.0.0.1`，并要求显式提供数据库密码和 `JWT_SECRET`。
- 只有 backend 容器运行双迁移，Celery worker 设置 `RUN_MIGRATIONS=0`，迁移职责没有重复竞争。

### 仓库卫生

- 未跟踪真实 `.env`、上传文件、`node_modules`、`dist`、Python 缓存或测试缓存；命中的环境文件均为示例文件。
- `.gitignore` 覆盖本地环境、上传目录、构建产物、缓存和 `.worktrees`。
- 未发现应用源码中的未完成任务或修复标记。
- 四份由 `e723154` 新增的 2026-07-31 设计和计划文档均保留。

## 必须修复

### P0：角色与数据归属校验不完整

证据：

- `backend_python/app/routers/permissions.py:52-110` 的菜单、角色创建/修改/删除和授权接口只依赖 `get_current_user`；`backend_python/app/crud/permission.py` 不接收操作者，也没有角色校验。
- `backend_python/app/routers/correcting.py:14-35` 的提交列表、详情和教师批改接口只要求登录；`backend_python/app/crud/correcting.py:27-143` 没有按教师或作业归属过滤。
- `backend_python/app/routers/dashboard.py:14-35` 的管理员统计和最近用户接口只要求登录，路径中的 `/admin/` 不会自动形成访问控制。
- `backend_python/app/routers/ai_rules.py:33-66` 允许任意已登录用户创建、更新、删除、启停和复制 AI 规则，CRUD 层没有所有者或角色校验。
- `backend_python/app/routers/assignments.py:22-154` 与 `backend_python/app/routers/classes.py:14-95` 多数教师/学生端点只要求登录。部分修改操作在 CRUD 层有归属校验，但教师作业详情、作业学生列表、班级详情、班级学生列表等读取接口缺少等价边界。

影响：普通学生或权限较低账号可能读取全平台用户、提交、班级和运营数据，或调用角色、菜单、规则、批改等管理操作。前端路由守卫只能隐藏界面，不能替代后端授权。

修复方向：

1. 为每个路由建立角色矩阵，在路由层统一使用 `require_roles`。
2. 所有读取和写入在 CRUD 层再次校验资源归属，教师只能访问自己班级和作业，学生只能访问自己加入班级及自己的提交。
3. 对角色不匹配、同角色越权、跨班级/跨作业访问增加 403 集成测试；权限、上传、看板和批改目前没有对应的安全回归文件。

### P0：附件路径可越出上传目录，且缺少文件归属

证据：

- `backend_python/app/schemas/submission.py:12-17` 将 `attachments` 定义为任意字典列表，`fileUrl` 没有格式或服务器签发校验。
- `backend_python/app/crud/submission.py:111-123` 用字符串替换得到文件名，再通过 `os.path.join(upload_dir, filename)` 删除文件，没有 `resolve()` 后的目录边界检查。
- 同一客户端附件字符串在 `backend_python/app/crud/submission.py:167-185` 被直接用于读取和文本提取。
- `backend_python/app/routers/upload.py:61-101` 的下载、预览、删除同样直接执行 `settings.upload_path / filename`，没有规范化、边界或上传者校验。
- `backend_python/app/main.py:67-68` 将整个上传目录公开挂载到 `/uploads`，会绕过下载/预览端点的认证。

影响：具备作业提交条件的学生可以把带目录跳转片段的附件 URL 写入草稿，在删除草稿时尝试删除上传目录以外、进程有权限访问的文件。任意已登录用户也可按已知文件名删除其他人的上传；公开静态挂载使附件保密性无法由 API 权限控制。

修复方向：

1. 服务器生成不可猜测的文件 ID，并把上传者、用途、关联作业/提交和磁盘相对路径写入数据库；业务请求只提交文件 ID。
2. 统一使用安全路径解析函数，拒绝绝对路径、`..`、路径分隔符和不在 `upload_path.resolve()` 子树内的结果。
3. 删除操作按文件记录验证所有者或教师的资源归属；静态附件改为受控下载响应，或只公开明确允许匿名访问的资源目录。
4. 增加目录穿越、跨用户删除、未认证读取、伪造附件 URL 和超大压缩文档测试。

### P1：生产前端依赖存在已知漏洞

`npm audit --omit=dev` 报告 `10` 个生产依赖漏洞：`1 critical`、`6 high`、`3 moderate`。涉及直接或传递依赖 `form-data`、`axios`、`lodash`、`lodash-es`、`postcss`、`preact`、`xlsx`、`echarts`、`element-plus` 和 `follow-redirects`。其中多数有可用修复；当前 `xlsx` 审计项没有注册表内自动修复，`echarts` 建议升级会跨主版本。

影响：漏洞是否可利用取决于实际调用路径，但在公网部署前不能忽略 critical/high 项。直接执行 `npm audit fix --force` 可能引入破坏性升级。

修复方向：逐包升级并运行完整前端测试/构建；对 `xlsx` 评估受维护替代包或上游安全版本；把生产依赖审计加入 CI，并通过明确的例外清单管理暂时无法修复的项。

### P1：默认凭据与前端令牌日志应收紧

- `backend_python/app/config.py:13-24` 和 `backend_python/.env.example` 提供可直接运行的默认数据库密码、JWT 密钥和默认用户密码。Docker 部署会强制覆盖数据库密码与 JWT 密钥，但非 Docker 启动可能意外使用默认值。
- `frontend/src/store/modules/user.ts:196-199` 会在浏览器控制台输出刷新令牌前 10 个字符；`frontend/src/utils/request.ts` 还保留大量认证流程调试日志。

影响：错误部署可能使用公开已知凭据；令牌前缀和认证错误对象会增加浏览器日志、录屏或远程日志采集中的敏感信息暴露面。

修复方向：生产模式启动时拒绝默认密钥和密码；示例文件使用明显占位值；移除令牌内容日志，并用受环境开关控制的结构化调试日志替代。

## 建议修改

### 统一后端分层

- `backend_python/app/routers/assistant.py` 仍含直接 ORM 查询和 `commit()`，与项目约定的“路由薄、CRUD 厚”不一致。
- `backend_python/app/routers/assignments.py` 在路由中处理临时文件和查重提取，`backend_python/app/routers/classes.py` 在路由中分支处理管理员逻辑。

建议把业务分支、数据库访问和文件处理下沉到 CRUD/service，使权限校验、事务和测试入口集中。

### 统一前端网络访问

助手 SSE 使用原生 `fetch` 是合理的，但上传、下载、预览、查重和部分删除操作也各自拼接 `Authorization`。这些请求不会自动共享 Axios 的 401 刷新队列和统一错误处理。

建议抽出一个支持 Blob/SSE 的认证 fetch 辅助层，至少统一令牌刷新、403 处理、超时、取消与错误格式。

### 拆分大文件并优化产物

- `backend_python/app/agent/service.py` 超过 `1500` 行。
- 多个 Vue 页面和组件超过 `1000` 行，教师看板、作业详情、提交页、查重页和批改抽屉最明显。
- 构建产物中 `ai_loading.gif` 约 `6.0 MiB`；Element Plus、WangEditor、图表和主入口 chunk 较大。

建议按职责拆分 service/composable/子组件，压缩或改用更高效的加载动画格式，并用路由级懒加载和包体预算防止体积继续增长。

### 扩充 CI 门禁

当前 CI 能捕获本次导入、测试、类型和构建回归，但没有覆盖：Docker 镜像构建、双 Alembic head 检查、`pip check`、生产依赖审计、格式/静态检查和权限安全测试。建议把这些检查逐步加入独立 job，依赖漏洞先采用可维护的阈值和例外清单，避免无计划地永久忽略或一次性强制升级。

## 仅供参考

- 后端测试的唯一 skip 来自容器入口测试缺少 gitignored `.env.docker`；Compose 配置已在主工作区使用本地环境文件单独验证。
- pytest 警告主要包括 Starlette TestClient/httpx 兼容性、测试 JWT 密钥不足 32 字节和 Pillow `Image.getdata()` 弃用。Pillow 计划在 2027-10-15 发布的 14.0.0 中移除该 API，应在升级前替换。
- Vite 提示其 CJS Node API 已弃用，可在构建工具升级窗口处理。
- `npm audit` 全依赖结果为 `27` 个漏洞（含开发依赖），高于生产依赖结果；应优先处理生产依赖，再处理工具链。
- 本次是代码、配置、依赖和静态安全审计，没有连接真实 MySQL/PostgreSQL 数据、运行完整 Docker 镜像或执行主动渗透测试，因此不能据此证明生产环境绝对安全。

## 验证命令与结果

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| 后端导入 | `python -c "import app.main"` | 通过 |
| 后端语法 | `python -m compileall -q app` | 通过 |
| 后端测试 | `python -m pytest -q` | `649 passed, 1 skipped` |
| 前端测试 | `npx vitest run` | `159 passed` |
| 前端类型与构建 | `npm run build` | 通过 |
| 业务迁移 | `python -m alembic -c alembic.ini heads` | 单 head：`e2b6c9d4a7f1` |
| 助手迁移 | `python -m alembic -c alembic_assistant.ini heads` | 单 head：`20260727_03` |
| Python 依赖 | `python -m pip check` | 无损坏依赖 |
| Compose | `docker compose --env-file .env.docker config --quiet` | 通过 |
| 生产依赖审计 | `npm audit --omit=dev` | `10` 个漏洞，非零退出 |

## 建议执行顺序

1. 修复附件路径边界和文件归属，并补安全测试。
2. 为权限、批改、看板、AI 规则、作业和班级接口补齐角色与资源归属校验。
3. 分批升级存在 critical/high 漏洞的前端生产依赖。
4. 移除令牌日志并为非 Docker 生产启动增加弱默认值保护。
5. 再处理分层、大文件、包体和 CI 增强。
