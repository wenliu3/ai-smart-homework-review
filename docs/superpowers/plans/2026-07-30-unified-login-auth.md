# 统一账号登录与认证错误处理实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将登录页改为单一账号输入，并修复登录 401 被错误当作 Token 过期、切换账号残留旧会话状态的问题。

**架构：** 保留后端现有 `usernameOrEmailOrStudentId` 统一查询接口；前端新增纯函数定义公开认证请求边界，登录表单统一发送一个账号字段。Vuex 用户模块区分“合并资料”和“替换/清空会话”，响应拦截器只对受保护请求的 401 执行单飞刷新。

**技术栈：** Vue 3、TypeScript、Vuex 4、Axios、Element Plus、Vitest、Vue Test Utils、FastAPI、SQLAlchemy、pytest。

**设计规格：** `docs/superpowers/specs/2026-07-30-unified-login-auth-design.md`

---

## 文件结构

- 创建 `backend_python/tests/unit/test_auth_login.py`：锁定用户名、邮箱、学号统一登录的既有后端契约。
- 创建 `frontend/src/utils/auth-request.ts`：提供公开认证路径识别、Token 附加和 401 刷新决策纯函数。
- 创建 `frontend/src/utils/__tests__/auth-request.spec.ts`：覆盖公开认证与受保护请求的分流决策。
- 创建 `frontend/src/views/__tests__/Login.spec.ts`：覆盖单一账号输入和统一登录载荷。
- 创建 `frontend/src/store/modules/__tests__/user.spec.ts`：覆盖会话完整替换和完整清理。
- 修改 `frontend/src/views/Login.vue`：移除登录方式选择，改为一个账号字段。
- 修改 `frontend/src/utils/request.ts`：公开认证请求不附加 Token、不刷新、不弹会话过期框。
- 修改 `frontend/src/store/modules/user.ts`：增加替换会话、清理会话语义，并在登录/刷新/退出中使用。

### 任务 1：锁定后端统一账号登录契约

**文件：**
- 创建：`backend_python/tests/unit/test_auth_login.py`
- 验证：`backend_python/app/crud/auth.py`

- [ ] **步骤 1：添加后端契约测试**

```python
import pytest

from app.core.security import hash_password
from app.models import User


@pytest.fixture()
def login_user(db):
    user = User(
        username="login_teacher",
        email="login_teacher@test.local",
        student_id="2024999",
        password=hash_password("test-password"),
        name="登录测试用户",
        role="teacher",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.parametrize(
    "account",
    ["login_teacher", "login_teacher@test.local", "2024999"],
)
def test_login_accepts_username_email_or_student_id(client, login_user, account):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "usernameOrEmailOrStudentId": account,
            "password": "test-password",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["user"]["id"] == str(login_user.id)


@pytest.mark.parametrize("account,password", [
    ("missing-user", "test-password"),
    ("login_teacher", "wrong-password"),
])
def test_login_rejects_unknown_account_or_wrong_password(
    client, login_user, account, password,
):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "usernameOrEmailOrStudentId": account,
            "password": password,
        },
    )

    assert response.status_code == 401
    assert response.json()["message"] == "账号或密码错误"
```

- [ ] **步骤 2：运行契约测试并记录基线**

运行：

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_auth_login.py -q
```

预期：`5 passed`。这些是对后端既有能力的特征测试；如果失败，先按实际统一响应结构修正测试读取方式，不改变登录查询语义。

- [ ] **步骤 3：提交后端契约测试**

```powershell
git add backend_python/tests/unit/test_auth_login.py
git commit -m "test: 锁定统一账号登录契约"
```

### 任务 2：登录页改为单一账号输入

**文件：**
- 创建：`frontend/src/views/__tests__/Login.spec.ts`
- 修改：`frontend/src/views/Login.vue`

- [ ] **步骤 1：编写登录页失败测试**

```ts
import ElementPlus from "element-plus";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { createStore } from "vuex";
import { describe, expect, it, vi } from "vitest";

import Login from "../Login.vue";

async function mountLogin() {
  const loginAction = vi.fn().mockResolvedValue({
    mustChangePassword: false,
    user: { role: "teacher" },
  });
  const store = createStore({
    modules: {
      user: {
        namespaced: true,
        actions: { login: loginAction },
      },
    },
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/login", component: Login },
      { path: "/dashboard", component: { template: "<div>dashboard</div>" } },
    ],
  });
  await router.push("/login");
  await router.isReady();
  const wrapper = mount(Login, {
    global: { plugins: [store, router, ElementPlus] },
  });
  return { wrapper, loginAction };
}

describe("Login", () => {
  it("只显示一个统一账号输入，不显示登录方式选择", async () => {
    const { wrapper } = await mountLogin();

    expect(wrapper.find('[data-testid="login-account"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("登录方式");
    expect(wrapper.text()).toContain("用户名、邮箱或学号");
  });

  it("去除账号首尾空白后发送统一登录字段", async () => {
    const { wrapper, loginAction } = await mountLogin();
    await wrapper.find('[data-testid="login-account"] input').setValue("  teacher  ");
    await wrapper.find('[data-testid="login-password"] input').setValue("123456789");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(loginAction).toHaveBeenCalledWith(
      expect.anything(),
      {
        usernameOrEmailOrStudentId: "teacher",
        password: "123456789",
        rememberMe: true,
      },
    );
  });
});
```

- [ ] **步骤 2：运行登录页测试，确认红灯**

运行：

```powershell
cd frontend
npx vitest run src/views/__tests__/Login.spec.ts
```

预期：FAIL，`data-testid="login-account"` 不存在，并且页面仍包含“登录方式”。

- [ ] **步骤 3：最小化修改登录模板**

在注册用户名字段之后，用以下登录字段替换分段选择和三个登录字段：

```vue
<el-form-item v-if="!isRegister" label="账号" prop="account">
  <el-input
    v-model="form.account"
    data-testid="login-account"
    placeholder="请输入用户名、邮箱或学号"
    autocomplete="username"
    class="!rounded"
  />
</el-form-item>
```

给密码输入增加测试标识和浏览器自动填充语义：

```vue
<el-input
  v-model="form.password"
  data-testid="login-password"
  placeholder="请输入密码"
  type="password"
  autocomplete="current-password"
  show-password
  class="!rounded"
/>
```

- [ ] **步骤 4：最小化修改登录表单状态与提交逻辑**

表单状态保留注册字段，删除 `studentId`、`loginType` 和 `handleLoginTypeChange`，增加：

```ts
const form = reactive({
  account: "",
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
  rememberMe: true,
});
```

增加账号校验并注册到规则：

```ts
const validateAccount = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  const account = value?.trim();
  if (!account) {
    callback(new Error("请输入用户名、邮箱或学号"));
    return;
  }
  if (account.length > 255) {
    callback(new Error("账号长度不能超过255个字符"));
    return;
  }
  callback();
};

const rules = reactive<FormRules>({
  account: [{ validator: validateAccount, trigger: "blur" }],
  // username、email、password、confirmPassword 保持既有规则
});
```

登录分支改为直接发送统一字段：

```ts
const loginData = {
  usernameOrEmailOrStudentId: form.account.trim(),
  password: form.password,
  rememberMe: form.rememberMe,
};
const loginResponse = await store.dispatch("user/login", loginData);
```

- [ ] **步骤 5：运行登录页测试，确认绿灯**

运行：

```powershell
cd frontend
npx vitest run src/views/__tests__/Login.spec.ts
```

预期：`2 passed`，无未处理异常。

- [ ] **步骤 6：提交统一登录界面**

```powershell
git add frontend/src/views/Login.vue frontend/src/views/__tests__/Login.spec.ts
git commit -m "feat: 统一登录账号输入"
```

### 任务 3：隔离公开认证请求与 Token 刷新

**文件：**
- 创建：`frontend/src/utils/auth-request.ts`
- 创建：`frontend/src/utils/__tests__/auth-request.spec.ts`
- 修改：`frontend/src/utils/request.ts`

- [ ] **步骤 1：编写认证请求决策失败测试**

```ts
import { describe, expect, it } from "vitest";

import {
  getResponseErrorMessage,
  isPublicAuthRequest,
  shouldAttachAccessToken,
  shouldAttemptTokenRefresh,
} from "../auth-request";

describe("auth request policy", () => {
  it.each([
    "/v1/auth/login",
    "/api/v1/auth/login?redirect=%2F",
    "/v1/auth/register",
    "/v1/auth/forgot-password",
    "/v1/auth/reset-password",
    "/v1/auth/refresh-token",
    "/auth/login",
    "/auth/register",
  ])("将 %s 识别为公开认证请求", (url) => {
    expect(isPublicAuthRequest(url)).toBe(true);
    expect(shouldAttachAccessToken(url)).toBe(false);
    expect(shouldAttemptTokenRefresh(401, url, false)).toBe(false);
  });

  it("只对未重试过的受保护 401 请求刷新令牌", () => {
    expect(shouldAttemptTokenRefresh(401, "/teacher/assignments", false)).toBe(true);
    expect(shouldAttemptTokenRefresh(401, "/teacher/assignments", true)).toBe(false);
    expect(shouldAttemptTokenRefresh(403, "/teacher/assignments", false)).toBe(false);
  });

  it("保留后端认证错误消息", () => {
    expect(getResponseErrorMessage({ message: "账号或密码错误" }, "登录失败"))
      .toBe("账号或密码错误");
  });
});
```

- [ ] **步骤 2：运行决策测试，确认红灯**

运行：

```powershell
cd frontend
npx vitest run src/utils/__tests__/auth-request.spec.ts
```

预期：FAIL，无法导入 `../auth-request`。

- [ ] **步骤 3：实现认证请求决策纯函数**

```ts
const PUBLIC_AUTH_PATHS = new Set([
  "/v1/auth/login",
  "/v1/auth/register",
  "/v1/auth/forgot-password",
  "/v1/auth/reset-password",
  "/v1/auth/refresh-token",
  "/auth/login",
  "/auth/register",
]);

function normalizeRequestPath(url = ""): string {
  const pathname = new URL(url, "http://local.test").pathname;
  return pathname.replace(/^\/api(?=\/)/, "");
}

export function isPublicAuthRequest(url?: string): boolean {
  return PUBLIC_AUTH_PATHS.has(normalizeRequestPath(url));
}

export function shouldAttachAccessToken(url?: string): boolean {
  return !isPublicAuthRequest(url);
}

export function shouldAttemptTokenRefresh(
  status: number | undefined,
  url: string | undefined,
  alreadyRetried: boolean,
): boolean {
  return status === 401 && !alreadyRetried && !isPublicAuthRequest(url);
}

export function getResponseErrorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object") {
    const message = (data as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}
```

- [ ] **步骤 4：将请求拦截器接入公开认证策略**

在 `request.ts` 导入上述函数，并把请求 Token 条件改为：

```ts
if (token && shouldAttachAccessToken(config.url)) {
  config.headers["Authorization"] = `Bearer ${token}`;
}
```

保留现有 ASCII Token 校验，但只在需要附加访问令牌时执行。

- [ ] **步骤 5：将响应 401 接入公开认证策略**

在 HTTP 错误分支最前面处理公开认证请求：

```ts
const status = error.response?.status;
const requestUrl = originalRequest?.url;

if (status === 401 && isPublicAuthRequest(requestUrl)) {
  const message = getResponseErrorMessage(
    error.response?.data,
    requestUrl?.includes("/login") ? "账号或密码错误" : "认证请求失败",
  );
  return Promise.reject(new Error(message));
}
```

将受保护请求刷新条件替换为：

```ts
if (shouldAttemptTokenRefresh(status, requestUrl, !!originalRequest._retry)) {
  // 保留现有单飞刷新和请求队列实现
}
```

删除“刷新接口 401 立即调用 `handleAuthError`”的内层分支；刷新请求错误直接回到发起刷新操作的外层 `catch`，由外层统一处理一次。

标准响应体中出现认证业务码时同样检查 `response.config.url`：公开认证请求只拒绝并保留消息，受保护请求才调用 `handleAuthError`。

- [ ] **步骤 6：运行认证请求决策测试，确认绿灯**

运行：

```powershell
cd frontend
npx vitest run src/utils/__tests__/auth-request.spec.ts
```

预期：`10 passed`（参数化公开路径 8 条，另 2 个独立行为用例）。

- [ ] **步骤 7：提交认证请求边界修复**

```powershell
git add frontend/src/utils/auth-request.ts frontend/src/utils/__tests__/auth-request.spec.ts frontend/src/utils/request.ts
git commit -m "fix: 隔离登录失败与令牌刷新"
```

### 任务 4：完整替换和清理用户会话

**文件：**
- 创建：`frontend/src/store/modules/__tests__/user.spec.ts`
- 修改：`frontend/src/store/modules/user.ts`
- 修改：`frontend/src/utils/request.ts`

- [ ] **步骤 1：编写用户会话失败测试**

```ts
import { beforeEach, describe, expect, it } from "vitest";

import userModule from "../user";

describe("user session state", () => {
  beforeEach(() => localStorage.clear());

  it("新登录会话完整替换旧账号字段", () => {
    const state = userModule.state();
    state.userInfo = {
      token: "student-token",
      refreshToken: "student-refresh",
      role: "student",
      studentId: "2024041",
    };

    userModule.mutations.REPLACE_USER_INFO(state, {
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      role: "teacher",
      username: "teacher",
    });

    expect(state.userInfo).toEqual({
      token: "teacher-token",
      refreshToken: "teacher-refresh",
      role: "teacher",
      username: "teacher",
    });
    expect(state.userInfo.studentId).toBeUndefined();
    expect(localStorage.getItem("token")).toBe("teacher-token");
  });

  it("清理会话同时清除内存和本地存储", () => {
    const state = userModule.state();
    state.userInfo = { token: "old-token", refreshToken: "old-refresh" };
    (state as any).refreshPromise = Promise.resolve();
    localStorage.setItem("token", "old-token");
    localStorage.setItem("userInfo", JSON.stringify(state.userInfo));

    userModule.mutations.CLEAR_SESSION(state);

    expect(state.userInfo).toBeNull();
    expect(state.refreshPromise).toBeNull();
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem("userInfo")).toBeNull();
  });
});
```

- [ ] **步骤 2：运行会话测试，确认红灯**

运行：

```powershell
cd frontend
npx vitest run src/store/modules/__tests__/user.spec.ts
```

预期：FAIL，`REPLACE_USER_INFO` 和 `CLEAR_SESSION` 不存在。

- [ ] **步骤 3：实现会话替换与清理 mutation**

```ts
REPLACE_USER_INFO(state, userInfo) {
  state.userInfo = userInfo ? { ...userInfo } : null;
  if (state.userInfo) {
    localStorage.setItem("userInfo", JSON.stringify(state.userInfo));
    if (state.userInfo.token) localStorage.setItem("token", state.userInfo.token);
  } else {
    localStorage.removeItem("userInfo");
    localStorage.removeItem("token");
  }
},

CLEAR_SESSION(state) {
  state.userInfo = null;
  state.refreshPromise = null;
  localStorage.removeItem("userInfo");
  localStorage.removeItem("token");
},
```

- [ ] **步骤 4：让登录、刷新失败和退出使用新语义**

增加动作：

```ts
replaceSession({ commit }, userInfo) {
  commit("REPLACE_USER_INFO", userInfo);
},

clearSession({ commit }) {
  commit("CLEAR_SESSION");
},
```

登录成功后构造完整新会话并调用 `replaceSession`，不要再通过 `SET_USER_INFO` 与旧账号合并：

```ts
const session = {
  token: response.token,
  refreshToken: response.refreshToken,
  tokenExpiresAt: Date.now() + response.expiresIn * 1000,
  mustChangePassword: response.mustChangePassword,
  isFirstLogin: response.isFirstLogin,
  ...(response.user || {}),
};
await dispatch("replaceSession", session);
```

缺少刷新令牌、刷新失败以及退出登录的 `finally` 分支统一调用 `CLEAR_SESSION`；刷新成功和资料加载仍使用 `SET_USER_INFO` 合并当前会话。

- [ ] **步骤 5：认证失败时同时清理用户与权限**

在 `request.ts` 的 `handleAuthError` 首次进入时同步发起两个清理动作：

```ts
void store.dispatch("user/clearSession");
void store.dispatch("auth/clearPermissions");
```

删除仅清理权限、却保留 `user.state.userInfo` 的旧逻辑。保留 `isHandling401`，确保对话框和跳转只执行一次。

- [ ] **步骤 6：运行会话测试，确认绿灯**

运行：

```powershell
cd frontend
npx vitest run src/store/modules/__tests__/user.spec.ts
```

预期：`2 passed`。

- [ ] **步骤 7：提交会话状态修复**

```powershell
git add frontend/src/store/modules/user.ts frontend/src/store/modules/__tests__/user.spec.ts frontend/src/utils/request.ts
git commit -m "fix: 完整替换并清理登录会话"
```

### 任务 5：完整自动化验证与浏览器回归

**文件：**
- 验证：`frontend/src/views/Login.vue`
- 验证：`frontend/src/utils/request.ts`
- 验证：`frontend/src/store/modules/user.ts`
- 验证：`backend_python/app/crud/auth.py`

- [ ] **步骤 1：运行全部前端单元测试**

```powershell
cd frontend
npm test
```

预期：所有 Vitest 用例通过，输出中无失败用例和未处理 Promise 拒绝。

- [ ] **步骤 2：运行前端类型检查**

```powershell
cd frontend
npx vue-tsc --noEmit
```

预期：退出码 0，无 TypeScript 错误。

- [ ] **步骤 3：运行后端认证测试和后端语法检查**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_auth_login.py -q
python -m compileall -q backend_python/app
```

预期：认证测试全部通过，语法检查退出码 0。

- [ ] **步骤 4：检查差异质量**

```powershell
git diff --check
git status --short
```

预期：`git diff --check` 无输出；状态只包含本计划列出的实现与测试文件。

- [ ] **步骤 5：重建并启动前端容器**

```powershell
docker compose --env-file .env.docker up -d --build frontend
docker compose --env-file .env.docker ps
```

预期：前端容器为 `healthy`，其余服务保持运行。

- [ ] **步骤 6：浏览器验证错误密码**

在 `http://localhost/login` 输入 `teacher` 和错误密码并提交，验证：

```text
页面内错误：账号或密码错误
认证失败对话框：不存在
登录已过期提示：不存在
刷新令牌请求：不发生
```

- [ ] **步骤 7：浏览器验证三种账号与角色切换**

依次执行并检查页面身份：

```text
用户名 teacher → 教师工作台，显示张老师
教师邮箱 → 教师工作台，显示张老师
学号 2024041 → 学生学习台，显示赵一
学生退出后再次用 teacher → 教师工作台，菜单和姓名无学生字段残留
```

- [ ] **步骤 8：提交最终验证记录**

```powershell
git status --short
git log -5 --oneline
```

预期：实现提交完整存在，工作区没有意外修改。最终报告列出自动化测试数量、浏览器验证账号类型和 Token 异常复现前后的差异。
